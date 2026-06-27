from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from .. import db
from ..models import User, Line, Annotation

bp = Blueprint("stats", __name__)


@bp.route("/stats")
@login_required
def index():
    total_lines = Line.query.count()

    # Lines with at least one validated/edited annotation (done)
    validated_ids = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(("validated", "edited")))
        .distinct()
        .subquery()
    )
    total_validated = db.session.query(func.count()).select_from(validated_ids).scalar()
    total_skipped_only = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status == "skipped")
        .filter(Annotation.line_id.notin_(
            db.session.query(Annotation.line_id)
            .filter(Annotation.status.in_(("validated", "edited")))
        ))
        .distinct()
        .count()
    )
    total_untouched = total_lines - total_validated - total_skipped_only

    # Per-user stats
    per_user = (
        db.session.query(
            User.username,
            Annotation.status,
            func.count(Annotation.id).label("cnt"),
            func.avg(Annotation.elapsed_seconds).label("avg_elapsed"),
        )
        .join(User, Annotation.user_id == User.id)
        .group_by(User.username, Annotation.status)
        .order_by(User.username, Annotation.status)
        .all()
    )

    # Reshape into {username: {status: {cnt, avg_elapsed}}}
    user_stats = {}
    for row in per_user:
        u = user_stats.setdefault(row.username, {})
        u[row.status] = {
            "cnt": row.cnt,
            "avg_elapsed": round(row.avg_elapsed, 1) if row.avg_elapsed else None,
        }

    return render_template(
        "stats.html",
        total_lines=total_lines,
        total_validated=total_validated,
        total_skipped_only=total_skipped_only,
        total_untouched=total_untouched,
        user_stats=user_stats,
    )
