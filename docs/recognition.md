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

Only current-media cast centroids are considered. Acceptance requires both a
minimum cosine score and a top-one minus top-two margin. Defaults (`0.48` and
`0.10`) are intentionally conservative and must be calibrated using the actual
movie/episode acceptance corpus. Neighbour frames at ±0.5 seconds may reinforce
identity; only the central frame defines geometry.

InsightFace remains a possible future backend, but its public pretrained model
packs are restricted to non-commercial research. They are not downloaded or
accepted by this deployment.

