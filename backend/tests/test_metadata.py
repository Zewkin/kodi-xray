from pydantic import SecretStr

from xray.api.schemas import CastMember, MediaPayload
from xray.config import Settings
from xray.metadata.providers import (
    CompositeMetadataProvider,
    PersonMetadata,
    TmdbMetadataProvider,
    TvmazeMetadataProvider,
    episode_identity,
)


def settings(tmp_path, *, tmdb_token=None, max_cast=80):
    return Settings(
        path_maps=[{"kodi_prefix": "nfs://nas/media/", "backend_prefix": tmp_path}],
        api_token=SecretStr("a" * 24),
        tmdb_token=SecretStr(tmdb_token) if tmdb_token else None,
        metadata={"tvmaze_enabled": True, "max_cast": max_cast},
    )


def test_tvmaze_title_from_raw_episode_filename():
    media = MediaPayload(
        file=(
            "nfs://nas/media/The.Americans.S01.1080p/"
            "The.Americans.S01E02.1080p.BluRay.mkv"
        ),
        media_type="video",
    )
    assert TvmazeMetadataProvider.search_title(media) == "The Americans"


def test_tvmaze_does_not_guess_non_episode_filename():
    media = MediaPayload(file="nfs://nas/media/random-video.mkv", media_type="video")
    assert TvmazeMetadataProvider.search_title(media) is None


def test_episode_identity_strips_release_year_from_game_of_thrones_filename():
    media = MediaPayload(
        file=(
            "nfs://nas/media/Game of Thrones Complete 4K Collection/"
            "Game of Thrones (2011) - S01E01 - Winter Is Coming.mkv"
        ),
        media_type="unknown",
        season=-1,
        episode=-1,
    )

    assert episode_identity(media) == episode_identity(
        MediaPayload(file=media.file, title="Game of Thrones (2011) - S01E01")
    )
    identity = episode_identity(media)
    assert identity is not None
    assert (identity.title, identity.year, identity.season, identity.episode) == (
        "Game of Thrones",
        2011,
        1,
        1,
    )


def test_episode_identity_strips_dot_delimited_release_year():
    media = MediaPayload(
        file=(
            "nfs://nas/media/Rome.2005.S01.1080p/"
            "Rome.2005.S01E02.How.Titus.Pullo.Brought.Down.the.Republic.mkv"
        ),
        media_type="unknown",
    )

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.year, identity.season, identity.episode) == (
        "Rome",
        2005,
        1,
        2,
    )


def test_episode_identity_preserves_show_whose_title_is_a_year():
    media = MediaPayload(file="nfs://nas/media/1923.S01E02.Natures.Empty.Throne.mkv")

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.year, identity.season, identity.episode) == (
        "1923",
        None,
        1,
        2,
    )


def test_episode_identity_supports_scrubs_latin_x_numbering():
    media = MediaPayload(file="nfs://nas/media/Scrubs/Season 1/Scrubs 1x04 My Old Lady.avi")

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.season, identity.episode) == ("Scrubs", 1, 4)


def test_episode_identity_supports_scrubs_cyrillic_x_numbering():
    media = MediaPayload(
        file="nfs://nas/media/Scrubs/Season 3/Scrubs 3х14 My Screwup.avi"
    )

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.season, identity.episode) == ("Scrubs", 3, 14)


def test_episode_identity_uses_show_parent_when_filename_starts_with_sxe():
    media = MediaPayload(
        file="nfs://nas/media/South Park/Season 01/S01E02 - Weight Gain 4000.mkv"
    )

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.season, identity.episode) == ("South Park", 1, 2)


def test_episode_identity_uses_release_parent_when_filename_starts_with_sxe():
    media = MediaPayload(
        file=(
            "nfs://nas/media/Desperate Housewives Collection/"
            "Desperate.Housewives.S05.1080p.WEB-DL/S05E19.Look Into Their Eyes.mkv"
        )
    )

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.season, identity.episode) == (
        "Desperate Housewives",
        5,
        19,
    )


def test_episode_identity_combines_episode_only_filename_with_season_directory():
    media = MediaPayload(
        file=(
            "nfs://nas/media/Westworld (2016-2022) BDRip-AVC/"
            "Season 01/E10. The Bicameral Mind.mkv"
        )
    )

    identity = episode_identity(media)

    assert identity is not None
    assert (identity.title, identity.year, identity.season, identity.episode) == (
        "Westworld",
        2016,
        1,
        10,
    )


