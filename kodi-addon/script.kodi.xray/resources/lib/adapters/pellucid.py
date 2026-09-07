from .generic import GenericAdapter


class PellucidAdapter(GenericAdapter):
    skin_id = "skin.pellucid"

    def get_forbidden_regions(self, gui_width, gui_height, has_clearart=False):
        regions = super().get_forbidden_regions(gui_width, gui_height, has_clearart)
        regions.append(
            {"x": 0, "y": 810 * gui_height / 1080.0, "w": gui_width, "h": 270 * gui_height / 1080.0, "kind": "seekbar"}
        )
        if has_clearart:
            regions.append(
                {
                    "x": 1032 * gui_width / 1920.0,
                    "y": 666 * gui_height / 1080.0,
                    "w": 864 * gui_width / 1920.0,
                    "h": 414 * gui_height / 1080.0,
                    "kind": "clearart",
                }
            )
        return regions

    def visibility_condition(self):
        return (
            "Player.Paused + VideoPlayer.IsFullscreen + !Window.IsActive(videoosd) + "
            "!Window.IsActive(osdvideosettings) + !Window.IsActive(osdaudiosettings) + "
            "!Window.IsActive(osdsubtitlesettings) + !Window.IsActive(DialogSubtitles.xml) + "
            "!Window.IsVisible(fullscreeninfo) + !Window.IsVisible(visualisation)"
        )

