#!/usr/bin/env python3
"""
Migration: add left/right padding to polygon_points stored in the line table.

For each polygon, points whose x <= horizontal midpoint are shifted left by
PADDING pixels; points to the right of the midpoint are shifted right by
PADDING pixels. The left edge is clamped to 0.

Usage:
    env/bin/python scripts/migrate_polygon_padding.py [--padding 5] [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BATCH_SIZE = 500


def pad_polygon_lr(points_str: str, padding: int = 5) -> str:
    """Expand a polygon ~padding pixels left and right."""
    coords = list(map(int, points_str.split()))
    if len(coords) < 4 or len(coords) % 2 != 0:
        return points_str  # malformed — leave untouched

    xs = coords[0::2]
    mid_x = (min(xs) + max(xs)) / 2

    new_coords = []
    for i in range(0, len(coords), 2):
        x, y = coords[i], coords[i + 1]
        if x <= mid_x:
            x = max(0, x - padding)
        else:
            x = x + padding
        new_coords.extend([x, y])

    return " ".join(map(str, new_coords))


def migrate(app, padding: int, dry_run: bool):
    from app.models import Line
    from app import db

    with app.app_context():
        lines = Line.query.all()
        print(f"{'[DRY RUN] ' if dry_run else ''}Padding {len(lines)} polygons by ±{padding}px…")

        changed = skipped = 0
        for i, line in enumerate(lines, 1):
            raw = line.polygon_points.strip()
            if not raw:
                skipped += 1
                continue

            padded = pad_polygon_lr(raw, padding)
            if padded == raw:
                skipped += 1
                continue

            line.polygon_points = padded
            changed += 1

            if not dry_run and i % BATCH_SIZE == 0:
                db.session.commit()
                print(f"  {i}/{len(lines)} committed…", flush=True)

        if not dry_run:
            db.session.commit()

        print(f"\nDone. {changed} polygons updated, {skipped} unchanged/skipped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--padding", type=int, default=5, help="Pixels to expand on each side (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Compute changes without writing to DB")
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    migrate(app, args.padding, args.dry_run)


if __name__ == "__main__":
    main()
