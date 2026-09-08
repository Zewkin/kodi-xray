from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from xray.api.schemas import CastMember, MediaPayload
from xray.config import Settings


@dataclass
class PersonMetadata:
    external_id: str
    name: str
    roles: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EpisodeIdentity:
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None


EPISODE_PATTERN = re.compile(r"^(.*?)[ ._-]+S([0-9]{1,2})E([0-9]{1,3})(?:\b|[ ._-])", re.IGNORECASE)
X_EPISODE_PATTERN = re.compile(
    r"^(.*?)[ ._-]+([0-9]{1,2})[xх]([0-9]{1,3})(?:\b|[ ._-])", re.IGNORECASE
)
EPISODE_MARKER_PATTERN = re.compile(
    r"(?:^|[ ._-])S([0-9]{1,2})E([0-9]{1,3})(?:\b|[ ._-])", re.IGNORECASE
)
X_EPISODE_MARKER_PATTERN = re.compile(
    r"(?:^|[ ._-])([0-9]{1,2})[xх]([0-9]{1,3})(?:\b|[ ._-])", re.IGNORECASE
)
EPISODE_ONLY_PATTERN = re.compile(r"^E([0-9]{1,3})(?:\b|[ ._-])", re.IGNORECASE)
SEASON_DIRECTORY_PATTERN = re.compile(r"^(?:season|сезон)[ ._-]*([0-9]{1,2})$", re.IGNORECASE)
SEASON_RELEASE_PATTERN = re.compile(r"^(.*?)[ ._-]+S([0-9]{1,2})(?:\b|[ ._-])", re.IGNORECASE)
YEAR_RANGE_PATTERN = re.compile(
    r"^(.*?)\s*\(((?P<start>(?:19|20)[0-9]{2})(?:\s*[-–—]\s*(?:19|20)[0-9]{2})?)\).*$"
)
RELEASE_SUFFIX_PATTERN = re.compile(
    r"\b(?:2160p|1080[pi]|720p|576p|480p|uhd|blu-?ray|bdrip|web-?dl|webrip|remux|dvdrip)\b.*$",
    re.IGNORECASE,
)
TRAILING_YEAR_PATTERN = re.compile(
    r"(?:\s*[-–—]?\s*)(?:\((?P<parenthesized>(?:19|20)[0-9]{2})\)|(?P<bare>(?:19|20)[0-9]{2}))\s*$"
)


def episode_identity(media: MediaPayload) -> EpisodeIdentity | None:
    season = media.season if media.season is not None and media.season >= 0 else None
    episode = media.episode if media.episode is not None and media.episode >= 0 else None
    year = media.year

    candidates = [value for value in (media.show, media.title) if value]
    path_parts = [part for part in unquote(urlsplit(media.file).path).split("/") if part]
    filename = path_parts[-1].rsplit(".", 1)[0] if path_parts else ""
    candidates.append(filename)
    title = None
    for value in candidates:
        match = EPISODE_PATTERN.search(value) or X_EPISODE_PATTERN.search(value)
        if match:
            title = match.group(1)
            season = season if season is not None else int(match.group(2))
            episode = episode if episode is not None else int(match.group(3))
            break
        if value == media.show:
            title = value
            break
    if not title:
        marker = EPISODE_MARKER_PATTERN.search(filename) or X_EPISODE_MARKER_PATTERN.search(filename)
        if marker:
            season = season if season is not None else int(marker.group(1))
            episode = episode if episode is not None else int(marker.group(2))
            title, parent_year = _identity_from_parents(path_parts[:-1], season)
            year = year or parent_year
        else:
            episode_match = EPISODE_ONLY_PATTERN.search(filename)
            parent_season = _season_from_parents(path_parts[:-1])
            if episode_match and parent_season is not None:
                season = season if season is not None else parent_season
                episode = episode if episode is not None else int(episode_match.group(1))
                title, parent_year = _identity_from_parents(path_parts[:-1], season)
                year = year or parent_year
    if not title:
        return None

    title = " ".join(re.sub(r"[._]+", " ", title).split()).strip(" -–—")
    year_match = TRAILING_YEAR_PATTERN.search(title)
    if year_match:
        title_without_year = TRAILING_YEAR_PATTERN.sub("", title).strip(" -–—")
        if title_without_year:
            year = year or int(year_match.group("parenthesized") or year_match.group("bare"))
            title = title_without_year
    return EpisodeIdentity(title=title, year=year, season=season, episode=episode)


