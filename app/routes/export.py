import csv
import io
import os
from collections import defaultdict

from flask import Blueprint, Response
from flask_login import login_required
from sqlalchemy import func

from .. import db
from ..models import User, Line, Annotation

bp = Blueprint("export", __name__)

VALIDATED_STATUSES = ("validated", "edited")


@bp.route("/export/csv")
@login_required
def csv_export():
    # Most recent terminal (validated/edited) annotation per (line, user)
    terminal = (
        db.session.query(
            Annotation.line_id,
            User.username,
            Annotation.status,
            Annotation.corrected_text,
        )
        .join(User, Annotation.user_id == User.id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .filter(
            Annotation.id.in_(
                db.session.query(func.max(Annotation.id))
                .filter(Annotation.status.in_(VALIDATED_STATUSES))
                .group_by(Annotation.line_id, Annotation.user_id)
            )
        )
        .all()
    )

    by_line = defaultdict(dict)  # line_id -> {username: (status, corrected_text)}
    for row in terminal:
        by_line[row.line_id][row.username] = (row.status, row.corrected_text)

    lines = (
        Line.query.filter(Line.id.in_(by_line.keys()))
        .order_by(Line.book_id, Line.line_index)
        .all()
    )

    max_annotators = max((len(anns) for anns in by_line.values()), default=0)

    header = ["filename", "book_id", "line_id", "original_text"]
    for i in range(1, max_annotators + 1):
        header += [f"action_of_annotation_{i}", f"text_of_annotation_{i}", f"annotator_{i}"]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)

    for line in lines:
        anns = by_line[line.id]
        row = [
            os.path.basename(line.alto_xml),
            line.book_id,
            line.id,
            line.ocr_text,
        ]
        for username in sorted(anns):
            status, corrected_text = anns[username]
            text = corrected_text if status == "edited" else line.ocr_text
            row += [status, text, username]
        row += [""] * (3 * max_annotators - (len(row) - 4))
        writer.writerow(row)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=annotations_export.csv"},
    )
