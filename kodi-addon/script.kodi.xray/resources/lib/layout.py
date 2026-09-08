import unicodedata
from dataclasses import dataclass

try:
    from .font_metrics import measure_text
except ImportError:  # Direct module loading in the lightweight test harness.
    from font_metrics import measure_text


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def overlaps(self, other):
        return not (
            self.x + self.w <= other.x
            or other.x + other.w <= self.x
            or self.y + self.h <= other.y
            or other.y + other.h <= self.y
        )

    @property
    def center(self):
        return self.x + self.w / 2.0, self.y + self.h / 2.0


@dataclass
class Placement:
    face: Rect
    label: Rect
    anchor: tuple
    candidate: str
    person: dict


class LayoutEngine:
    CANDIDATES = (
        ("right", 1, 0),
        ("top-right", 1, -1),
        ("bottom-right", 1, 1),
        ("left", -1, 0),
        ("top-left", -1, -1),
        ("bottom-left", -1, 1),
        ("above", 0, -1),
        ("below", 0, 1),
    )

    def place(self, people, viewport, adapter, gui_width=1920, gui_height=1080):
        theme = adapter.theme
        label_theme = theme["label"]
        height = theme["label"]["height"] * gui_height / 1080.0
        margins = adapter.get_safe_regions(gui_width, gui_height)
        forbidden = [Rect(item["x"], item["y"], item["w"], item["h"]) for item in adapter.get_forbidden_regions(gui_width, gui_height, _has_clearart())]
        faces = [self._face_rect(person["bbox"], viewport) for person in people]
        placed = []
        for index, (person, face) in enumerate(zip(people, faces)):
            width = self._label_width(person, label_theme) * gui_width / 1920.0
            scored = []
            for name, horizontal, vertical in self.CANDIDATES:
                label = self._candidate(face, width, height, horizontal, vertical)
                score = self._penalty(label, face, faces, [item.label for item in placed], forbidden, margins, gui_width, gui_height)
                if adapter.theme["behavior"].get("prefer_edge_labels"):
                    score += min(label.x, max(0, gui_width - label.x - label.w)) * 0.02
                scored.append((score, name, label))
            _, name, label = min(scored, key=lambda item: item[0])
            placed.append(Placement(face, label, self._anchor(face, name), name, person))
        return placed

    @classmethod
    def _label_width(cls, person, theme):
        fallback = float(theme.get("width", 330))
        if not theme.get("auto_width", False):
            return fallback

        actor = person.get("actor", {}).get("name", "")
        roles = " / ".join(person.get("roles", []))
        actor_size = float(theme.get("actor_font_size", 20))
        role_size = float(theme.get("role_font_size", 32))
        actor_width = cls._font_text_width(actor, actor_size, "actor", theme)
        role_width = cls._font_text_width(roles, role_size, "role", theme)
        content_width = max(actor_width, role_width)
        content_width += float(theme.get("text_width_slack", 8))
        if theme.get("show_portrait") and person.get("portrait"):
            content_width += float(theme.get("portrait_width", 80))
        minimum = float(theme.get("min_width", 160))
        maximum = float(theme.get("max_width", 520))
        return max(minimum, min(maximum, content_width))

    @classmethod
    def _font_text_width(cls, text, font_size, prefix, theme):
        measured = measure_text(theme.get(prefix + "_font_file"), text, font_size)
        if measured is not None:
            return measured
        default_scale = float(theme.get("text_width_scale", 1.0))
        scale = float(theme.get(prefix + "_width_scale", default_scale))
        return cls._estimated_text_width(text, font_size) * scale

    @staticmethod
    def _estimated_text_width(text, font_size):
        """Approximate Kodi label width where its Python API exposes no text metrics."""
        units = 0.0
        for char in text or "":
            category = unicodedata.category(char)
            if category.startswith("M"):
                continue
            if char.isspace():
                units += 0.32
            elif char in "ijlI1|!.,:;'`":
                units += 0.28
            elif char in "mwMW@%&ЖШЩЮФЫ":
                units += 0.86
            elif unicodedata.east_asian_width(char) in ("W", "F"):
                units += 1.0
            elif category.startswith("P"):
                units += 0.38
            elif char.isupper():
                units += 0.62
            elif char.isdigit():
                units += 0.54
            else:
                units += 0.52
        return units * font_size

    @staticmethod
    def _anchor(face, candidate):
        x, y = face.center
        if "right" in candidate:
            x = face.x + face.w + 6
        elif "left" in candidate:
            x = face.x - 6
        if "top" in candidate or candidate == "above":
            y = face.y - 6
        elif "bottom" in candidate or candidate == "below":
            y = face.y + face.h + 6
        return x, y

    @staticmethod
    def _face_rect(bbox, viewport):
        return Rect(
            viewport.x + bbox["x"] * viewport.w,
            viewport.y + bbox["y"] * viewport.h,
            bbox["w"] * viewport.w,
            bbox["h"] * viewport.h,
        )

    @staticmethod
    def _candidate(face, width, height, horizontal, vertical):
        gap = 28
        if horizontal > 0:
            x = face.x + face.w + gap
        elif horizontal < 0:
            x = face.x - width - gap
        else:
            x = face.x + (face.w - width) / 2
        if vertical > 0:
            y = face.y + face.h + gap
        elif vertical < 0:
            y = face.y - height - gap
        else:
            y = face.y + (face.h - height) / 2
        return Rect(x, y, width, height)

    @staticmethod
    def _penalty(label, face, faces, labels, forbidden, margins, gui_width, gui_height):
        score = 0.0
        if label.x < margins["left"] or label.y < margins["top"]:
            score += 100000
        if label.x + label.w > gui_width - margins["right"] or label.y + label.h > gui_height - margins["bottom"]:
            score += 100000
        score += sum(50000 for other in faces if label.overlaps(other))
        score += sum(20000 for other in labels if label.overlaps(other))
        score += sum(18000 for region in forbidden if label.overlaps(region))
        lx, ly = label.center
        fx, fy = face.center
        score += ((lx - fx) ** 2 + (ly - fy) ** 2) ** 0.5 * 0.1
        return score


def compute_viewport(frame_width, frame_height, gui_width, gui_height, view_mode):
    pixel_ratio = float(view_mode.get("pixelratio", 1.0) or 1.0)
    aspect = frame_width * pixel_ratio / max(frame_height, 1)
    gui_aspect = gui_width / max(gui_height, 1)
    if aspect >= gui_aspect:
        width = gui_width
        height = width / aspect
    else:
        height = gui_height
        width = height * aspect
    zoom = float(view_mode.get("zoom", 1.0) or 1.0)
    width *= zoom
    height *= zoom
    x = (gui_width - width) / 2.0
    shift = float(view_mode.get("verticalshift", 0.0) or 0.0)
    y = (gui_height - height) / 2.0 + shift * gui_height * 0.05
    return Rect(x, y, width, height)


def _has_clearart():
    try:
        import xbmc

        return bool(xbmc.getInfoLabel("Player.Art(clearart)") or xbmc.getInfoLabel("Player.Art(clearlogo)"))
    except ImportError:
        return False
