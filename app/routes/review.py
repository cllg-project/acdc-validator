from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import exists as sa_exists
from .. import db
from ..models import Line, Annotation

bp = Blueprint("review", __name__)

VALIDATED_STATUSES = ("validated", "edited")

# Statuses that permanently retire a line for the current user
DONE_FOR_USER_STATUSES = ("validated", "edited", "rejected")


MAX_ANNOTATIONS = 2


def _next_line(user_id):
    """Return the next Line that:
    - the current user skipped or flagged for editing in Step 1, AND
    - has not been globally saturated, AND
    - the user has not already resolved in Step 2.
    """
    from sqlalchemy import func
    saturated = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .group_by(Annotation.line_id)
        .having(func.count(Annotation.id) >= MAX_ANNOTATIONS)
        .subquery()
    )
    user_flagged = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.user_id == user_id)
        .filter(Annotation.status.in_(("skip_edited", "skipped")))
        .subquery()
    )
    user_done = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.user_id == user_id)
        .filter(Annotation.status.in_(DONE_FOR_USER_STATUSES))
        .subquery()
    )
    return (
        Line.query
        .filter(sa_exists().where(user_flagged.c.line_id == Line.id))
        .filter(~sa_exists().where(saturated.c.line_id == Line.id))
        .filter(~sa_exists().where(user_done.c.line_id == Line.id))
        .order_by(db.func.random())
        .first()
    )


@bp.route("/review")
@login_required
def index():
    line = _next_line(current_user.id)
    if line is None:
        flash("Nothing left to review — great work!")
        return render_template("done.html", step="review")
    # Pre-fill with the most recent saved correction for this line (any user)
    last = (
        Annotation.query
        .filter_by(line_id=line.id)
        .filter(Annotation.corrected_text.isnot(None))
        .order_by(Annotation.id.desc())
        .first()
    )
    prefill = line.ocr_text
    total_lines = Line.query.filter_by(book_id=line.book_id).count()
    return render_template("review.html", line=line, prefill=prefill, from_validate="0", total_lines=total_lines)


@bp.route("/review/<int:line_id>", methods=["GET"])
@login_required
def specific(line_id):
    line = Line.query.get_or_404(line_id)
    last = (
        Annotation.query
        .filter_by(line_id=line.id)
        .filter(Annotation.corrected_text.isnot(None))
        .order_by(Annotation.id.desc())
        .first()
    )
    prefill = line.ocr_text
    from_validate = request.args.get("from_validate", "0")
    total_lines = Line.query.filter_by(book_id=line.book_id).count()
    return render_template("review.html", line=line, prefill=prefill, from_validate=from_validate, total_lines=total_lines)


@bp.route("/review/<int:line_id>", methods=["POST"])
@login_required
def submit(line_id):
    line = Line.query.get_or_404(line_id)
    action = request.form.get("action")  # edited | validated | skipped | rejected
    if action not in ("edited", "validated", "skipped", "rejected"):
        flash("Invalid action.")
        return redirect(url_for("review.index"))

    text = request.form.get("text", "").strip()

    # What gets saved per action:
    #   edited    → corrected_text = new text (user changed something)
    #   validated → corrected_text = None (OCR was fine as-is)
    #   skipped   → corrected_text = text as left (partial work saved, line returns later)
    #   rejected  → corrected_text = None (user dismisses line permanently for themselves)
    if action == "edited":
        corrected = text or None
    elif action == "skipped":
        corrected = text if text != request.form.get("original_text", "") else None
    else:
        corrected = None

    elapsed = _parse_elapsed(request.form.get("elapsed_seconds"))
    ann = Annotation(
        user_id=current_user.id,
        line_id=line.id,
        status=action,
        corrected_text=corrected,
        finished_at=datetime.now(timezone.utc),
        elapsed_seconds=elapsed,
    )
    db.session.add(ann)
    db.session.commit()
    if request.form.get("from_validate") == "1":
        return redirect(url_for("validate.index"))
    return redirect(url_for("review.index"))


def _parse_elapsed(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
