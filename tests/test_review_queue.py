"""Tests for the Step 2 (review) queue logic in app.routes.review._next_line.

Key rules under test:
- skipped in Step 1     → appears in Step 2
- skip_edited in Step 1 → appears in Step 2
- validated in Step 1   → does NOT appear in Step 2
- rejected in Step 1    → does NOT appear in Step 2
- skipped in Step 2     → cycles back (not permanently retired)
- validated/edited/rejected in Step 2 → permanently retired
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.models import User, Line, Annotation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_line_counter = 0


def make_line(db, suffix=""):
    global _line_counter
    _line_counter += 1
    line = Line(
        book_id=f"test_book_{suffix or _line_counter}",
        page_png="p.png",
        page_jpg="p.jpg",
        alto_xml="a.xml",
        line_index=0,
        hpos=0, vpos=0, width=100, height=20,
        polygon_points="",
        ocr_text="test",
    )
    db.session.add(line)
    db.session.flush()
    return line


def make_user(db, name):
    user = User(username=name, password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def annotate(db, user, line, status):
    ann = Annotation(user_id=user.id, line_id=line.id, status=status)
    db.session.add(ann)
    db.session.flush()
    return ann


def next_line(app, user_id):
    from app.routes.review import _next_line
    with app.app_context():
        return _next_line(user_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_skipped_in_step1_appears_in_step2(app, db):
    user = make_user(db, "u_skip")
    line = make_line(db, "skip")
    annotate(db, user, line, "skipped")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == line.id


def test_skip_edited_in_step1_appears_in_step2(app, db):
    user = make_user(db, "u_skip_edited")
    line = make_line(db, "skip_edited")
    annotate(db, user, line, "skip_edited")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == line.id


def test_validated_in_step1_not_in_step2(app, db):
    user = make_user(db, "u_validated")
    line = make_line(db, "validated")
    annotate(db, user, line, "validated")
    db.session.commit()

    assert next_line(app, user.id) is None


def test_rejected_in_step1_not_in_step2(app, db):
    user = make_user(db, "u_rejected")
    line = make_line(db, "rejected")
    annotate(db, user, line, "rejected")
    db.session.commit()

    assert next_line(app, user.id) is None


def test_skipped_in_step2_cycles_back(app, db):
    """A line skip_edited in step 1 then skipped in step 2 should return."""
    user = make_user(db, "u_step2_skip")
    line = make_line(db, "step2_skip")
    annotate(db, user, line, "skip_edited")
    annotate(db, user, line, "skipped")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == line.id


def test_edited_in_step2_retires_line(app, db):
    user = make_user(db, "u_step2_edited")
    line = make_line(db, "step2_edited")
    annotate(db, user, line, "skip_edited")
    annotate(db, user, line, "edited")
    db.session.commit()

    assert next_line(app, user.id) is None


def test_validated_in_step2_retires_line(app, db):
    user = make_user(db, "u_step2_validated")
    line = make_line(db, "step2_validated")
    annotate(db, user, line, "skipped")
    annotate(db, user, line, "validated")
    db.session.commit()

    assert next_line(app, user.id) is None


def test_other_users_skip_does_not_affect_queue(app, db):
    """Another user skipping a line must not put it in the current user's queue."""
    owner = make_user(db, "u_owner")
    other = make_user(db, "u_other")
    line = make_line(db, "other_skip")
    annotate(db, other, line, "skipped")
    db.session.commit()

    assert next_line(app, owner.id) is None


def test_globally_saturated_line_excluded(app, db):
    """A line with MAX_ANNOTATIONS validated annotations should not appear."""
    from app.routes.review import MAX_ANNOTATIONS
    user = make_user(db, "u_saturated_main")
    line = make_line(db, "saturated")
    annotate(db, user, line, "skipped")

    for i in range(MAX_ANNOTATIONS):
        other = make_user(db, f"u_saturated_other_{i}")
        annotate(db, other, line, "validated")

    db.session.commit()
    assert next_line(app, user.id) is None
