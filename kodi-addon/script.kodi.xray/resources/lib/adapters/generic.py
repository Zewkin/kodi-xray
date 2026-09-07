class GenericAdapter:
    skin_id = "generic"

    def __init__(self, theme):
        self.theme = theme

    def get_safe_regions(self, gui_width, gui_height):
        layout = self.theme["layout"]
        return {
            "left": layout["screen_margin_left"] * gui_width / 1920.0,
            "right": layout["screen_margin_right"] * gui_width / 1920.0,
            "top": layout["screen_margin_top"] * gui_height / 1080.0,
            "bottom": layout["screen_margin_bottom"] * gui_height / 1080.0,
        }

    def get_forbidden_regions(self, gui_width, gui_height, has_clearart=False):
        layout = self.theme["layout"]
        return [
            {
                "x": 0,
                "y": layout["subtitle_top"] * gui_height / 1080.0,
                "w": gui_width,
                "h": layout["subtitle_height"] * gui_height / 1080.0,
                "kind": "subtitles",
            }
        ]

    def supports_inline_face_labels(self):
        return True

    def visibility_condition(self):
        return (
            "Player.Paused + VideoPlayer.IsFullscreen + !Window.IsActive(videoosd) + "
            "!Window.IsActive(osdvideosettings) + !Window.IsActive(osdaudiosettings) + "
            "!Window.IsActive(osdsubtitlesettings) + !Window.IsActive(DialogSubtitles.xml)"
        )


