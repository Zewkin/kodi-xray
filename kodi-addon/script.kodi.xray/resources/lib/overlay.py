import os

import xbmcaddon
import xbmcgui
import xbmcvfs

from .kodi import gui_size, view_mode
from .layout import LayoutEngine, compute_viewport


class OverlayWindow:
    """Non-focusable overlay surface attached to Kodi's fullscreen video window."""

    def __init__(self):
        self.window = xbmcgui.Window(12005)
        self.dynamic_controls = []
        self.closed = False

    def configure(self, result, adapter, settings):
        self.result = result
        self.adapter = adapter
        self.settings = settings
        addon_path = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
        self.dark_texture = os.path.join(addon_path, "resources", "media", "dark.png")
        self.accent_texture = os.path.join(addon_path, "resources", "media", "accent.png")
        self._render()

    def _add(self, control):
        self.window.addControl(control)
        self.dynamic_controls.append(control)
        return control

    def show(self):
        # Controls are visible as soon as they are attached. Keeping this method
        # preserves the renderer interface without activating a focus-stealing dialog.
        return None

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.dynamic_controls:
            try:
                self.window.removeControls(self.dynamic_controls)
            except (AttributeError, RuntimeError):
                for control in self.dynamic_controls:
                    try:
                        self.window.removeControl(control)
                    except RuntimeError:
                        pass
        self.dynamic_controls = []

    def _render(self):
        width, height = gui_size()
        mode = view_mode()
        requested_mode = self.settings.get("display_mode", "auto")
        nonlinear = bool(mode.get("nonlinstretch", False))
        people = self.result.get("people", [])
        unknown = self.result.get("unknown_faces", 0) if self.settings.get("show_unknown") else 0
        inline_max = self.adapter.theme["layout"]["inline_max_faces"]
        use_side = requested_mode == "side" or nonlinear or len(people) > inline_max or bool(unknown)
        if requested_mode == "inline" and not nonlinear:
            use_side = False
        if use_side:
            self._render_side_panel(people, unknown, width, height)
            return
        frame = self.result.get("frame", {"width": 1920, "height": 1080})
        viewport = compute_viewport(frame["width"], frame["height"], width, height, mode)
        placements = LayoutEngine().place(people, viewport, self.adapter, width, height)
        for placement in placements:
            self._render_inline(placement, width, height)
        if self.settings.get("debug"):
            self._render_debug(placements, width, height)

    def _render_inline(self, placement, gui_width, gui_height):
        theme = self.adapter.theme["label"]
        rect = placement.label
        x, y, w, h = (int(rect.x), int(rect.y), int(rect.w), int(rect.h))
        x_scale = gui_width / 1920.0
        y_scale = gui_height / 1080.0
        if theme.get("show_background") in ("always", "auto"):
            padding_x = int(theme.get("background_padding_x", 10) * x_scale)
            padding_y = int(theme.get("background_padding_y", 6) * y_scale)
            self._add(
                xbmcgui.ControlImage(
                    x - padding_x, y - padding_y, w + padding_x * 2, h + padding_y * 2,
                    self.dark_texture, colorDiffuse=theme["background_color"]
                )
            )
        actor = placement.person.get("actor", {}).get("name", "")
        roles = " / ".join(placement.person.get("roles", []))
        role_height = int(theme.get("role_height", h * 0.56) * (y_scale if "role_height" in theme else 1.0))
        actor_offset = int(theme.get("actor_offset", h * 0.62) * (y_scale if "actor_offset" in theme else 1.0))
        actor_height = int(theme.get("actor_height", h * 0.36) * (y_scale if "actor_height" in theme else 1.0))
        text_x = x
        text_width = w
        portrait = placement.person.get("portrait")
        if self.settings.get("show_portrait") and portrait:
            portrait_size = min(h, 68)
            self._add(xbmcgui.ControlImage(x, y, portrait_size, portrait_size, portrait))
            text_x += portrait_size + 12
            text_width = max(80, text_width - portrait_size - 12)
        show_role = self.settings.get("show_character", True) and bool(roles)
        if show_role:
            self._add(
                xbmcgui.ControlLabel(
                    text_x, y, text_width, role_height, roles,
                    font=theme["role_font"], textColor=theme["role_color"]
                )
            )
        if self.settings.get("show_actor", True):
            actor_y = y + actor_offset if show_role else y
            self._add(
                xbmcgui.ControlLabel(
                    text_x, actor_y, text_width, actor_height, actor,
                    font=theme["actor_font"], textColor=theme["actor_color"]
                )
            )
    def _render_side_panel(self, people, unknown, width, height):
        theme = self.adapter.theme["label"]
        panel_width = int(width * 0.34)
        x = width - panel_width
        self._add(xbmcgui.ControlImage(x, 0, panel_width, height, self.dark_texture, colorDiffuse="E6151515"))
        self._add(xbmcgui.ControlLabel(x + 42, 56, panel_width - 84, 44, "X-RAY", font=theme["role_font"], textColor=theme["accent_color"]))
        y = 126
        y_scale = height / 1080.0
        actor_offset = int(theme.get("actor_offset", 45) * (y_scale if "actor_offset" in theme else 1.0))
        actor_height = int(theme.get("actor_height", 26) * (y_scale if "actor_height" in theme else 1.0))
        role_height = int(theme.get("role_height", 30) * (y_scale if "role_height" in theme else 1.0))
        row_height = max(int(78 * y_scale), actor_offset + actor_height + int(8 * y_scale))
        for index, person in enumerate(people[:12], 1):
            actor = person.get("actor", {}).get("name", "")
            roles = " / ".join(person.get("roles", []))
            self._add(xbmcgui.ControlLabel(x + 42, y, 42, 36, str(index), font=theme["actor_font"], textColor=theme["accent_color"]))
            text_x = x + 86
            portrait = person.get("portrait")
            if self.settings.get("show_portrait") and portrait:
                self._add(xbmcgui.ControlImage(text_x, y, 58, 58, portrait))
                text_x += 70
            if roles:
                self._add(xbmcgui.ControlLabel(text_x, y, width - text_x - 32, role_height, roles, font=theme["role_font"], textColor=theme["role_color"]))
            actor_y = y + actor_offset if roles else y
            self._add(xbmcgui.ControlLabel(text_x, actor_y, width - text_x - 32, actor_height, actor, font=theme["actor_font"], textColor=theme["actor_color"]))
            y += row_height
        if unknown and y < height - 70:
            self._add(xbmcgui.ControlLabel(x + 42, y, 42, 36, "?", font=theme["actor_font"], textColor=theme["accent_color"]))
            label = "UNKNOWN" if unknown == 1 else "UNKNOWN × {}".format(unknown)
            self._add(xbmcgui.ControlLabel(x + 86, y, panel_width - 118, 36, label, font=theme["actor_font"], textColor=theme["actor_color"]))

    def _render_debug(self, placements, width, height):
        for placement in placements:
            face = placement.face
            color = self.adapter.theme["label"]["accent_color"]
            x, y, w, h = int(face.x), int(face.y), int(face.w), int(face.h)
            self._add(xbmcgui.ControlImage(x, y, w, 2, self.accent_texture, colorDiffuse=color))
            self._add(xbmcgui.ControlImage(x, y + h - 2, w, 2, self.accent_texture, colorDiffuse=color))
            self._add(xbmcgui.ControlImage(x, y, 2, h, self.accent_texture, colorDiffuse=color))
            self._add(xbmcgui.ControlImage(x + w - 2, y, 2, h, self.accent_texture, colorDiffuse=color))
            text = "sim {:.3f} margin {:.3f} {}".format(
                placement.person.get("similarity", 0), placement.person.get("top2_margin", 0), placement.candidate
            )
            self._add(xbmcgui.ControlLabel(x, max(0, y - 24), 360, 24, text, font="font10", textColor="FFFFFFFF"))
        summary = "API {:.0f}ms | faces {} | unknown {}".format(
            self.result.get("latency_ms", 0), len(placements), self.result.get("unknown_faces", 0)
        )
        self._add(xbmcgui.ControlLabel(24, 18, width - 48, 28, summary, font="font10", textColor="FFFFFFFF"))


def create_overlay(result, adapter, settings):
    window = OverlayWindow()
    window.configure(result, adapter, settings)
    return window