def test_tmdb_searches_show_then_uses_episode_credits(tmp_path, monkeypatch):
    provider = TmdbMetadataProvider(settings(tmp_path, tmdb_token="token"))
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        if path == "/search/tv":
            return {
                "results": [
                    {"id": 1399, "name": "Game of Thrones", "first_air_date": "2011-04-17"}
                ]
            }
        assert path == "/tv/1399/season/1/episode/1/credits"
        return {
            "cast": [
                {
                    "id": 1223786,
                    "name": "Emilia Clarke",
                    "character": "Daenerys Targaryen",
                    "profile_path": "/emilia.jpg",
                }
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    people = provider.get_cast(
        MediaPayload(
            file="nfs://nas/media/Game of Thrones (2011) - S01E01 - Winter Is Coming.mkv"
        )
    )

    assert calls == [
        (
            "/search/tv",
            {"query": "Game of Thrones", "include_adult": "false", "first_air_date_year": 2011},
        ),
        ("/tv/1399/season/1/episode/1/credits", None),
    ]
    assert people == [
        PersonMetadata(
            external_id="tmdb:1223786",
            name="Emilia Clarke",
            roles=["Daenerys Targaryen"],
            image_urls=["https://image.tmdb.org/t/p/w500/emilia.jpg"],
        )
    ]


def test_tvmaze_combines_main_and_episode_guest_cast_and_both_portraits(tmp_path, monkeypatch):
    provider = TvmazeMetadataProvider(settings(tmp_path))
    calls = []

    def cast_item(person_id, actor, role, suffix):
        return {
            "person": {
                "id": person_id,
                "name": actor,
                "image": {"original": f"https://images.example/{suffix}-actor.jpg"},
            },
            "character": {
                "name": role,
                "image": {"original": f"https://images.example/{suffix}-character.jpg"},
            },
        }

    def fake_get(path, params=None):
        calls.append((path, params))
        return {
            "/search/shows": [{"show": {"id": 82, "name": "Game of Thrones"}}],
            "/shows/82/cast": [cast_item(1, "Emilia Clarke", "Daenerys Targaryen", "emilia")],
            "/shows/82/episodebynumber": {"id": 4952},
            "/episodes/4952/guestcast": [cast_item(2, "Guest Actor", "Guest Role", "guest")],
        }[path]

    monkeypatch.setattr(provider, "_get", fake_get)
    people = provider.get_cast(
        MediaPayload(file="nfs://nas/media/Game of Thrones (2011) - S01E01 - Winter Is Coming.mkv")
    )

    assert calls == [
        ("/search/shows", {"q": "Game of Thrones"}),
        ("/shows/82/cast", None),
        ("/shows/82/episodebynumber", {"season": "1", "number": "1"}),
        ("/episodes/4952/guestcast", None),
    ]
    assert [(person.name, person.roles) for person in people] == [
        ("Emilia Clarke", ["Daenerys Targaryen"]),
        ("Guest Actor", ["Guest Role"]),
    ]
    assert people[0].image_urls == [
        "https://images.example/emilia-actor.jpg",
        "https://images.example/emilia-character.jpg",
    ]


def test_tvmaze_prefers_original_when_exact_titles_are_duplicated(tmp_path, monkeypatch):
    provider = TvmazeMetadataProvider(settings(tmp_path))
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        return {
            "/search/shows": [
                {"show": {"id": 84836, "name": "Scrubs", "premiered": "2026-02-25"}},
                {"show": {"id": 532, "name": "Scrubs", "premiered": "2001-10-02"}},
            ],
            "/shows/84836/episodebynumber": {"id": 90001, "name": "My Way Home"},
            "/shows/532/episodebynumber": {"id": 40945, "name": "My Old Lady"},
            "/shows/532/cast": [],
            "/episodes/40945/guestcast": [],
        }[path]

    monkeypatch.setattr(provider, "_get", fake_get)
    provider.get_cast(
        MediaPayload(file="nfs://nas/media/Scrubs/Season 1/Scrubs 1x04 My Old Lady.avi")
    )

    assert calls == [
        ("/search/shows", {"q": "Scrubs"}),
        ("/shows/84836/episodebynumber", {"season": "1", "number": "4"}),
        ("/shows/532/episodebynumber", {"season": "1", "number": "4"}),
        ("/shows/532/cast", None),
        ("/episodes/40945/guestcast", None),
    ]


def test_composite_prefers_tmdb_but_merges_missing_kodi_cast(tmp_path, monkeypatch):
    provider = CompositeMetadataProvider(settings(tmp_path, tmdb_token="token"))
    media = MediaPayload(
        file="nfs://nas/media/Show.S01E01.mkv",
        cast=[
            CastMember(name="Emilia Clarke", roles=["Dany"], image_urls=["https://kodi/emilia.jpg"]),
            CastMember(name="Kodi Only", roles=["Local Role"]),
        ],
    )
    monkeypatch.setattr(
        provider.tmdb,
        "get_cast",
        lambda value: [
            PersonMetadata(
                external_id="tmdb:1",
                name="Emilia Clarke",
                roles=["Daenerys Targaryen"],
                image_urls=["https://tmdb/emilia.jpg"],
            )
        ],
    )

    people = provider.get_cast(media)

    assert [person.name for person in people] == ["Emilia Clarke", "Kodi Only"]
    assert people[0].external_id == "tmdb:1"
    assert people[0].roles == ["Daenerys Targaryen", "Dany"]
    assert people[0].image_urls == ["https://tmdb/emilia.jpg", "https://kodi/emilia.jpg"]
