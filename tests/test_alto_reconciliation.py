"""Tests for ALTO XML reconciliation and xml_line_id migration."""
import os
from xml.etree import ElementTree as ET

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

EXPECTED_IDS = ["line_1", "line_2", "line_3"]
EXPECTED_CONTENTS = [
    "First line of Greek text",
    "Second line of Greek text",
    "Third line of Greek text",
]
EXPECTED_POLYGONS = [
    "100 200 95 230 100 250 900 250 905 220 900 200",
    "100 350 98 380 100 405 850 405 852 375 850 350",
    "100 510 97 540 100 558 800 558 803 528 800 510",
]


def _parse_text_lines(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    return root.findall(f".//{{{ALTO_NS}}}TextLine")


# ---------------------------------------------------------------------------
# XML parsing tests (no DB)
# ---------------------------------------------------------------------------


def test_parse_extracts_line_ids():
    xml_path = os.path.join(FIXTURES_DIR, "sample_alto.xml")
    text_lines = _parse_text_lines(xml_path)
    ids = [tl.get("ID") for tl in text_lines]
    assert ids == EXPECTED_IDS


def test_parse_extracts_polygon_points():
    xml_path = os.path.join(FIXTURES_DIR, "sample_alto.xml")
    text_lines = _parse_text_lines(xml_path)
    for tl, expected_pts in zip(text_lines, EXPECTED_POLYGONS):
        polygon_el = tl.find(f".//{{{ALTO_NS}}}Polygon")
        assert polygon_el is not None
        assert polygon_el.get("POINTS") == expected_pts


def test_parse_extracts_ocr_text():
    xml_path = os.path.join(FIXTURES_DIR, "sample_alto.xml")
    text_lines = _parse_text_lines(xml_path)
    for tl, expected_text in zip(text_lines, EXPECTED_CONTENTS):
        string_el = tl.find(f"{{{ALTO_NS}}}String")
        assert string_el is not None
        assert string_el.get("CONTENT") == expected_text


def test_no_id_xml_returns_none_ids():
    xml_path = os.path.join(FIXTURES_DIR, "sample_alto_no_ids.xml")
    text_lines = _parse_text_lines(xml_path)
    ids = [tl.get("ID") for tl in text_lines]
    assert all(id_ is None for id_ in ids)


# ---------------------------------------------------------------------------
# DB ingest tests
# ---------------------------------------------------------------------------


def test_ingest_line_count(loaded_lines):
    assert len(loaded_lines) == 3


def test_ingest_line_index_order(loaded_lines):
    indices = [line.line_index for line in loaded_lines]
    assert indices == [0, 1, 2]


def test_ingest_polygon_points_stored(loaded_lines):
    for line, expected_pts in zip(loaded_lines, EXPECTED_POLYGONS):
        assert line.polygon_points == expected_pts


def test_ingest_ocr_text_stored(loaded_lines):
    for line, expected_text in zip(loaded_lines, EXPECTED_CONTENTS):
        assert line.ocr_text == expected_text


def test_ingest_bbox_stored(loaded_lines):
    expected_bboxes = [
        (100, 200, 800, 50),
        (100, 350, 750, 55),
        (100, 510, 700, 48),
    ]
    for line, (hpos, vpos, width, height) in zip(loaded_lines, expected_bboxes):
        assert (line.hpos, line.vpos, line.width, line.height) == (hpos, vpos, width, height)


# ---------------------------------------------------------------------------
# Migration / backfill logic tests
# ---------------------------------------------------------------------------


def _run_backfill(lines, data_path):
    """Mirror the backfill logic from scripts/migrate_xml_line_ids.py."""
    for line in lines:
        xml_abs = os.path.join(data_path, line.alto_xml)
        tree = ET.parse(xml_abs)
        root = tree.getroot()
        text_lines = root.findall(f".//{{{ALTO_NS}}}TextLine")
        if line.line_index < len(text_lines):
            tl = text_lines[line.line_index]
            line.xml_line_id = tl.get("ID")
        else:
            line.xml_line_id = None


def test_migration_backfills_xml_line_id(loaded_lines, db):
    _run_backfill(loaded_lines, FIXTURES_DIR)
    db.session.commit()

    for line, expected_id in zip(loaded_lines, EXPECTED_IDS):
        assert line.xml_line_id == expected_id


def test_all_db_lines_reconcile_to_alto(loaded_lines, db):
    _run_backfill(loaded_lines, FIXTURES_DIR)
    db.session.commit()

    xml_path = os.path.join(FIXTURES_DIR, "sample_alto.xml")
    text_lines = _parse_text_lines(xml_path)
    xml_id_map = {tl.get("ID"): tl for tl in text_lines}

    for line in loaded_lines:
        assert line.xml_line_id in xml_id_map, (
            f"Line {line.id} xml_line_id={line.xml_line_id!r} not found in ALTO"
        )
        tl = xml_id_map[line.xml_line_id]
        string_el = tl.find(f"{{{ALTO_NS}}}String")
        assert string_el.get("CONTENT") == line.ocr_text


def test_missing_id_handled_gracefully(loaded_lines, db):
    """Backfill against an XML that has no @ID attributes sets xml_line_id to None."""
    for line in loaded_lines:
        line.alto_xml = "sample_alto_no_ids.xml"
    db.session.commit()

    _run_backfill(loaded_lines, FIXTURES_DIR)
    db.session.commit()

    for line in loaded_lines:
        assert line.xml_line_id is None

    # Restore so other tests are unaffected
    for line in loaded_lines:
        line.alto_xml = "sample_alto.xml"
    db.session.commit()
