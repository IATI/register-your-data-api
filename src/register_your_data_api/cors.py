"""Cross-Origin Resource Sharing (CORS) configuration.

The allowed origins have to be read before the FastAPI app object is handed to uvicorn,
because Starlette refuses to add middleware once an application has started - and that
includes the lifespan in which the Context is built.  This module therefore reads the
environment directly rather than going through Context.
"""

import json
import os
import re
from typing import Final

import dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

CORS_ALLOWED_ORIGINS_FILE: Final[str] = "CORS_ALLOWED_ORIGINS_FILE"

# The verbs the API serves, and no others.
ALLOWED_METHODS: Final[list[str]] = ["GET", "POST", "PATCH", "PUT", "DELETE"]

ALLOWED_HEADERS: Final[list[str]] = ["Authorization", "Content-Type"]

# Scheme, host and an optional port, and nothing else.  Browsers send an Origin header in
# exactly this form and CORSMiddleware compares it by string equality, so an entry with a
# trailing slash, a path, or an upper case host would silently never match.  A wildcard is
# rejected by this pattern too: a single "*" entry would switch CORSMiddleware into
# allow-all mode, which is precisely what we are avoiding.
_ORIGIN_PATTERN: Final[re.Pattern[str]] = re.compile(r"https?://[a-z0-9.-]+(:[0-9]+)?")


def get_environment_config(env_file: str = ".env") -> dict[str, str]:
    """Read configuration with the same precedence as Context: the env file, then os.environ.

    Parameters
    ----------
    env_file : str
        Path to the environment file.  A missing file is not an error, in which case only
        os.environ is used.

    Returns
    -------
    dict[str, str]
    """

    env: dict[str, str] = {key: value for key, value in dotenv.dotenv_values(env_file).items() if value is not None}
    env.update(os.environ)

    return env


def load_allowed_origins(env: dict[str, str] | None = None) -> list[str]:
    """Load the origins the API will accept cross-origin requests from.

    Parameters
    ----------
    env : dict[str, str] | None
        Environment variables to read the configuration from.  Defaults to the values
        returned by get_environment_config().

    Returns
    -------
    list[str]
        The configured origins, or an empty list if CORS_ALLOWED_ORIGINS_FILE is not set,
        in which case no cross-origin requests are allowed at all.

    Raises
    ------
    RuntimeError
        If CORS_ALLOWED_ORIGINS_FILE is set but the file it names cannot be read, is not
        valid JSON, or does not contain a list of well formed origins.
    """

    if env is None:
        env = get_environment_config()

    filename = env.get(CORS_ALLOWED_ORIGINS_FILE, "").strip()

    if not filename:
        return []

    origins = _read_origins_file(filename)

    if not isinstance(origins, list):
        raise RuntimeError(f"CORS allowed origins file {filename} must contain a JSON list of origins")

    invalid_origins = [origin for origin in origins if not _is_valid_origin(origin)]

    if invalid_origins:
        raise RuntimeError(
            f"CORS allowed origins file {filename} contains invalid origins: {invalid_origins}.  Each must be "
            "of the form scheme://host[:port], lower case, with no trailing slash and no path.  Wildcards are "
            "not allowed."
        )

    return origins


def add_cors_middleware(app: FastAPI, allowed_origins: list[str]) -> None:
    """Add CORS middleware to a FastAPI app instance.

    Preflight OPTIONS requests are answered by this middleware before the router, and so
    before the per-endpoint Security() dependencies, which is what stops browsers being
    given a 401 for a preflight.

    Note that CORS is enforced by the browser, not by us: a request from an origin that is
    not allowed is still served as normal, it just comes back without the headers the
    browser needs in order to hand the response to the calling script.

    An empty list registers no middleware at all, so a deployment that has not opted into
    CORS is left exactly as it was.  Registering the middleware with an empty allowlist
    would not be equivalent: it would still intercept preflights, answering OPTIONS with a
    400 where the router would previously have returned 405.

    Parameters
    ----------
    app : FastAPI
    allowed_origins : list[str]
        Origins to accept cross-origin requests from.  An empty list disables CORS.
    """

    if not allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
    )


def _read_origins_file(filename: str) -> object:
    """Read and parse the JSON origins file, translating any failure into a RuntimeError."""

    try:
        with open(filename, "r") as file:
            return json.load(file)
    except OSError as err:
        raise RuntimeError(f"Could not read CORS allowed origins file {filename}: {err}") from err
    except ValueError as err:
        # Covers json.JSONDecodeError and the UnicodeDecodeError raised when the file is
        # not readable as text; both are ValueError subclasses.
        raise RuntimeError(f"CORS allowed origins file {filename} is not valid JSON: {err}") from err


def _is_valid_origin(origin: object) -> bool:
    """Check that a single entry from the origins file is an origin we can match against."""

    return isinstance(origin, str) and _ORIGIN_PATTERN.fullmatch(origin) is not None
