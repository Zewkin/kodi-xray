import os

import xbmcaddon
import xbmcgui
import xbmcvfs

from .kodi import gui_size, view_mode
from .layout import LayoutEngine, Rect, compute_viewport


class OverlayWindow(xbmcgui.WindowXMLDialog):
    def configure(self, result, adapter, settings):
        self.result = result
        self.adapter = adapter
        self.settings = settings
        self.dynamic_controls = []
        addon_path = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
        self.dark_texture = os.path.join(addon_path, "resources", "media", "dark.png")
        self.accent_texture = os.path.join(addon_path, "resources", "media", "accent.png")

    def onInit(self):
        self._render()

    def _add(self, control):
        self.addControl(control)
        self.dynamic_controls.append(control)
        return control

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
        if theme.get("show_background") == "always":
            self._add(xbmcgui.ControlImage(x - 10, y - 6, w + 20, h + 12, self.dark_texture, colorDiffuse=theme["background_color"]))
        actor = placement.person.get("actor", {}).get("name", "").upper()
        roles = " / ".join(placement.person.get("roles", []))
        text_x = x
        text_width = w
        portrait = placement.person.get("portrait")
        if self.settings.get("show_portrait") and portrait:
            portrait_size = min(h, 68)
            self._add(xbmcgui.ControlImage(x, y, portrait_size, portrait_size, portrait))
            text_x += portrait_size + 12
            text_width = max(80, w - portrait_size - 12)
        if self.settings.get("show_actor", True):
            self._add(
                xbmcgui.ControlLabel(
                    text_x, y, text_width, int(h * 0.52), actor, font=theme["actor_font"], textColor=theme["actor_color"]
                )
            )
        if self.settings.get("show_character", True) and roles:
            self._add(
                xbmcgui.ControlLabel(
                    text_x, y + int(h * 0.48), text_width, int(h * 0.42), roles, font=theme["role_font"], textColor=theme["role_color"]
                )
            )
        anchor_x, anchor_y = (int(value) for value in placement.anchor)
        line_y = y + h - 7
        if anchor_x >= x + w / 2:
            line_x = x + int(w * 0.48)
            line_w = max(20, anchor_x - line_x)
        else:
            line_x = anchor_x
            line_w = max(20, x + int(w * 0.52) - anchor_x)
        self._add(xbmcgui.ControlImage(line_x, line_y, line_w, 2, self.accent_texture))
        self._add(xbmcgui.ControlLabel(anchor_x - 9, anchor_y - 14, 24, 28, "●", font="font13", textColor=theme["accent_color"], alignment=2 | 4))

    def _render_side_panel(self, people, unknown, width, height):
        theme = self.adapter.theme["label"]
        panel_width = int(width * 0.34)
        x = width - panel_width
        self._add(xbmcgui.ControlImage(x, 0, panel_width, height, self.dark_texture, colorDiffuse="E6151515"))
        self._add(xbmcgui.ControlLabel(x + 42, 56, panel_width - 84, 44, "X-RAY", font=theme["actor_font"], textColor=theme["accent_color"]))
        y = 126
        for index, person in enumerate(people[:12], 1):
            actor = person.get("actor", {}).get("name", "").upper()
            roles = " / ".join(person.get("roles", []))
            self._add(xbmcgui.ControlLabel(x + 42, y, 42, 36, str(index), font=theme["actor_font"], textColor=theme["accent_color"]))
            text_x = x + 86
            portrait = person.get("portrait")
            if self.settings.get("show_portrait") and portrait:
                self._add(xbmcgui.ControlImage(text_x, y, 58, 58, portrait))
                text_x += 70
            self._add(xbmcgui.ControlLabel(text_x, y, width - text_x - 32, 36, actor, font=theme["actor_font"], textColor=theme["actor_color"]))
            if roles:
                self._add(xbmcgui.ControlLabel(text_x, y + 32, width - text_x - 32, 30, roles, font=theme["role_font"], textColor=theme["role_color"]))
            y += 78
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
    addon_path = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
    window = OverlayWindow("XRayOverlay.xml", addon_path, "Default", "1080i")
    window.configure(result, adapter, settings)
    return window
