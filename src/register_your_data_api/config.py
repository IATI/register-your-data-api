"""Configuration read straight from the environment.

Both Sentry and CORS have to be configured before the FastAPI application object is
created, which is earlier than the ``Context`` (created in the application lifespan)
exists.  They therefore read the environment here rather than going through ``Context``,
using the same precedence that ``Context`` uses: values from the ``.env`` file in the
current directory, overridden by real environment variables.
"""

import os

import dotenv


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
