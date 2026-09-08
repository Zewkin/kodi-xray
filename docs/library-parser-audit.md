# Downloads parser audit

Audit date: 2026-09-08. Scope: recursive read-only scan of
`/mnt/bigdata/downloads`.

- Files inspected: 2,598 total, including 2,449 video files.
- Episode-like videos: 2,431.
- Parsed after fixes: 2,431 (100%).
- Unsupported episode-like filenames: 0.

Observed episode conventions:

| Convention | Count | Example |
| --- | ---: | --- |
| `SxxEyy` | 2,229 | `Show.S01E02.Title.mkv` |
| Latin `NxNN` | 160 | `Scrubs 1x04 My Old Lady.avi` |
| Cyrillic `NхNN` | 22 | `Scrubs 3х14 My Screwup.avi` |
| `Exx` plus season directory | 20 | `Season 01/E10. The Bicameral Mind.mkv` |

The scan found and fixed three previously unsupported directory-dependent
groups: 317 South Park episodes whose filename starts with `SxxEyy`, 180
Desperate Housewives episodes whose show title is in a season release folder,
and 20 Westworld episodes whose season appears only in the parent directory.

The remaining 18 videos without episode markers are feature films,
documentaries/specials, or Dolby Vision test clips. No multi-episode,
absolute-number, or standalone `Episode NN` conventions are present.

Exact-title collisions in TVmaze were checked for every parsed show title.
Candidate selection now verifies the requested episode and compares its title
when the filename provides one. Live checks resolved the intended versions of
Scrubs, Silo, The Americans, and Dark Matter.

Re-run the audit with:

```bash
PYTHONPATH=backend/src python infra/diagnostics/audit-library-names.py /media
```