def _season_from_parents(parents: list[str]) -> int | None:
    for parent in reversed(parents):
        match = SEASON_DIRECTORY_PATTERN.fullmatch(parent.strip())
        if match:
            return int(match.group(1))
    return None


def _identity_from_parents(parents: list[str], season: int | None) -> tuple[str | None, int | None]:
    for parent in reversed(parents):
        value = parent.strip()
        if SEASON_DIRECTORY_PATTERN.fullmatch(value):
            continue
        release = SEASON_RELEASE_PATTERN.search(value)
        if release and (season is None or int(release.group(2)) == season):
            return release.group(1), None
        dated = YEAR_RANGE_PATTERN.search(value)
        if dated and dated.group(1).strip():
            return dated.group(1), int(dated.group("start"))
        if value:
            return value, None
    return None, None


def _episode_title_hint(media: MediaPayload) -> str | None:
    path_parts = [part for part in unquote(urlsplit(media.file).path).split("/") if part]
    filename = path_parts[-1].rsplit(".", 1)[0] if path_parts else ""
    marker = (
        EPISODE_MARKER_PATTERN.search(filename)
        or X_EPISODE_MARKER_PATTERN.search(filename)
        or EPISODE_ONLY_PATTERN.search(filename)
    )
    if not marker:
        return None
    value = re.sub(r"[._]+", " ", filename[marker.end():]).strip(" -–—")
    value = RELEASE_SUFFIX_PATTERN.sub("", value).strip(" -–—")
    return value or None


class MetadataProvider(ABC):
    @abstractmethod
    def resolve_media(self, media: MediaPayload) -> dict[str, Any]: ...

    @abstractmethod
    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]: ...

    @abstractmethod
    def get_person_images(self, person_id: str) -> list[str]: ...


class KodiMetadataProvider(MetadataProvider):
    def resolve_media(self, media: MediaPayload) -> dict[str, Any]:
        return media.model_dump(exclude={"cast"})

    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]:
        return [self._person(member) for member in media.cast]

    def get_person_images(self, person_id: str) -> list[str]:
        return []

    @staticmethod
    def _person(member: CastMember) -> PersonMetadata:
        external_id = member.id or "kodi:" + hashlib.sha256(member.name.casefold().encode()).hexdigest()[:24]
        return PersonMetadata(
            external_id=external_id,
            name=member.name,
            roles=list(dict.fromkeys(member.roles)),
            image_urls=[KodiMetadataProvider._unwrap_image(url) for url in member.image_urls if url],
        )

    @staticmethod
    def _unwrap_image(value: str) -> str:
        if value.startswith("image://"):
            value = unquote(value[8:])
            if value.endswith("/"):
                value = value[:-1]
        return value


