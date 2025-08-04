import io
import itertools

import pytest

import register_your_data_api.util as util


def test_empty_env_vars() -> None:
    """Test that an empty .env file is caught properly"""
    context = util.Context(logs_to_stdout=True)
    env_mock = io.StringIO()
    with pytest.raises(RuntimeError) as exc_info:
        context._load_and_validate_env(env_mock)
    assert str(exc_info.value) == "No environment variables found"


def test_missing_env_vars() -> None:
    """Test that missing required variable errors in .env are caught and logged properly"""
    REQUIRED_VARS = util.Context._REQUIRED_ENV_VARS
    context = util.Context(logs_to_stdout=True)
    env_mock = io.StringIO()

    for test_keys in itertools.combinations(REQUIRED_VARS, len(REQUIRED_VARS) - 1):
        key_not_included = list(set(REQUIRED_VARS).difference(test_keys))[0]

        for key in test_keys:
            env_mock.write(f'{key} = "abcdef123"\n')
        env_mock.seek(0)

        with pytest.raises(RuntimeError) as exc_info:
            context._load_and_validate_env(env_mock)

        assert str(exc_info.value) == f"Environment variables missing {key_not_included} variable"

        env_mock.truncate(0)
        env_mock.seek(0)
        context._env = {}
