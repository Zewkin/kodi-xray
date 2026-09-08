import importlib.util
import sys
from pathlib import Path


MODULE = Path(__file__).parents[1] / "script.kodi.xray" / "resources" / "lib" / "layout.py"
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location("xray_addon_layout", MODULE)
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class Adapter:
    theme = {
        "layout": {"inline_max_faces": 3},
        "label": {"width": 300, "height": 70},
        "behavior": {"prefer_edge_labels": False},
    }

    def get_safe_regions(self, _width, _height):
        return {"left": 96, "right": 96, "top": 54, "bottom": 270}

    def get_forbidden_regions(self, _width, _height, _clearart):
        return [{"x": 0, "y": 810, "w": 1920, "h": 270}]


def test_cinematic_viewport_is_letterboxed():
    viewport = layout.compute_viewport(1920, 800, 1920, 1080, {})
    assert viewport.w == 1920
    assert viewport.h == 800
    assert viewport.y == 140


def test_labels_do_not_overlap_face_when_space_exists():
    people = [{"actor": {"name": "A"}, "roles": [], "bbox": {"x": 0.45, "y": 0.3, "w": 0.1, "h": 0.2}}]
    viewport = layout.Rect(0, 0, 1920, 1080)
    placements = layout.LayoutEngine().place(people, viewport, Adapter())
    assert len(placements) == 1
    assert not placements[0].label.overlaps(placements[0].face)


def test_auto_width_tracks_longest_visible_name():
    theme = {
        "width": 300,
        "auto_width": True,
        "min_width": 170,
        "max_width": 520,
        "actor_font_size": 20,
        "role_font_size": 32,
        "text_width_slack": 8,
    }
    short = {"actor": {"name": "A Li"}, "roles": ["May"]}
    long = {"actor": {"name": "David Oyelowo"}, "roles": ["Sheriff Holston Becker"]}
    assert layout.LayoutEngine._label_width(short, theme) == 170
    assert 300 < layout.LayoutEngine._label_width(long, theme) < 520


def test_auto_width_is_capped_for_exceptionally_long_roles():
    theme = {
        "auto_width": True,
        "min_width": 170,
        "max_width": 420,
        "actor_font_size": 20,
        "role_font_size": 32,
    }
    person = {"actor": {"name": "Actor"}, "roles": ["A" * 200]}
    assert layout.LayoutEngine._label_width(person, theme) == 420


def test_auto_width_accepts_font_calibration():
    theme = {
        "auto_width": True,
        "min_width": 120,
        "max_width": 520,
        "actor_font_size": 20,
        "role_font_size": 32,
        "actor_width_scale": 1.0,
        "role_width_scale": 0.7,
        "text_width_slack": 6,
    }
    person = {"actor": {"name": "Jordan Gavaris"}, "roles": ["Felix Dawkins"]}
    width = layout.LayoutEngine._label_width(person, theme)
    assert 145 < width < 150
