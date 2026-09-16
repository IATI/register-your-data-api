import json
from pathlib import Path
from typing import Any

import pytest

from register_your_data_api.cors import CORS_ALLOWED_ORIGINS_FILE, load_allowed_origins


def write_origins_file(tmp_path: Path, contents: Any) -> str:
    """Write an origins file containing the given JSON-serialisable contents."""

    origins_file = tmp_path / "cors-allowed-origins.json"
    origins_file.write_text(json.dumps(contents))

    return str(origins_file)


def write_raw_origins_file(tmp_path: Path, contents: str) -> str:
    """Write an origins file with contents that are not necessarily valid JSON."""

    origins_file = tmp_path / "cors-allowed-origins.json"
    origins_file.write_text(contents)

    return str(origins_file)


def test_no_origins_configured() -> None:
    assert load_allowed_origins({}) == []


@pytest.mark.parametrize("filename", ["", "   "])
def test_blank_filename_configured(filename: str) -> None:
    assert load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename}) == []


def test_origins_are_loaded(tmp_path: Path) -> None:
    origins = ["https://client.example.org", "https://dev.client.example.org"]

    filename = write_origins_file(tmp_path, origins)

    assert load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename}) == origins


def test_origins_file_may_be_an_empty_list(tmp_path: Path) -> None:
    """An empty list is valid configuration and means no cross-origin requests are allowed."""

    filename = write_origins_file(tmp_path, [])

    assert load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename}) == []


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "https://client.example.org",
        "https://client.example.org:8443",
    ],
)
def test_valid_origin_forms(tmp_path: Path, origin: str) -> None:
    filename = write_origins_file(tmp_path, [origin])

    assert load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename}) == [origin]


def test_missing_origins_file(tmp_path: Path) -> None:
    filename = str(tmp_path / "does-not-exist.json")

    with pytest.raises(RuntimeError, match="Could not read CORS allowed origins file"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})


def test_origins_file_is_not_valid_json(tmp_path: Path) -> None:
    filename = write_raw_origins_file(tmp_path, "['not json',]")

    with pytest.raises(RuntimeError, match="is not valid JSON"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})


def test_origins_file_is_not_readable_as_text(tmp_path: Path) -> None:
    """A file in the wrong encoding raises UnicodeDecodeError, which must not escape."""

    origins_file = tmp_path / "cors-allowed-origins.json"
    origins_file.write_bytes(json.dumps(["https://client.example.org"]).encode("utf-16"))

    with pytest.raises(RuntimeError, match="is not valid JSON"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: str(origins_file)})


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param({"origins": ["https://client.example.org"]}, id="object_not_list"),
        pytest.param("https://client.example.org", id="string_not_list"),
        pytest.param(123, id="number_not_list"),
    ],
)
def test_origins_file_must_contain_a_list(tmp_path: Path, contents: Any) -> None:
    """Valid JSON of the wrong shape is a different failure from a bad entry within a list."""

    filename = write_origins_file(tmp_path, contents)

    with pytest.raises(RuntimeError, match="must contain a JSON list of origins"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})


@pytest.mark.parametrize(
    "origin",
    [
        pytest.param(123, id="number_entry"),
        pytest.param(None, id="null_entry"),
        pytest.param(["https://client.example.org"], id="nested_list_entry"),
        pytest.param("", id="empty_entry"),
        pytest.param("   ", id="whitespace_entry"),
        pytest.param("https://client.example.org/", id="trailing_slash"),
        pytest.param("https://client.example.org/api/v1", id="path"),
        pytest.param("https://Client.Example.org", id="not_lower_case"),
        pytest.param("client.example.org", id="no_scheme"),
        pytest.param("ftp://client.example.org", id="unsupported_scheme"),
    ],
)
def test_malformed_origins_are_rejected(tmp_path: Path, origin: Any) -> None:
    """Each of these shapes must be refused.

    What varies between the cases is only whether the origin is rejected at all - the
    wording of the failure is the same for every one of them, and is covered by
    test_the_error_names_only_the_invalid_origins below.
    """

    filename = write_origins_file(tmp_path, [origin])

    with pytest.raises(RuntimeError, match="contains invalid origins"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})


def test_the_error_names_only_the_invalid_origins(tmp_path: Path) -> None:
    """Whoever is editing a long list needs to be told which entries are wrong."""

    filename = write_origins_file(
        tmp_path,
        [
            "https://good-one.example.org",
            "https://bad-one.example.org/",
            "https://good-two.example.org",
            "ftp://bad-two.example.org",
        ],
    )

    with pytest.raises(RuntimeError, match="contains invalid origins") as raised:
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})

    message = str(raised.value)

    assert "https://bad-one.example.org/" in message
    assert "ftp://bad-two.example.org" in message
    assert "good-one" not in message
    assert "good-two" not in message


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(["*"], id="only_wildcard"),
        pytest.param(["https://client.example.org", "*"], id="wildcard_alongside_an_origin"),
    ],
)
def test_wildcard_origins_are_rejected(tmp_path: Path, contents: Any) -> None:
    """A single "*" entry would put CORSMiddleware into allow-all mode, so it must not load."""

    filename = write_origins_file(tmp_path, contents)

    with pytest.raises(RuntimeError, match="Wildcards are not allowed"):
        load_allowed_origins({CORS_ALLOWED_ORIGINS_FILE: filename})
