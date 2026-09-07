from dataclasses import dataclass


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
        width = theme["label"]["width"] * gui_width / 1920.0
        height = theme["label"]["height"] * gui_height / 1080.0
        margins = adapter.get_safe_regions(gui_width, gui_height)
        forbidden = [Rect(item["x"], item["y"], item["w"], item["h"]) for item in adapter.get_forbidden_regions(gui_width, gui_height, _has_clearart())]
        faces = [self._face_rect(person["bbox"], viewport) for person in people]
        placed = []
        for index, (person, face) in enumerate(zip(people, faces)):
            scored = []
            for name, horizontal, vertical in self.CANDIDATES:
                label = self._candidate(face, width, height, horizontal, vertical)
                score = self._penalty(label, face, faces, [item.label for item in placed], forbidden, margins, gui_width, gui_height)
                if adapter.theme["behavior"].get("prefer_edge_labels"):
                    score += min(label.x, max(0, gui_width - label.x - label.w)) * 0.02
                scored.append((score, name, label))
            _, name, label = min(scored, key=lambda item: item[0])
            placed.append(Placement(face, label, face.center, name, person))
        return placed

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

