from collections import defaultdict
from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from .. import db
from ..models import User, Line, Annotation
from ..text_utils import normalize

bp = Blueprint("disagreements", __name__)

TERMINAL = ("validated", "edited")
PER_PAGE = 20


@bp.route("/disagreements")
@login_required
def index():
    page = request.args.get("page", 1, type=int)

    # Most recent terminal annotation per (line, user)
    terminal = (
        db.session.query(
            Annotation.line_id,
            User.username,
            Annotation.status,
            Annotation.corrected_text,
        )
        .join(User, Annotation.user_id == User.id)
        .filter(Annotation.status.in_(TERMINAL))
        .filter(
            Annotation.id.in_(
                db.session.query(func.max(Annotation.id))
                .filter(Annotation.status.in_(TERMINAL))
                .group_by(Annotation.line_id, Annotation.user_id)
            )
        )
        .all()
    )

    # line_id → {username: (status, corrected_text)}
    by_line: dict[int, dict] = defaultdict(dict)
    for row in terminal:
        by_line[row.line_id][row.username] = (row.status, row.corrected_text)

    # Keep only lines with 2+ annotators that disagree
    disagreement_ids = []
    for line_id, anns in by_line.items():
        users = list(anns)
        if len(users) < 2:
            continue
        disagrees = False
        for i, u1 in enumerate(users):
            for u2 in users[i + 1:]:
                s1, t1 = anns[u1]
                s2, t2 = anns[u2]
                agree = (
                    (s1 == "validated" and s2 == "validated")
                    or (s1 == "edited" and s2 == "edited" and normalize(t1) == normalize(t2))
                )
                if not agree:
                    disagrees = True
                    break
            if disagrees:
                break
        if disagrees:
            disagreement_ids.append(line_id)

    total = len(disagreement_ids)
    start = (page - 1) * PER_PAGE
    page_ids = disagreement_ids[start: start + PER_PAGE]

    lines = {l.id: l for l in Line.query.filter(Line.id.in_(page_ids)).all()}

    rows = []
    for line_id in page_ids:
        line = lines.get(line_id)
        if line:
            rows.append((line, by_line[line_id]))

    rows.sort(key=lambda r: (r[0].book_id, r[0].line_index))

    pages = (total + PER_PAGE - 1) // PER_PAGE

    return render_template(
        "disagreements.html",
        rows=rows,
        page=page,
        pages=pages,
        total=total,
        has_prev=page > 1,
        has_next=page < pages,
    )
