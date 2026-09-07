from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit

from xray.config import Settings


class PathResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedMedia:
    kodi_path: str
    path: Path
    root: Path

    def media_key(self, duration: float) -> str:
        stat = self.path.stat()
        identity = "\0".join(
            (str(self.path), str(stat.st_size), str(stat.st_mtime_ns), f"{duration:.3f}")
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class SecurePathResolver:
    """Map Kodi NFS URLs to allow-listed local files without permitting traversal."""

    def __init__(self, settings: Settings):
        self._maps = settings.path_maps
        self._roots = tuple(root.resolve(strict=True) for root in settings.media.roots)

    @staticmethod
    def _canonical_url(value: str) -> str:
        if "\x00" in value:
            raise PathResolutionError("NUL is not allowed")
        decoded = unquote(value)
        parsed = urlsplit(decoded)
        if parsed.scheme.lower() != "nfs" or not parsed.hostname:
            raise PathResolutionError("only configured nfs:// paths are accepted")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise PathResolutionError("credentials, query and fragment are not allowed")
        segments = PurePosixPath(parsed.path).parts
        if ".." in segments:
            raise PathResolutionError("parent traversal is not allowed")
        host = parsed.hostname.lower()
        netloc = host if parsed.port is None else f"{host}:{parsed.port}"
        normalized_path = "/" + "/".join(part for part in segments if part not in ("/", "."))
        return urlunsplit(("nfs", netloc, normalized_path, "", ""))

    def resolve(self, kodi_path: str) -> ResolvedMedia:
        normalized = self._canonical_url(kodi_path)
        for mapping in self._maps:
            prefix = self._canonical_url(mapping.kodi_prefix)
            if not prefix.endswith("/"):
                prefix += "/"
            if not normalized.startswith(prefix):
                continue
            relative = normalized[len(prefix) :]
            if not relative or ".." in PurePosixPath(relative).parts:
                raise PathResolutionError("invalid relative media path")
            candidate = (mapping.backend_prefix / relative).resolve(strict=True)
            root = self._containing_root(candidate)
            if root is None:
                raise PathResolutionError("resolved path is outside configured media roots")
            if not candidate.is_file():
                raise PathResolutionError("media path is not a regular file")
            return ResolvedMedia(kodi_path=kodi_path, path=candidate, root=root)
        raise PathResolutionError("Kodi path does not match any configured path map")

    def _containing_root(self, candidate: Path) -> Path | None:
        for root in self._roots:
            try:
                candidate.relative_to(root)
                return root
            except ValueError:
                continue
        return None

