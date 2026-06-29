from collections import defaultdict
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from .. import db
from ..models import User, Line, Annotation
from ..text_utils import normalize

bp = Blueprint("stats", __name__)

VALIDATED_STATUSES = ("validated", "edited")


@bp.route("/stats")
@login_required
def index():
    total_lines = Line.query.count()

    validated_ids = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .distinct()
        .subquery()
    )
    total_validated = db.session.query(func.count()).select_from(validated_ids).scalar()
    total_skipped_only = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status == "skipped")
        .filter(Annotation.line_id.notin_(
            db.session.query(Annotation.line_id)
            .filter(Annotation.status.in_(VALIDATED_STATUSES))
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

    user_stats = {}
    for row in per_user:
        u = user_stats.setdefault(row.username, {})
        u[row.status] = {
            "cnt": row.cnt,
            "avg_elapsed": round(row.avg_elapsed, 1) if row.avg_elapsed else None,
        }

    # ── Inter-annotator agreement ────────────────────────────────
    # Fetch every terminal annotation (validated/edited), keep only the most
    # recent one per (user, line) in case of duplicates.
    terminal = (
        db.session.query(
            Annotation.line_id,
            User.username,
            Annotation.status,
            Annotation.corrected_text,
            func.max(Annotation.id).label("last_id"),
        )
        .join(User, Annotation.user_id == User.id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .group_by(Annotation.line_id, User.username)
        .all()
    )

    # line_id → {username: (status, corrected_text)}
    by_line = defaultdict(dict)
    for row in terminal:
        by_line[row.line_id][row.username] = (row.status, row.corrected_text)

    # Collect all annotator usernames that appear in terminal annotations
    annotators = sorted({u for anns in by_line.values() for u in anns})

    # Pairwise agreement counts: matrix[u1][u2] = {agree_validate, agree_edited, disagree, total}
    matrix = {u1: {u2: {"agree_validate": 0, "agree_edited": 0, "disagree": 0, "total": 0}
                   for u2 in annotators}
              for u1 in annotators}

    for line_anns in by_line.values():
        print(line_anns)
        users_here = [u for u in annotators if u in line_anns]
        for i, u1 in enumerate(users_here):
            for u2 in users_here[i+1:]:
                s1, t1 = line_anns[u1]
                s2, t2 = line_anns[u2]
                cell1 = matrix[u1][u2]
                cell2 = matrix[u2][u1]
                for cell in (cell1, cell2):
                    cell["total"] += 1
                    if s1 == "validated" and s2 == "validated":
                        cell["agree_validate"] += 1
                    elif s1 == "edited" and s2 == "edited" and normalize(t1) == normalize(t2):
                        cell["agree_edited"] += 1
                    else:
                        cell["disagree"] += 1

    return render_template(
        "stats.html",
        total_lines=total_lines,
        total_validated=total_validated,
        total_skipped_only=total_skipped_only,
        total_untouched=total_untouched,
        user_stats=user_stats,
        annotators=annotators,
        iaa_matrix=matrix,
    )
