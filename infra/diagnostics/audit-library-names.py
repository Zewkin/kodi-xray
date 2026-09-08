#!/usr/bin/env python3
"""Audit episode filename conventions against the production metadata parser."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from xray.api.schemas import MediaPayload
from xray.metadata.providers import episode_identity


VIDEO_EXTENSIONS = {
    ".avi", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4",
    ".mpeg", ".mpg", ".ts", ".vob", ".webm", ".wmv",
}
SXE = re.compile(r"S[0-9]{1,2}E[0-9]{1,3}", re.IGNORECASE)
LATIN_X = re.compile(r"[0-9]{1,2}x[0-9]{1,3}", re.IGNORECASE)
CYRILLIC_X = re.compile(r"[0-9]{1,2}х[0-9]{1,3}", re.IGNORECASE)
SEASON_DIRECTORY = re.compile(r"^(?:season|сезон)[ ._-]*[0-9]{1,2}$", re.IGNORECASE)
EPISODE_ONLY = re.compile(r"^E[0-9]{1,3}(?:\b|[ ._-])", re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--examples", type=int, default=5)
    args = parser.parse_args()

    videos = sorted(
        path for path in args.root.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    formats = Counter()
    parsed_titles = Counter()
    parsed_identities = Counter()
    identity_examples = {}
    unsupported: dict[str, list[str]] = defaultdict(list)
    likely_episodes = 0
    parsed_episodes = 0

    for path in videos:
        relative = path.relative_to(args.root)
        stem = path.stem
        parents = relative.parts[:-1]
        if SXE.search(stem):
            format_name = "SxxEyy"
        elif CYRILLIC_X.search(stem):
            format_name = "NхNN (Cyrillic)"
        elif LATIN_X.search(stem):
            format_name = "NxNN"
        elif EPISODE_ONLY.search(stem) and any(SEASON_DIRECTORY.fullmatch(part) for part in parents):
            format_name = "Exx + Season directory"
        else:
            continue
        likely_episodes += 1
        formats[format_name] += 1
        media = MediaPayload(file="nfs://audit/downloads/" + relative.as_posix())
        identity = episode_identity(media)
        if identity is None:
            top = relative.parts[0]
            if len(unsupported[top]) < args.examples:
                unsupported[top].append(relative.as_posix())
            continue
        parsed_episodes += 1
        parsed_titles[identity.title] += 1
        identity_key = f"{identity.title} ({identity.year or 'year unknown'})"
        parsed_identities[identity_key] += 1
        identity_examples.setdefault(identity_key, relative.as_posix())

    print(json.dumps({
        "video_files": len(videos),
        "likely_episodes": likely_episodes,
        "parsed_episodes": parsed_episodes,
        "unsupported_episodes": likely_episodes - parsed_episodes,
        "formats": dict(formats),
        "parsed_titles": dict(parsed_titles.most_common()),
        "parsed_identities": dict(parsed_identities.most_common()),
        "identity_examples": identity_examples,
        "unsupported_groups": unsupported,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
