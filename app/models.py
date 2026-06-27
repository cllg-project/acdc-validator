from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    annotations = db.relationship("Annotation", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Line(db.Model):
    __tablename__ = "line"
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(128), nullable=False)
    page_png = db.Column(db.String(512), nullable=False)  # relative to DATA_PATH
    page_jpg = db.Column(db.String(512), nullable=False)  # relative to DATA_PATH
    alto_xml = db.Column(db.String(512), nullable=False)  # relative to DATA_PATH
    line_index = db.Column(db.Integer, nullable=False)
    hpos = db.Column(db.Integer, nullable=False)
    vpos = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    polygon_points = db.Column(db.Text, nullable=False)  # "x1,y1 x2,y2 ..."
    ocr_text = db.Column(db.Text, nullable=False)
    annotations = db.relationship("Annotation", backref="line", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("book_id", "line_index", name="uq_book_line"),
    )


class Annotation(db.Model):
    __tablename__ = "annotation"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    line_id = db.Column(db.Integer, db.ForeignKey("line.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False)  # validated / edited / skipped
    corrected_text = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    elapsed_seconds = db.Column(db.Float, nullable=True)
