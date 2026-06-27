import io
import os
from flask import Blueprint, current_app, send_file, abort
from flask_login import login_required
from PIL import Image, ImageDraw
from ..models import Line
from .. import db

bp = Blueprint("image", __name__)

# Horizontal padding: small (just a breath of margin)
H_PADDING = 20
# Vertical context: show this many line-heights above and below the polygon
V_CONTEXT_FACTOR = 2.5
GREY_FILL = (200, 200, 200)
GREY_ALPHA = 180  # 0=transparent, 255=opaque — semi-transparent so text is still legible


@bp.route("/image/<int:line_id>")
@login_required
def line_image(line_id):
    line = Line.query.get_or_404(line_id)
    data_path = current_app.config["DATA_PATH"]
    jpg_path = os.path.join(data_path, line.page_jpg)

    if not os.path.exists(jpg_path):
        abort(404)

    with Image.open(jpg_path) as img:
        img_w, img_h = img.size

        v_pad = int(line.height * V_CONTEXT_FACTOR)
        x0 = max(0, line.hpos - H_PADDING)
        y0 = max(0, line.vpos - v_pad)
        x1 = min(img_w, line.hpos + line.width + H_PADDING)
        y1 = min(img_h, line.vpos + line.height + v_pad)

        crop = img.crop((x0, y0, x1, y1)).convert("RGB")

    # Build polygon in crop-relative coordinates
    raw_points = line.polygon_points.strip()
    if raw_points:
        coords = list(map(int, raw_points.split()))
        poly = [(coords[i] - x0, coords[i + 1] - y0) for i in range(0, len(coords), 2)]

        crop_w, crop_h = crop.size

        # Semi-transparent grey dimming outside the polygon
        dim = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dim)
        # Fill everything grey, then cut out the polygon as fully transparent
        draw.rectangle([0, 0, crop_w, crop_h], fill=(*GREY_FILL, GREY_ALPHA))
        draw.polygon(poly, fill=(0, 0, 0, 0))

        base = crop.convert("RGBA")
        result = Image.alpha_composite(base, dim).convert("RGB")
    else:
        result = crop

    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg")


@bp.route("/image/example")
@login_required
def example_image():
    """Return a random line image for use on the homepage."""
    line = Line.query.order_by(db.func.random()).first()
    if line is None:
        abort(404)
    return line_image(line.id)
