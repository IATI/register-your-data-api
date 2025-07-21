# IATI Register Your Data (API)

## Summary

 Product  | IATI Register Your Data (API) 
--- | ---
Description | The Register Your Data product is an API and web app design to make write changes into the new IATI Registry. 
Website | None 
Related |  
Documentation | Rest of README.md
Technical Issues | [GitHub issues page](https://github.com/IATI/register-your-data-api/issues) 
Support | [IATI Support Website](https://iatistandard.org/en/guidance/get-support/) 

## High-level requirements

* Python 3.12.11

## Development

### Adding new dependencies

New dependencies are added to `pyproject.toml`.  Once these have been added `requirements.txt` and/or `requirements_dev.txt` need to be regenerated.  With:

```
pip-compile --output-file=requirements.txt --strip-extras
```

and/or

```
pip-compile --extra=dev --output-file=requirements_dev.txt --strip-extras
```

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
bandit -r src/
bandit -r tests/
```

### Versioning

The version is set in `pyproject.toml`.  When making updates, set the version to an appropriate value.


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