class TmdbMetadataProvider(MetadataProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.token = settings.tmdb_token.get_secret_value() if settings.tmdb_token else None

    def resolve_media(self, media: MediaPayload) -> dict[str, Any]:
        return media.model_dump(exclude={"cast"})

    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]:
        if not self.token:
            return []
        identity = episode_identity(media)
        tmdb_id = media.unique_ids.get("tmdb") or self._search_tv_id(identity)
        if not tmdb_id:
            return []
        if identity and identity.season is not None and identity.episode is not None:
            path = f"/tv/{tmdb_id}/season/{identity.season}/episode/{identity.episode}/credits"
        else:
            media_kind = "tv" if media.media_type == "episode" else "movie"
            path = f"/{media_kind}/{tmdb_id}/credits"
        data = self._get(path)
        cast = data.get("cast", []) + data.get("guest_stars", [])
        people: list[PersonMetadata] = []
        seen: set[int] = set()
        for item in cast:
            person_id = item.get("id")
            if not person_id or person_id in seen:
                continue
            seen.add(person_id)
            role = item.get("character") or item.get("roles", [{}])[0].get("character")
            images = []
            if item.get("profile_path"):
                images.append(self.settings.metadata.tmdb_image_base_url + item["profile_path"])
            people.append(
                PersonMetadata(
                    external_id=f"tmdb:{person_id}",
                    name=item.get("name") or item.get("original_name") or str(person_id),
                    roles=[role] if role else [],
                    image_urls=images,
                )
            )
            if len(people) >= self.settings.metadata.max_cast:
                break
        return people

    def _search_tv_id(self, identity: EpisodeIdentity | None) -> int | None:
        if identity is None or identity.season is None or identity.episode is None:
            return None
        params: dict[str, Any] = {"query": identity.title, "include_adult": "false"}
        if identity.year:
            params["first_air_date_year"] = identity.year
        payload = self._get("/search/tv", params)
        results = payload.get("results", [])
        if not results and identity.year:
            params.pop("first_air_date_year", None)
            results = self._get("/search/tv", params).get("results", [])
        normalized = _normalize_name(identity.title)
        exact = [
            item
            for item in results
            if normalized in {_normalize_name(item.get("name", "")), _normalize_name(item.get("original_name", ""))}
        ]
        candidates = exact or results
        if identity.year and len(candidates) > 1:
            same_year = [item for item in candidates if str(item.get("first_air_date", "")).startswith(str(identity.year))]
            candidates = same_year or candidates
        return int(candidates[0]["id"]) if candidates and candidates[0].get("id") else None

    def get_person_images(self, person_id: str) -> list[str]:
        if not self.token or not person_id.startswith("tmdb:"):
            return []
        payload = self._get(f"/person/{person_id.split(':', 1)[1]}/images")
        profiles = sorted(payload.get("profiles", []), key=lambda item: item.get("vote_average", 0), reverse=True)
        return [
            self.settings.metadata.tmdb_image_base_url + item["file_path"]
            for item in profiles[: self.settings.metadata.reference_images_per_actor]
            if item.get("file_path")
        ]

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"}
        query = {"language": "en-US", **(params or {})}
        with httpx.Client(base_url=self.settings.metadata.tmdb_base_url, headers=headers, timeout=8) as client:
            response = client.get(path, params=query)
            response.raise_for_status()
            return response.json()


