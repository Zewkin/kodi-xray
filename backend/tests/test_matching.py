import numpy as np

from xray.recognition.matching import match_embedding


def gallery():
    return [
        {
            "person_id": 1,
            "external_id": "tmdb:1",
            "name": "Actor One",
            "roles": ["Hero"],
            "vector": np.asarray([1.0, 0.0], dtype=np.float32),
        },
        {
            "person_id": 2,
            "external_id": "tmdb:2",
            "name": "Actor Two",
            "roles": ["Rival"],
            "vector": np.asarray([0.0, 1.0], dtype=np.float32),
        },
    ]


def test_accepts_strong_unambiguous_match():
    result = match_embedding(np.asarray([0.99, 0.01]), gallery(), 0.48, 0.10)
    assert result.accepted
    assert result.person["external_id"] == "tmdb:1"


def test_unknown_wins_over_ambiguous_nearest_candidate():
    vector = np.asarray([0.707, 0.707], dtype=np.float32)
    result = match_embedding(vector, gallery(), 0.48, 0.10)
    assert not result.accepted
    assert result.person is None


def test_unknown_wins_below_threshold():
    vector = np.asarray([0.20, 0.20], dtype=np.float32)
    result = match_embedding(vector, gallery(), 0.48, 0.10)
    assert not result.accepted


def test_best_reference_is_not_diluted_by_a_dissimilar_portrait():
    references = gallery() + [
        {
            "person_id": 1,
            "external_id": "tmdb:1",
            "name": "Actor One",
            "roles": ["Hero"],
            "vector": np.asarray([0.0, -1.0], dtype=np.float32),
        }
    ]
    result = match_embedding(np.asarray([0.99, 0.01]), references, 0.48, 0.10)
    assert result.accepted
    assert result.person["external_id"] == "tmdb:1"
    assert result.best > 0.98
