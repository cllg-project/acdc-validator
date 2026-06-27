from flask import Blueprint, render_template
from flask_login import login_required
from ..models import Line, Annotation
from .. import db
from sqlalchemy import func

bp = Blueprint("home", __name__)

VALIDATED_STATUSES = ("validated", "edited")
MAX_ANNOTATIONS = 2


@bp.route("/home")
@login_required
def index():
    total = Line.query.count()
    done = (
        db.session.query(func.count(func.distinct(Annotation.line_id)))
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .scalar() or 0
    )
    # Lines that have reached the cap
    saturated = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .group_by(Annotation.line_id)
        .having(func.count(Annotation.id) >= MAX_ANNOTATIONS)
        .count()
    )
    return render_template("home.html", total=total, done=done, saturated=saturated)
