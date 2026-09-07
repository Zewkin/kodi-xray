# Skin adapter API v1

An adapter supplies:

- `get_safe_regions(gui_width, gui_height)`;
- `get_forbidden_regions(gui_width, gui_height, has_clearart)`;
- `supports_inline_face_labels()`;
- `visibility_condition()`;
- a theme dictionary containing layout/label/behavior values.

The layout engine owns candidate generation and collision penalties. The
adapter does not perform recognition, and backend output contains no screen
placement or skin semantics. Unknown skins use `GenericAdapter`.

New adapters should use 1920×1080 values in their JSON and let the addon scale
them to the actual GUI. Dynamic art/OSD regions belong in the adapter, not in
the recognition response.

