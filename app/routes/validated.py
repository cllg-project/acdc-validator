from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from .. import db
from ..models import Line, Annotation, User

bp = Blueprint("validated", __name__)

VALIDATED_STATUSES = ("validated", "edited")
PER_PAGE = 50


@bp.route("/validated")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    book_filter = request.args.get("book", "").strip()
    status_filter = request.args.get("status", "").strip()
    user_filter = request.args.get("user", "").strip()

    # Most-recent validated/edited annotation per line
    best_sq = (
        db.session.query(
            Annotation.line_id,
            func.max(Annotation.id).label("ann_id"),
        )
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .group_by(Annotation.line_id)
        .subquery()
    )

    query = (
        db.session.query(Line, Annotation, User.username)
        .join(best_sq, Line.id == best_sq.c.line_id)
        .join(Annotation, Annotation.id == best_sq.c.ann_id)
        .join(User, User.id == Annotation.user_id)
    )

    if book_filter:
        query = query.filter(Line.book_id.contains(book_filter))
    if status_filter in VALIDATED_STATUSES:
        query = query.filter(Annotation.status == status_filter)
    if user_filter:
        query = query.filter(User.username == user_filter)

    query = query.order_by(Line.book_id, Line.line_index)

    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    book_ids = [
        r[0]
        for r in db.session.query(Line.book_id).distinct().order_by(Line.book_id).all()
    ]
    usernames = [
        r[0]
        for r in db.session.query(User.username).join(Annotation).distinct().order_by(User.username).all()
    ]

    return render_template(
        "validated.html",
        pagination=pagination,
        rows=pagination.items,
        book_filter=book_filter,
        status_filter=status_filter,
        user_filter=user_filter,
        book_ids=book_ids,
        usernames=usernames,
    )
