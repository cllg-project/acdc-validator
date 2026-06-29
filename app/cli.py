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
    app.cli.add_command(deduplicate_cmd)
    app.cli.add_command(cap_cmd)
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

        seen_positions: set[tuple[int, int]] = set()
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

            pos_key = (hpos, vpos)
            if pos_key in seen_positions:
                skipped += 1
                continue
            seen_positions.add(pos_key)

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


@click.command("deduplicate")
def deduplicate_cmd():
    """Remove duplicate Line rows (same hpos/vpos within a book) and migrate their annotations."""
    from collections import defaultdict
    from sqlalchemy import text as sa_text

    TERMINAL = {"validated", "edited"}

    def ann_priority(ann):
        return (1 if ann.status in TERMINAL else 0, ann.id)

    rows = db.session.execute(sa_text("""
        SELECT l.id AS dup_id, c.keep_id
        FROM line l
        JOIN (
            SELECT book_id, hpos, vpos, MIN(id) AS keep_id
            FROM line
            GROUP BY book_id, hpos, vpos
            HAVING COUNT(*) > 1
        ) c ON l.book_id = c.book_id AND l.hpos = c.hpos AND l.vpos = c.vpos
        WHERE l.id != c.keep_id
    """)).fetchall()

    if not rows:
        click.echo("No duplicate lines found.")
        return

    # Group all duplicate ids by their canonical id so we handle cascading correctly.
    canonical_to_dups: dict[int, list[int]] = defaultdict(list)
    for dup_id, keep_id in rows:
        canonical_to_dups[keep_id].append(dup_id)

    click.echo(f"Found {sum(len(v) for v in canonical_to_dups.values())} duplicate line rows across {len(canonical_to_dups)} canonical lines.")
    moved = replaced = dropped = deleted = 0

    for keep_id, dup_ids in canonical_to_dups.items():
        # Gather all annotations from ALL duplicates, grouped by user.
        dup_anns = Annotation.query.filter(Annotation.line_id.in_(dup_ids)).all()
        by_user: dict[int, list] = defaultdict(list)
        for ann in dup_anns:
            by_user[ann.user_id].append(ann)

        for user_id, user_anns in by_user.items():
            best_dup = max(user_anns, key=ann_priority)
            for ann in user_anns:
                if ann.id != best_dup.id:
                    db.session.delete(ann)
                    dropped += 1

            canonical_ann = Annotation.query.filter_by(line_id=keep_id, user_id=user_id).first()
            if canonical_ann:
                if ann_priority(best_dup) > ann_priority(canonical_ann):
                    # Dup annotation is better — promote it onto the canonical row.
                    canonical_ann.status = best_dup.status
                    canonical_ann.corrected_text = best_dup.corrected_text
                    canonical_ann.started_at = best_dup.started_at
                    canonical_ann.finished_at = best_dup.finished_at
                    canonical_ann.elapsed_seconds = best_dup.elapsed_seconds
                    replaced += 1
                else:
                    dropped += 1
                db.session.delete(best_dup)
            else:
                best_dup.line_id = keep_id
                moved += 1

        for dup_id in dup_ids:
            dup_line = db.session.get(Line, dup_id)
            if dup_line:
                db.session.delete(dup_line)
                deleted += 1

    db.session.commit()
    click.echo(
        f"Done. {deleted} duplicate lines removed, "
        f"{moved} annotations moved, {replaced} annotations upgraded, "
        f"{dropped} redundant annotations dropped."
    )


@click.command("cap")
@click.option("--max-lines", default=5, show_default=True, help="Max lines to keep per book.")
def cap_cmd(max_lines):
    """Cap each book to --max-lines lines, always preserving annotated lines."""
    annotated_ids = {
        row[0] for row in db.session.query(Annotation.line_id).distinct()
    }
    book_ids = [r[0] for r in db.session.query(Line.book_id).distinct()]

    deleted = 0
    for book_id in book_ids:
        lines = Line.query.filter_by(book_id=book_id).order_by(Line.line_index).all()
        if len(lines) <= max_lines:
            continue
        annotated = [l for l in lines if l.id in annotated_ids]
        unannotated = [l for l in lines if l.id not in annotated_ids]
        slots = max(0, max_lines - len(annotated))
        for line in unannotated[slots:]:
            db.session.delete(line)
            deleted += 1

    db.session.commit()
    click.echo(f"Done. {deleted} lines removed (cap={max_lines}).")


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
