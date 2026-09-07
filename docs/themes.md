# Themes

Bundled themes are `generic.json` and `pellucid.json`. Theme selection defaults
to Auto based on `xbmc.getSkinDir()`.

Users may place `theme-overrides.json` below
`special://profile/addon_data/script.kodi.xray/`. Overrides are recursively
merged at runtime and survive addon updates. Layout coordinates use the
1920×1080 reference canvas. Invalid override JSON is ignored with a warning.

