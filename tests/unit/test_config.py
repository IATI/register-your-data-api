"""Tests for configuration read straight from the environment.

Sentry and CORS both rely on this, because each is configured before the Context exists.
"""

from pathlib import Path

import pytest

from register_your_data_api.config import get_environment_config

SOME_VARIABLE = "SOME_VARIABLE"


def test_environment_config_reads_the_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # os.environ wins over the file, so a real variable of this name in the ambient
    # environment would mask what this test is checking.
    monkeypatch.delenv(SOME_VARIABLE, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text('SOME_VARIABLE="a-value"\n')

    env = get_environment_config(str(env_file))

    assert env[SOME_VARIABLE] == "a-value"


def test_environment_config_prefers_os_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('SOME_VARIABLE="from-the-env-file"\n')

    monkeypatch.setenv(SOME_VARIABLE, "from-os-environ")

    env = get_environment_config(str(env_file))

    assert env[SOME_VARIABLE] == "from-os-environ"


def test_environment_config_tolerates_a_missing_env_file(tmp_path: Path) -> None:
    env = get_environment_config(str(tmp_path / "does-not-exist"))

    assert isinstance(env, dict)
