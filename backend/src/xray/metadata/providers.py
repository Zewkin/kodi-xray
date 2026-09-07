from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

import httpx

from xray.api.schemas import CastMember, MediaPayload
from xray.config import Settings


@dataclass
class PersonMetadata:
    external_id: str
    name: str
    roles: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)


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
        tmdb_id = media.unique_ids.get("tmdb")
        if not self.token or not tmdb_id:
            return []
        if media.media_type == "episode" and media.season is not None and media.episode is not None:
            path = f"/tv/{tmdb_id}/season/{media.season}/episode/{media.episode}/credits"
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

    def _get(self, path: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"}
        with httpx.Client(base_url=self.settings.metadata.tmdb_base_url, headers=headers, timeout=8) as client:
            response = client.get(path, params={"language": "en-US"})
            response.raise_for_status()
            return response.json()


class CompositeMetadataProvider(MetadataProvider):
    def __init__(self, settings: Settings):
        self.kodi = KodiMetadataProvider()
        self.tmdb = TmdbMetadataProvider(settings)

    def resolve_media(self, media: MediaPayload) -> dict[str, Any]:
        return self.kodi.resolve_media(media)

    def get_cast(self, media: MediaPayload) -> list[PersonMetadata]:
        kodi_cast = self.kodi.get_cast(media)
        if kodi_cast:
            return kodi_cast
        return self.tmdb.get_cast(media)

    def get_person_images(self, person_id: str) -> list[str]:
        return self.tmdb.get_person_images(person_id)

