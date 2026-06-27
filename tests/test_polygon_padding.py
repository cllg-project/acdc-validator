"""Tests for the left/right polygon padding migration."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from scripts.migrate_polygon_padding import pad_polygon_lr


# ---------------------------------------------------------------------------
# Unit tests for pad_polygon_lr
# ---------------------------------------------------------------------------


def test_rectangle_expands_left_and_right():
    # "x_left y_top x_left y_bottom x_right y_bottom x_right y_top"
    pts = "100 200 100 250 900 250 900 200"
    result = pad_polygon_lr(pts, padding=5)
    coords = list(map(int, result.split()))
    xs = coords[0::2]
    assert min(xs) == 95
    assert max(xs) == 905


def test_irregular_polygon_left_points_shift_left():
    # Left side: x=95,100; right side: x=900,905 — midpoint ~500
    pts = "100 200 95 230 100 250 900 250 905 220 900 200"
    result = pad_polygon_lr(pts, padding=5)
    coords = list(map(int, result.split()))
    # x=100 → 95, x=95 → 90, x=900 → 905, x=905 → 910
    assert coords[0] == 95   # (100,200) x
    assert coords[2] == 90   # (95,230) x
    assert coords[4] == 95   # (100,250) x
    assert coords[6] == 905  # (900,250) x
    assert coords[8] == 910  # (905,220) x
    assert coords[10] == 905 # (900,200) x


def test_y_coordinates_unchanged():
    pts = "100 200 100 250 900 250 900 200"
    result = pad_polygon_lr(pts, padding=5)
    coords = list(map(int, result.split()))
    ys = coords[1::2]
    assert ys == [200, 250, 250, 200]


def test_left_edge_clamped_to_zero():
    pts = "3 100 3 150 900 150 900 100"
    result = pad_polygon_lr(pts, padding=5)
    coords = list(map(int, result.split()))
    xs = coords[0::2]
    assert min(xs) == 0


def test_custom_padding():
    pts = "200 100 200 200 800 200 800 100"
    result = pad_polygon_lr(pts, padding=10)
    coords = list(map(int, result.split()))
    xs = coords[0::2]
    assert min(xs) == 190
    assert max(xs) == 810


def test_zero_padding_is_noop():
    pts = "100 200 100 250 900 250 900 200"
    assert pad_polygon_lr(pts, padding=0) == pts


def test_malformed_odd_coords_returned_unchanged():
    pts = "100 200 300"
    assert pad_polygon_lr(pts, padding=5) == pts


def test_empty_string_returned_unchanged():
    assert pad_polygon_lr("", padding=5) == ""


# ---------------------------------------------------------------------------
# DB integration test
# ---------------------------------------------------------------------------


def test_migrate_updates_polygon_in_db(loaded_lines, db):
    from scripts.migrate_polygon_padding import pad_polygon_lr as _pad

    original_polygons = [line.polygon_points for line in loaded_lines]

    for line in loaded_lines:
        line.polygon_points = _pad(line.polygon_points, padding=5)
    db.session.commit()

    for line, original in zip(loaded_lines, original_polygons):
        assert line.polygon_points == _pad(original, padding=5)
        # Left side shifted left
        orig_coords = list(map(int, original.split()))
        new_coords = list(map(int, line.polygon_points.split()))
        orig_xs = orig_coords[0::2]
        new_xs = new_coords[0::2]
        assert min(new_xs) < min(orig_xs)
        assert max(new_xs) > max(orig_xs)
