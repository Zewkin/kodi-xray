# Pellucid adapter

Reference repository: `chrisbevan/skin.pellucid`.
Reference commit: `1394c02fc8b189263ae6abf1b1102b2a4d7bc7f1`.

At that commit, `1080i/DialogSeekBar.xml` owns the paused-video layer and is
visible for `Player.Paused` while hiding for `videoosd`, video/audio settings,
subtitle dialogs, fullscreen info and visualisation. X-Ray mirrors those
conditions and renders a separate transparent dialog above it; no Pellucid XML
is modified.

The grid is 1920×1080 with 96 px left/right rhythm, a 54 px top margin, 72 px
columns and 36 px rows. X-Ray reserves 270 px at the bottom. Clearart begins at
column 15 / row 18 (roughly x=1104, y=666); clearlogo begins at column 14.
When either is present, the adapter reserves the lower-right art region.

The default `razzmatazz.xml` palette maps `textActive` to `fff0f0f0`,
`highlight` to `ffdb0a5b`, and background to `ff151515`. Actor/role sizing
tracks Pellucid `itemTitle` (30) and `itemSubTitle` (24). The addon references
semantic fonts but does not copy Pellucid fonts or artwork. The default style
uses no portrait, card or visible face box—only actor, role, a short leader and
anchor. Debug mode is the exception.

After a Pellucid update, verify `DialogSeekBar.xml`, `VideoOSD.xml`,
`Includes_grid.xml`, `Font.xml` and the active color file. Core X-Ray continues
to work even if safe-area calibration needs an adapter update. No native patch
is included in 0.1.0.