class TvmazeMetadataProvider(MetadataProvider):
    """Metadata-only fallback for raw TV filenames that Kodi has not scraped."""

    EPISODE_PATTERN = EPISODE_PATTERN

    def __init__(self, settings: Settings):
        self.settings = settings

    def resolve_media(self, media: MediaPayload) -> dict[str, Any]:
        return media.model_dump(exclude={"cast"})

    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]:
        if not self.settings.metadata.tvmaze_enabled:
            return []
        identity = episode_identity(media)
        if not identity:
            return []
        title = identity.title
        results = self._get("/search/shows", {"q": title})
        if not isinstance(results, list) or not results:
            return []
        normalized = self._normalize_title(title)
        exact = [item for item in results if self._normalize_title(item.get("show", {}).get("name", "")) == normalized]
        candidates = exact or results
        selected_episode = None
        if identity.year:
            same_year = [
                item
                for item in candidates
                if str(item.get("show", {}).get("premiered", "")).startswith(str(identity.year))
            ]
            candidates = same_year or candidates
        elif len(exact) > 1 and identity.season is not None and identity.episode is not None:
            hint = _episode_title_hint(media)
            viable = []
            for index, item in enumerate(exact):
                candidate_show = item.get("show", {})
                if not candidate_show.get("id"):
                    continue
                try:
                    candidate_episode = self._get(
                        f"/shows/{candidate_show['id']}/episodebynumber",
                        {"season": str(identity.season), "number": str(identity.episode)},
                    )
                except (httpx.HTTPError, ValueError):
                    continue
                similarity = 0.0
                if hint and candidate_episode.get("name"):
                    similarity = SequenceMatcher(
                        None,
                        _normalize_name(hint),
                        _normalize_name(candidate_episode["name"]),
                    ).ratio()
                viable.append((similarity, -index, item, candidate_episode))
            if viable:
                best = max(viable, key=lambda candidate: candidate[:2])
                if best[0] < 0.65:
                    best = max(viable, key=lambda candidate: candidate[1])
                _, _, selected, selected_episode = best
                candidates = [selected]
        show = candidates[0].get("show", {})
        if not show.get("id"):
            return []
        main_cast = self._get(f"/shows/{show['id']}/cast")
        guest_cast = []
        if identity.season is not None and identity.episode is not None:
            try:
                episode = selected_episode or self._get(
                    f"/shows/{show['id']}/episodebynumber",
                    {"season": str(identity.season), "number": str(identity.episode)},
                )
                if episode.get("id"):
                    guest_cast = self._get(f"/episodes/{episode['id']}/guestcast")
            except (httpx.HTTPError, ValueError):
                guest_cast = []
        return self._people_from_cast(
            (main_cast if isinstance(main_cast, list) else [])
            + (guest_cast if isinstance(guest_cast, list) else [])
        )

    def _people_from_cast(self, cast: list[dict[str, Any]]) -> list[PersonMetadata]:
        people: dict[int, PersonMetadata] = {}
        for item in cast:
            person = item.get("person") or {}
            character = item.get("character") or {}
            person_id = person.get("id")
            if not person_id or not person.get("name"):
                continue
            urls = []
            for image in (person.get("image") or {}, character.get("image") or {}):
                image_url = image.get("original") or image.get("medium")
                if isinstance(image_url, str) and image_url.startswith("https://") and image_url not in urls:
                    urls.append(image_url)
            role = character.get("name")
            if person_id not in people:
                people[person_id] = PersonMetadata(
                    external_id=f"tvmaze:{person_id}",
                    name=person["name"],
                    roles=[role] if role else [],
                    image_urls=urls,
                )
            else:
                current = people[person_id]
                if role and role not in current.roles:
                    current.roles.append(role)
                current.image_urls.extend(url for url in urls if url not in current.image_urls)
        return list(people.values())[: self.settings.metadata.max_cast]

    def get_person_images(self, person_id: str) -> list[str]:
        return []

    @classmethod
    def search_title(cls, media: MediaPayload) -> str | None:
        identity = episode_identity(media)
        return identity.title if identity else None

    @staticmethod
    def _clean_title(value: str) -> str:
        media = MediaPayload(file=value, title=value)
        identity = episode_identity(media)
        return identity.title if identity else " ".join(re.sub(r"[._]+", " ", value).split())

    @staticmethod
    def _normalize_title(value: str) -> str:
        return _normalize_name(value)

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        with httpx.Client(
            base_url=self.settings.metadata.tvmaze_base_url,
            headers={"Accept": "application/json", "User-Agent": "Kodi-XRay/0.1 (+local metadata cache)"},
            timeout=8,
            follow_redirects=False,
        ) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()


class CompositeMetadataProvider(MetadataProvider):
    def __init__(self, settings: Settings):
        self.kodi = KodiMetadataProvider()
        self.tmdb = TmdbMetadataProvider(settings)
        self.tvmaze = TvmazeMetadataProvider(settings)
        self.max_cast = settings.metadata.max_cast

    def resolve_media(self, media: MediaPayload) -> dict[str, Any]:
        return self.kodi.resolve_media(media)

    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]:
        kodi_cast = self.kodi.get_cast(media)
        try:
            tmdb_cast = self.tmdb.get_cast(media)
        except httpx.HTTPError:
            tmdb_cast = []
        if tmdb_cast:
            return _merge_cast(tmdb_cast, kodi_cast)[: self.max_cast]
        try:
            tvmaze_cast = self.tvmaze.get_cast(media)
        except (httpx.HTTPError, ValueError):
            tvmaze_cast = []
        return _merge_cast(tvmaze_cast, kodi_cast)[: self.max_cast]

    def get_person_images(self, person_id: str) -> list[str]:
        return self.tmdb.get_person_images(person_id)


def _normalize_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _merge_cast(primary: list[PersonMetadata], secondary: list[PersonMetadata]) -> list[PersonMetadata]:
    merged: dict[str, PersonMetadata] = {}
    for person in primary + secondary:
        key = _normalize_name(person.name)
        if key not in merged:
            merged[key] = PersonMetadata(
                external_id=person.external_id,
                name=person.name,
                roles=list(person.roles),
                image_urls=list(person.image_urls),
            )
            continue
        current = merged[key]
        current.roles.extend(role for role in person.roles if role not in current.roles)
        current.image_urls.extend(url for url in person.image_urls if url not in current.image_urls)
    return list(merged.values())
