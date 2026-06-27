import os
import pytest
from xml.etree import ElementTree as ET

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


@pytest.fixture(scope="session")
def app():
    from app import create_app, db as _db

    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DATA_PATH": FIXTURES_DIR,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture()
def db(app):
    from app import db as _db
    yield _db
    _db.session.rollback()


@pytest.fixture()
def loaded_lines(app, db):
    """Ingest sample_alto.xml into the test DB, yielding the Line rows."""
    from app.models import Line

    xml_rel = "sample_alto.xml"
    xml_abs = os.path.join(FIXTURES_DIR, xml_rel)
    book_id = "test_book"

    tree = ET.parse(xml_abs)
    root = tree.getroot()
    text_lines = root.findall(f".//{{{ALTO_NS}}}TextLine")

    inserted = []
    for idx, tl in enumerate(text_lines):
        string_el = tl.find(f"{{{ALTO_NS}}}String")
        if string_el is None:
            continue
        ocr_text = string_el.get("CONTENT", "").strip()
        if not ocr_text:
            continue

        polygon_el = tl.find(f".//{{{ALTO_NS}}}Polygon")
        points = polygon_el.get("POINTS", "") if polygon_el is not None else ""

        hpos = int(string_el.get("HPOS", tl.get("HPOS", 0)))
        vpos = int(string_el.get("VPOS", tl.get("VPOS", 0)))
        width = int(string_el.get("WIDTH", tl.get("WIDTH", 0)))
        height = int(string_el.get("HEIGHT", tl.get("HEIGHT", 0)))

        line = Line(
            book_id=book_id,
            page_png="test_page.png",
            page_jpg="test_page.jpg",
            alto_xml=xml_rel,
            line_index=idx,
            hpos=hpos,
            vpos=vpos,
            width=width,
            height=height,
            polygon_points=points,
            ocr_text=ocr_text,
        )
        db.session.add(line)
        inserted.append(line)

    db.session.commit()
    yield inserted

    for line in inserted:
        db.session.delete(line)
    db.session.commit()
