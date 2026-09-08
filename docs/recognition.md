# Recognition

The backend depends on the `FaceRecognitionBackend` contract (`detect`,
`align`, `embed`) rather than a model-specific API.

The baseline uses:

- OpenCV YuNet `2023mar`, SHA-256
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`, MIT;
- OpenCV SFace `2021dec`, SHA-256
  `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`,
  Apache-2.0.

`install-models.sh` downloads exact files from the official OpenCV Hugging
Face organization, verifies both hashes, and writes a local manifest including
source, version, license and download date. Weights are not committed.

YuNet supplies a box, five landmarks and detector confidence. SFace performs
landmark alignment before returning an L2-normalized embedding. Gallery images
are rejected when the face is small, blurred, absent, or ambiguous among
multiple similarly-sized faces.

Only the current media's cast is considered. Each identity is scored by its
best validated reference image, so a weak portrait cannot dilute a strong one.
Acceptance requires both a minimum cosine score and a top-one minus top-two margin. The deployed baseline
uses a `0.36` match threshold, a `0.10` margin and a `0.45` YuNet detector
threshold, calibrated for tone-mapped dark HDR frames. Neighbour frames at
±0.5 seconds may reinforce identity; only the central frame defines geometry.

InsightFace remains a possible future backend, but its public pretrained model
packs are restricted to non-commercial research. They are not downloaded or
accepted by this deployment.

For raw `Show (Year) - S01E02...` filenames, the backend extracts the normalized
show title, year, season and episode. With `XRAY_TMDB_TOKEN` configured it first
searches TMDb for the show, then requests the exact episode's credits from
`/tv/{series_id}/season/{season}/episode/{episode}/credits`. Kodi cast data is
merged only to fill gaps.

If TMDb is unavailable or has no result, the deployed configuration falls back
to TVmaze. It combines the show's main cast with `/episodes/:id/guestcast` and
caches both actor and character portraits when present. No video frames or
embeddings leave the backend. TVmaze data is used under its CC BY-SA
attribution terms: https://www.tvmaze.com/api
