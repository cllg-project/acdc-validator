"""Tests for the Step 1 (validate) queue logic in app.routes.validate._next_line.

Key rule under test — priority order:
1. Lines with one validated/edited annotation from another user (just need
   a confirming second pass).
2. Lines another user skipped/rejected/abstained on ("needs a real second
   annotation").
3. Lines nobody has touched yet.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.models import User, Line, Annotation

from tests.test_review_queue import make_line, make_user, annotate


@pytest.fixture(autouse=True)
def clean_slate(app, db):
    """validate._next_line's priority looks at ALL lines/annotations (not
    just ones tied to the current user), so leftover rows from earlier
    tests would skew priority ordering. Start each test from an empty table.
    """
    with app.app_context():
        Annotation.query.delete()
        Line.query.delete()
        User.query.delete()
        db.session.commit()


def next_line(app, user_id):
    from app.routes.validate import _next_line
    with app.app_context():
        return _next_line(user_id)


def test_partially_validated_prioritized_over_needs_second(app, db):
    user = make_user(db, "u_priority")
    other1 = make_user(db, "u_other1")
    other2 = make_user(db, "u_other2")

    partially_validated = make_line(db, "partial")
    annotate(db, other1, partially_validated, "validated")

    needs_second = make_line(db, "needs_second")
    annotate(db, other2, needs_second, "rejected")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == partially_validated.id


def test_partially_validated_prioritized_over_untouched(app, db):
    user = make_user(db, "u_priority2")
    other = make_user(db, "u_other3")

    partially_validated = make_line(db, "partial2")
    annotate(db, other, partially_validated, "edited")

    make_line(db, "untouched")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == partially_validated.id


def test_needs_second_prioritized_over_untouched(app, db):
    user = make_user(db, "u_priority3")
    other = make_user(db, "u_other4")

    needs_second = make_line(db, "needs_second2")
    annotate(db, other, needs_second, "skipped")

    make_line(db, "untouched2")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == needs_second.id


def test_abstained_counts_as_needs_second(app, db):
    user = make_user(db, "u_priority4")
    other = make_user(db, "u_other5")

    needs_second = make_line(db, "needs_second3")
    annotate(db, other, needs_second, "abstained")

    make_line(db, "untouched3")
    db.session.commit()

    result = next_line(app, user.id)
    assert result is not None
    assert result.id == needs_second.id
