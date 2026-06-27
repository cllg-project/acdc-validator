#!/usr/bin/env python3
"""
Data migration: backfill xml_line_id from ALTO XML files.

Run AFTER applying the Alembic schema migration:

    flask db upgrade
    env/bin/python scripts/migrate_xml_line_ids.py [--data-path ...]

The script re-reads each Line's ALTO XML, finds the TextLine at line_index,
and stores its @ID attribute. Lines in XMLs that carry no @ID are set to NULL
(gracefully — no crash).
"""
import argparse
import os
import sys
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
BATCH_SIZE = 500


def backfill(app, data_path):
    from app.models import Line
    from app import db

    with app.app_context():
        lines = Line.query.all()
        print(f"Backfilling xml_line_id for {len(lines)} lines…")

        updated = skipped = no_id = 0
        for i, line in enumerate(lines, 1):
            xml_abs = os.path.join(data_path, line.alto_xml)
            if not os.path.exists(xml_abs):
                print(f"  [WARN] Missing XML: {line.alto_xml}", flush=True)
                skipped += 1
                continue

            try:
                tree = ET.parse(xml_abs)
            except ET.ParseError as exc:
                print(f"  [WARN] XML parse error {line.alto_xml}: {exc}", flush=True)
                skipped += 1
                continue

            root = tree.getroot()
            text_lines = root.findall(f".//{{{ALTO_NS}}}TextLine")

            if line.line_index >= len(text_lines):
                print(
                    f"  [WARN] line_index={line.line_index} out of range "
                    f"({len(text_lines)} lines) in {line.alto_xml}",
                    flush=True,
                )
                skipped += 1
                continue

            xml_id = text_lines[line.line_index].get("ID")
            line.xml_line_id = xml_id
            if xml_id is None:
                no_id += 1
            else:
                updated += 1

            if i % BATCH_SIZE == 0:
                db.session.commit()
                print(f"  {i}/{len(lines)} committed…", flush=True)

        db.session.commit()
        print(
            f"\nDone. {updated} IDs set, {no_id} lines had no @ID in XML, {skipped} skipped."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", default=None, help="Path to book-samples folder")
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    data_path = args.data_path or app.config["DATA_PATH"]
    backfill(app, data_path)


if __name__ == "__main__":
    main()
