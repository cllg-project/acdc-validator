from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import exists
from .. import db
from ..models import Line, Annotation

bp = Blueprint("validate", __name__)

VALIDATED_STATUSES = ("validated", "edited")
MAX_ANNOTATIONS = 2


def _next_line(user_id):
    """Return the next Line that:
    - has fewer than MAX_ANNOTATIONS validated/edited annotations across all users, and
    - has not been touched at all by this user (any annotation).
    """
    from sqlalchemy import func
    # Lines that have reached the annotation cap (MAX_ANNOTATIONS distinct validated users)
    saturated = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .group_by(Annotation.line_id)
        .having(func.count(Annotation.id) >= MAX_ANNOTATIONS)
        .subquery()
    )
    user_seen = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.user_id == user_id)
        .subquery()
    )
    return (
        Line.query
        .filter(~exists().where(saturated.c.line_id == Line.id))
        .filter(~exists().where(user_seen.c.line_id == Line.id))
        .order_by(db.func.random())
        .first()
    )


@bp.route("/validate")
@login_required
def index():
    line = _next_line(current_user.id)
    if line is None:
        flash("All lines validated — nothing left in the queue!")
        return render_template("done.html", step="validate")
    return render_template("validate.html", line=line)


@bp.route("/validate/<int:line_id>", methods=["POST"])
@login_required
def submit(line_id):
    line = Line.query.get_or_404(line_id)
    action = request.form.get("action")  # validated | skipped | skip_edited | abstained
    if action not in ("validated", "skipped", "skip_edited", "abstained"):
        flash("Invalid action.")
        return redirect(url_for("validate.index"))

    elapsed = _parse_elapsed(request.form.get("elapsed_seconds"))
    ann = Annotation(
        user_id=current_user.id,
        line_id=line.id,
        status=action,
        finished_at=datetime.now(timezone.utc),
        elapsed_seconds=elapsed,
    )
    db.session.add(ann)
    db.session.commit()
    if action == "skip_edited":
        return redirect(url_for("review.specific", line_id=line.id))
    return redirect(url_for("validate.index"))


def _parse_elapsed(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
