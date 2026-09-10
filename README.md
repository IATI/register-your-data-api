# IATI Register Your Data (API)

## Summary

 Product  | IATI Register Your Data (API) 
--- | ---
Description | The Register Your Data product is an API and web app design to make write changes into the new IATI Registry.  This repository contains a FastAPI application 
Website | None 
Related |
Documentation | Rest of README.md
Technical Issues | [GitHub issues page](https://github.com/IATI/register-your-data-api/issues) 
Support | [IATI Support Website](https://iatistandard.org/en/guidance/get-support/) 

## High-level requirements

* Python 3.12.11
* Docker
* OpenSSL (or similar) to generate public/private key pairs for the audit log (on a local development instance, if necessary).

## Running

### Overview

Currently, the API application requires the following resources to run:

* A JSON Web Key Set server: the configuration details for the production server can be obtained from `https://api.eu.asgardeo.io/t/iati/oauth2/token/.well-known/openid-configuration` but in the future we should define a local IDP, such as [SIOCODE-Open/local-idp](https://github.com/SIOCODE-Open/local-idp), for local development and/or integration testing.
* Public/private key pair to encrypt the audit log (only the public key is required for running the application).  These can be generated with OpenSSL using `openssl genrsa -out private-key.pem 4096 && openssl rsa -in private-key.pem -pubout -out public-key.pem`.
* `.env` configuration file (see `.env.example` and a description of the variables below).

The API application is NOT currently wired up to the CRM.

### Configuration

The application is configured using a set of environment variables in a `.env` file.  The application looks in the current directory for this file.

| Variable                    | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `JWKS_URI`                  | URI for the JWKS, typically this should be obtained from `https://api.eu.asgardeo.io/t/iati/oauth2/token/.well-known/openid-configuration` or the Asgardeo console. |
| `ACCESS_CHECK_ENDPOINT`     | `True` enables the `/api/v1/access_check` endpoint to enable applications to check that the API can be called using an access token. |
| `APP_LOG_LEVEL`             | Log level for the application diagnostic log (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, or `"CRITICAL"` to match the [standard Python logging levels](https://docs.python.org/3/library/logging.html#levels)). |
| `APP_LOG_PATH`              | Location for the application diagnostic log.                 |
| `AUDIT_LOG_PATH`            | Location for the audit log.                                  |
| `AUDIT_LOG_PUBLIC_KEY_PATH` | Path to the public key for encrypting audit logs.            |
| `PROMETHEUS_PORT`           | Port to serve Prometheus metrics from.                       |
| `JWT_AUDIENCE`              | Audience that we expect to find in JWTs from the identity server. |
| `SENTRY_DSN`                | DSN of the Sentry project to report errors to.  **Optional** — leave empty or unset and Sentry is not initialised, and the application runs normally. |
| `SENTRY_ENVIRONMENT`        | Environment name that events are tagged with in Sentry, e.g. `"dev"` or `"prod"`.  Defaults to `"local-development"` rather than the SDK's own default of `"production"`, so that an unconfigured environment can never be mistaken for the live one. |
| `SENTRY_TRACES_SAMPLE_RATE` | Proportion of requests traced for performance monitoring, `0.0`–`1.0`.  Defaults to `1.0`; lower it (e.g. `0.1`) if trace volume becomes a problem. |

### Error monitoring with Sentry

Sentry is initialised in `src/main.py` by `register_your_data_api.sentry.setup_sentry()`,
before the FastAPI application object is created, so that its Starlette/FastAPI
integrations are in place.  It reports unhandled exceptions and traces requests.

Configuration is read directly from the environment rather than through `Context`,
because `Context` is not created until the application lifespan runs, which is after the
SDK has to be initialised.  Sentry is optional by design: error reporting should never be
the reason the API fails to start, so a missing DSN disables it rather than raising, and
so does a DSN the SDK rejects as malformed — `sentry_sdk.init` raises `BadDsn` for those,
which would otherwise stop the process at import time before there is a logger to report
it to.

The test suite must not report to a real project.  It imports `src/main.py` through
`tests/helpers/mocking.py`, so `setup_sentry()` runs during collection and a developer's
`.env` would otherwise point the suite's deliberately-provoked errors — and a transaction
per request — at whichever project that DSN names.  `tests/conftest.py` empties
`SENTRY_DSN` for the session, which is the SDK's own way of being switched off.

`include_local_variables=False` because otherwise Sentry would attach the local 
variables of every stack frame to an event, and this application's credentials reach 
the stack in forms which cannot all be recognised by name: an ASGI frame's locals hold 
the raw `scope`/`request` objects, whose headers are a list of `(bytes, bytes)` tuples 
rather than a named field, and the bearer token is a local variable in `auth/authn.py` 
in its own right as well as a field of `UserAndCredentials`.  Local variables are 
therefore not sent at all, which costs the variable values in a traceback but keeps
the file, line, function and source line of every frame.  With frame locals enabled
a live bearer token is transmitted in the event payload .

`send_default_pii=False` keeps cookies and the client IP address out of events, and the
`EventScrubber` denylist in `sentry.py` withholds this application's own secrets by name
wherever the SDK collects them by other means.

Be careful about what `send_default_pii=False` does **not** do, because the option name
suggests more than it delivers:

* It does not keep request **headers** out of events.  The SDK substitutes the sensitive
  ones and passes the rest through, so `host`, `user-agent` and `content-type` are sent.
  The `Authorization` header is withheld by the scrubber's `authorization` denylist entry,
  not by this option.
* It does not keep request **bodies** out of events — the SDK collects those regardless of
  it, bounded by `max_request_body_size`.  Because tracing is enabled the body rides out
  on the transaction event for **successful** requests too, so a `POST` creating a
  reporting org would have transmitted its `contact_email` on every call.
  `max_request_body_size="never"` is what actually withholds them.

Deciding that a variable holds a credential is still a manual step:
`tests/unit/test_sentry.py::test_sentry_scrubs_every_configuration_variable_which_looks_like_a_secret`
is a backstop that catches the common cases by name fragment, but a credential with an
unremarkable name would satisfy it.

Sentry also records the query string of every outgoing HTTP request, with the values
intact.  This application queries SuiteCRM by building record filters into the query
string, so those values carry the IDs of the people and organisations a request touched;
`before_breadcrumb` and `before_send_transaction` withhold them.  The method, the URL
without its query string and the response status are kept, so a breadcrumb still says
which request was being made.

**The audit log is never sent to Sentry.**  Sentry turns any log record of `ERROR` or
above into an event, and the audit log is written at `CRITICAL` for authentication
failures — where `auth/authn.py` records the contents of the `Authorization` header,
including the credential itself, for a request whose scheme is not `bearer`.  Sending
those records to a third party in plain text would defeat the point of encrypting the
audit log at rest, so `sentry.py` calls both `ignore_logger()` and
`ignore_logger_for_sentry_logs()` for it — the SDK keeps two separate ignore lists and
the first covers only events and breadcrumbs.  Sentry Logs are off, so the second call
changes nothing today; it is there so that enabling them later cannot silently start
sending the audit log.  The application's diagnostic log is still reported, which is 
how application code reports errors without referencing the SDK.

### FineGrainedAuthorisation database migrations

The FineGrainedAuthorisation system uses a postgres database. Migrations are
handled using alembic. Alembic is configured using the `pyproject.toml` file. If
the FGA models change or new ones are added, you can get alembic to generate a
migration file with the following command:

```bash
alembic -c pyproject.toml revision --autogenerate -m "Commit message"
```

**Note:** `alembic` cannot autogenerate the sqlalchemy commands or SQL code for
every type of migration, so after it has autogenerated a migration, check the
newly created file in `alembic/versions` to see what migration code is has
created and if it is adequate.

The database is not currently automatically migrated whenever FastAPI starts, as
this is not best practice. To migrate the database when a version is released,
the following command (suiteable for CI/CD pipelines) can be used:

```bash
alembic -c pyproject.toml upgrade head
```

If you need to reset the database (will likely cause data loss) to the initial
state, you can use the command:

```bash
alembic -c pyproject.toml downgrade base
```


### Running locally in development mode

To run the API locally in development mode execute the following from the command line.

```
fastapi dev src/main.py
```

This uses the [FastAPI CLI](https://fastapi.tiangolo.com/fastapi-cli/) with a built-in [uvicorn ASGI server](https://fastapi.tiangolo.com/deployment/manually/#use-the-fastapi-run-command).  To run locally in production mode change `dev` to `run`.

### Running in production mode from a Docker container

The docker container can be built with:

```
docker build . --tag rydapi
```

Running the API in production can be run directly from its Docker container with:

```
docker run \
  --mount type=bind,source=.env,target=/api/.env,readonly \
  --mount type=bind,source=./logs/,target=/api/logs/ \
  --mount type=bind,source=./keys/,target=/api/keys/,readonly \
  -p 8000:8000 \
  -p 9000:9000 \
  rydapi
```

This performs the following setup:
* `--mount type=bind,source=.env,target=/api/.env,readonly`: shares `.env` configuration file on the host with the container.
* `--mount type=bind,source=./logs/,target=/api/logs/`: allows the container to write logs to the /logs directory on the host.
* `--mount type=bind,source=./keys/,target=/api/keys/,readonly`: shares the `/keys` directory on the host with the container so public and private keys can be used by the container.
* `-p 8000:8000`: shares port 8000 for API traffic.
* `-p 9000:9000`: shares port 9000 for Prometheus metrics (assuming that this is the port as specified by the `.env` file.)

Care should be taken to make sure that the `.env` variables match the log (`APP_LOG_PATH` and `AUDIT_LOG_PATH`) and key directories (`AUDIT_LOG_PUBLIC_KEY_PATH`) and the Prometheus metric port (`PROMETHEUS_PORT`).

## Development

### Adding new dependencies

New dependencies are added to `pyproject.toml`.  Once these have been added `requirements.txt` and/or `requirements_dev.txt` need to be regenerated.  With:

```
pip-compile --all-build-deps --strip-extras
```

and/or

```
pip-compile --extra=dev --output-file=requirements_dev.txt --strip-extras
```

Note that the two commands take different options, so run each as given above rather than
applying one set of flags to both files.  The command line recorded at the top of each
generated file is the authoritative record of how that file was built.

**Regenerate on Linux, not on macOS.**  `pip-compile` resolves for the platform it runs on and
has no cross-platform mode, so a macOS run silently drops dependencies that the deployment
target needs.  SQLAlchemy, for example, requires `greenlet` on `x86_64` and `aarch64` but not
on Apple Silicon's `arm64`, so a run on an M-series Mac omits it and loses the pin.  

### Checking and linting

Linting is setup with `isort` and `black` and checked with `flake8`.  Static type checking is performed by `mypy`.  Configurations are stored in `pyproject.toml`.  To use these linters and checkers you will first need to install the development dependencies:

```
pip install -r requirements_dev.txt
```

Then the code can be linted with:

```
black .
isort .
```

And checked with flake8 and mypy:

```
flake8
mypy .
```

### Security testing
Static Security Application Testing is performed with `bandit`.  To use this tool you must also install the development dependencies and then test with:

```
bandit -c pyproject.toml -r .
```

### Versioning

The version is set in `pyproject.toml`.  When making updates, set the version to an appropriate value.  The version is fixed to 0.1.0 until we have a working API on a dev instance (albeit with mocked data).


## Audit Log Viewer

There is a command line application which can be used to decrypt and print the encrypted audit log files. This is primarily useful for use while development. This is the `audit_log_viewer.py` file.

### Configuration

The `audit_log_viewer.py` cli is configured using the following environment variables:

```shell
AUDIT_LOG_PATH=/path/to/log/file
AUDIT_LOG_PRIVATE_KEY_PATH=/path_to_private_key
```

These values will be automatically loaded from a `.env` in the root of the repository.

### Use

To display the audit log file configured by `AUDIT_LOG_PATH` use:

```bash
python src/audit_log_viewer.py
```

To decrypt and print log lines from `stdin` use:

```bash
python src/audit_log_viewer.py --use-stdin
```

The latter allows you to `tail -f` the encrypted log file and pipe it into the viewer.

## License
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.
    
    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

