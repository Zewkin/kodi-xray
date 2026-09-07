# Kodi addon

`script.kodi.xray` is pure Python and ships no NumPy, OpenCV, ONNX or native
libraries. It targets Kodi 21 Omega and Kodi 22 Piers on Android and CoreELEC.

The service registers `onAVStarted`, pause, resume, seek, stop and ended
callbacks. HTTP runs on daemon threads; the service loop consumes results and
updates the UI. Resume/stop invalidates the generation and closes the dialog
immediately, so late HTTP responses cannot reopen a stale overlay.

Manual activation uses `RunScript(script.kodi.xray)`. If the service is alive,
the script signals it through a Home window property. The addon publishes
`XRay.Active`, `XRay.State`, `XRay.Count`, `XRay.Ready` and `XRay.MediaKey`.

Kodi's `Player.GetViewMode` values feed the video-to-GUI transform. Normal
letterbox/pillarbox, zoom, pixel ratio and vertical shift are mapped linearly.
Non-linear stretch always selects the side-panel fallback.

Install the generated ZIP, set Backend URL and API token, then restart or
enable the addon service. The token is stored only in Kodi's private addon
profile and the backend environment file. Optional portraits are fetched with
the same bearer authentication into the private addon profile; they are never
embedded in public URLs. If `Show Unknown` is enabled, uncertain faces appear
only as an Unknown count in the side panel.
