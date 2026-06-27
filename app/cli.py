import os
import csv
import click
from xml.etree import ElementTree as ET
from PIL import Image as PILImage
from flask import current_app
from . import db
from .models import User, Line, Annotation


def register(app):
    app.cli.add_command(init_cmd)
    app.cli.add_command(user_cmd)
    app.cli.add_command(export_cmd)


@click.command("init")
@click.option("--data-path", default=None, help="Path to book-samples folder")
def init_cmd(data_path):
    """Initialise the database and convert PNGs to JPGs."""
    data_path = data_path or current_app.config["DATA_PATH"]
    db.create_all()
    click.echo(f"DB tables created. Reading data from: {data_path}")

    manifest_path = os.path.join(data_path, "manifest.csv")
    if not os.path.exists(manifest_path):
        click.echo(f"manifest.csv not found at {manifest_path}", err=True)
        return

    ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_lines = 0
    skipped = 0

    for row in rows:
        book_id = row["book_id"]
        png_rel = row["png"]
        xml_rel = row["alto_xml"]

        png_abs = os.path.join(data_path, png_rel)
        xml_abs = os.path.join(data_path, xml_rel)
        jpg_rel = os.path.splitext(png_rel)[0] + ".jpg"
        jpg_abs = os.path.join(data_path, jpg_rel)

        # Convert PNG → JPG once
        if not os.path.exists(jpg_abs):
            try:
                with PILImage.open(png_abs) as img:
                    img.convert("RGB").save(jpg_abs, "JPEG", quality=85)
            except Exception as e:
                click.echo(f"  [WARN] Could not convert {png_rel}: {e}")
                continue

        if not os.path.exists(xml_abs):
            click.echo(f"  [WARN] XML not found: {xml_rel}")
            continue

        try:
            tree = ET.parse(xml_abs)
        except ET.ParseError as e:
            click.echo(f"  [WARN] XML parse error {xml_rel}: {e}")
            continue

        root = tree.getroot()
        text_lines = root.findall(f".//{{{ALTO_NS}}}TextLine")

        for idx, tl in enumerate(text_lines):
            string_el = tl.find(f"{{{ALTO_NS}}}String")
            if string_el is None:
                continue
            ocr_text = string_el.get("CONTENT", "").strip()
            if not ocr_text:
                continue

            polygon_el = tl.find(f".//{{{ALTO_NS}}}Polygon")
            points = polygon_el.get("POINTS", "") if polygon_el is not None else ""

            # Use the String element bbox (most precise)
            hpos = int(string_el.get("HPOS", tl.get("HPOS", 0)))
            vpos = int(string_el.get("VPOS", tl.get("VPOS", 0)))
            width = int(string_el.get("WIDTH", tl.get("WIDTH", 0)))
            height = int(string_el.get("HEIGHT", tl.get("HEIGHT", 0)))

            existing = Line.query.filter_by(book_id=book_id, line_index=idx).first()
            if existing:
                skipped += 1
                continue

            line = Line(
                book_id=book_id,
                page_png=png_rel,
                page_jpg=jpg_rel,
                alto_xml=xml_rel,
                line_index=idx,
                hpos=hpos,
                vpos=vpos,
                width=width,
                height=height,
                polygon_points=points,
                ocr_text=ocr_text,
            )
            db.session.add(line)
            total_lines += 1

        db.session.commit()
        click.echo(f"  {book_id}: {len(text_lines)} lines")

    click.echo(f"\nDone. {total_lines} lines inserted, {skipped} already existed.")


@click.group("user")
def user_cmd():
    """Manage user accounts."""


@user_cmd.command("add")
@click.argument("username")
@click.password_option(prompt="Password", confirmation_prompt=True)
def user_add(username, password):
    """Create a new user."""
    db.create_all()
    if User.query.filter_by(username=username).first():
        click.echo(f"User '{username}' already exists.", err=True)
        return
    u = User(username=username)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.echo(f"User '{username}' created.")


@user_cmd.command("edit")
@click.argument("username")
@click.password_option(prompt="New password", confirmation_prompt=True)
def user_edit(username, password):
    """Change an existing user's password."""
    u = User.query.filter_by(username=username).first()
    if not u:
        click.echo(f"User '{username}' not found.", err=True)
        return
    u.set_password(password)
    db.session.commit()
    click.echo(f"Password updated for '{username}'.")


ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
VALIDATED_STATUSES = ("validated", "edited")


@click.command("export")
@click.option("--data-path", default=None, help="Path to book-samples folder")
def export_cmd(data_path):
    """Write .post-cllg.xml ALTO files with unvalidated lines removed."""
    data_path = data_path or current_app.config["DATA_PATH"]

    # Build lookup: xml_rel → {line_index: best_annotation}
    # "best" = any validated/edited annotation wins over skipped/none
    # Only load lines that have at least one validated/edited annotation
    validated_line_ids = (
        db.session.query(Annotation.line_id)
        .filter(Annotation.status.in_(VALIDATED_STATUSES))
        .distinct()
        .subquery()
    )
    lines = Line.query.filter(Line.id.in_(validated_line_ids)).all()

    page_map = {}  # xml_rel → {line_index: Line}
    for line in lines:
        page_map.setdefault(line.alto_xml, {})[line.line_index] = line

    written = skipped_pages = 0

    for xml_rel, line_by_idx in page_map.items():
        xml_abs = os.path.join(data_path, xml_rel)
        if not os.path.exists(xml_abs):
            click.echo(f"  [WARN] Missing XML: {xml_rel}")
            skipped_pages += 1
            continue

        # Best validated/edited annotation per line on this page
        validated = {}   # line_index → corrected_text or None
        for idx, line in line_by_idx.items():
            ann = (
                Annotation.query
                .filter_by(line_id=line.id)
                .filter(Annotation.status.in_(VALIDATED_STATUSES))
                .order_by(Annotation.id.desc())
                .first()
            )
            if ann:
                validated[idx] = ann.corrected_text  # None means keep original OCR text

        ET.register_namespace("", ALTO_NS)
        tree = ET.parse(xml_abs)
        root = tree.getroot()

        all_tl = root.findall(f".//{{{ALTO_NS}}}TextLine")
        kept = 0
        for block in root.findall(f".//{{{ALTO_NS}}}TextBlock"):
            for tl in list(block.findall(f"{{{ALTO_NS}}}TextLine")):
                idx = all_tl.index(tl)
                if idx not in validated:
                    block.remove(tl)
                else:
                    corrected = validated[idx]
                    if corrected is not None:
                        string_el = tl.find(f"{{{ALTO_NS}}}String")
                        if string_el is not None:
                            string_el.set("CONTENT", corrected)
                    kept += 1

        out_path = xml_abs.replace(".xml", ".post-cllg.xml")
        ET.indent(root, space="  ")
        tree.write(out_path, encoding="UTF-8", xml_declaration=True)
        click.echo(f"  {xml_rel}: {kept} lines → {os.path.basename(out_path)}")
        written += 1

    click.echo(f"\nDone. {written} files exported, {skipped_pages} skipped.")
