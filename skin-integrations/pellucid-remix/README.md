# Pellucid Remix typography integration

This optional local integration preserves the base skin-independent renderer
while matching the installed Pellucid Remix pause typography.

- Pellucid pause title: `pageTitle`, 48 px, line spacing 1.0.
- Pellucid media title: `menuTitle`, 30 px, line spacing 1.0.
- Large face label font: `xrayActor`, 32 px, line spacing 1.0.
- Small face label font: `xrayCharacter`, 20 px, line spacing 1.0.

Both size ratios are exactly 1.6. Pellucid's 68 px pause/title offset is
scaled by 32/48 to a 45 px character/actor offset.

`xrayActor` uses Pellucid's `roboto/condensedBold.ttf`; `xrayCharacter` uses
`roboto_slab/bold.ttf`. The compatibility names predate the character-first
layout: the theme maps the large font to the white character name and the
small font to the pink actor name. Register both names in every enabled
Font.xml fontset, then copy `theme-overrides.json` to
`special://profile/addon_data/script.kodi.xray/theme-overrides.json` and reload
the skin or restart Kodi. Back up Font.xml and the X-Ray theme first.

Inline cards have no face connector. Their content width is read from the
actual TrueType horizontal metrics of Pellucid's condensed character font and
slab actor font, then clamped to 120–520 px. The background adds 10 px of
padding on each side. A conservative per-font estimate is retained only as a
fallback when the active TTF cannot be read.
