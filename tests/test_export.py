"""Tests for the CSV export used to compute inter-annotator agreement."""
import csv
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import User, Line, Annotation

_line_counter = 0


def make_line(db, suffix=""):
    global _line_counter
    _line_counter += 1
    line = Line(
        book_id=f"export_book_{suffix or _line_counter}",
        page_png="p.png",
        page_jpg="p.jpg",
        alto_xml="folder/page-0001.xml",
        line_index=0,
        hpos=0, vpos=0, width=100, height=20,
        polygon_points="",
        ocr_text="original ocr text",
    )
    db.session.add(line)
    db.session.flush()
    return line


def make_user(db, name):
    user = User(username=name, password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def login(client, db, username):
    user = make_user(db, username)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return user


def test_export_csv_columns_and_rows(app, db):
    client = app.test_client()

    line1 = make_line(db, "one")
    line2 = make_line(db, "two")

    u1 = make_user(db, "annA")
    u2 = make_user(db, "annB")

    db.session.add(Annotation(user_id=u1.id, line_id=line1.id, status="validated"))
    db.session.add(Annotation(user_id=u2.id, line_id=line1.id, status="edited", corrected_text="fixed text"))
    db.session.add(Annotation(user_id=u1.id, line_id=line2.id, status="validated"))
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(u1.id)
        sess["_fresh"] = True

    resp = client.get("/export/csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"

    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    header = rows[0]
    assert header[:4] == ["filename", "book_id", "line_id", "original_text"]
    assert "action_of_annotation_1" in header
    assert "text_of_annotation_1" in header
    assert "annotator_1" in header
    # Two annotators appear on line1, so there should be 2 annotation slots.
    assert header.count("annotator_1") == 1
    assert any(h == "annotator_2" for h in header)

    data_rows = {row[2]: row for row in rows[1:]}  # keyed by line_id
    row1 = data_rows[str(line1.id)]
    assert row1[0] == "page-0001.xml"
    assert row1[1] == "export_book_one"
    assert row1[3] == "original ocr text"

    # annA validated -> text should be the original ocr text
    # annB edited -> text should be corrected text
    values = row1[4:]
    triples = [tuple(values[i:i + 3]) for i in range(0, len(values), 3)]
    by_annotator = {t[2]: t for t in triples if t[2]}
    assert by_annotator["annA"] == ("validated", "original ocr text", "annA")
    assert by_annotator["annB"] == ("edited", "fixed text", "annB")

    row2 = data_rows[str(line2.id)]
    values2 = row2[4:]
    triples2 = [tuple(values2[i:i + 3]) for i in range(0, len(values2), 3)]
    non_empty = [t for t in triples2 if t[2]]
    assert len(non_empty) == 1
    assert non_empty[0] == ("validated", "original ocr text", "annA")
