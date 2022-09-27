## Developing this application

### Prerequisites

 * Python version: application has been tested on python version 3.10
 * Composer version:  compatible with both Composer 1 and Composer 2
 * Composer version:  compatible with all Composer configurations
 * GCP IAM Permissions: executing user needs composer.environments.get [permission](https://cloud.google.com/composer/docs/how-to/access-control#permissions_for_api_methods)

### Clone repository

Clone the code from GitHub to your local machine

### Getting the correct version of python with pyenv

Install [pyenv](https://github.com/pyenv/pyenv).

Use pyenv to install a suitable version of python, e.g. 3.10.0
```shell
pyenv install 3.10.0    
```

Use pyenv to switch to python 3.10.0
```shell
pyenv shell 3.10.0
```

### Create a virtual environment with venv module

```shell
python -m venv venv
```

activate the virtual environment
```shell
source venv/bin/activate
```
check that we are using the Python of the virtual environment
```
which python
.../cloudcomposerdiff/venv/bin/python
```

### Install the package in editable mode

Install the package locally within the created virtual environment.

Do so in "editable mode" so that the package will reflect code changes.

Navigate to the directory containing pyproject.toml

Install all the dependcies end-users would get when running pip install

```
python -m pip install --editable .
```
Install additional dev only dependencies that end-users do not get
```shell
python -m pip install --editable .[dev]
```

with the above done, running the package will include code changes. This can
be used for testing during development.
```
cloudcomposerdiff \
--env1_project_id <> \
--env1_location <> \
--env1_name <> \
--env2_project_id <> \
--env2_location <> \
--env2_name <>
```
### Run tests w/ pytest

Navigate to the directory containing pyproject.toml
```shell
pytest
```

### Sort imports with isort

Navigate to the directory containing pyproject.toml

Apply the sort to all files recurisvely

```shell
isort . --profile=black
```

### Format the code with black

Navigate to the directory containing pyproject.toml

Apply the formatter to all files recurisvely

```shell
black .
```

### Lint the code

Navigate to the directory containing pyproject.toml

Lint the code

```shell
flake8 src tests --show-source --builtin=gettext --max-complexity=29 --import-order-style=pep8 --ignore=E121,E123,E126,E203,E226,E24,E266,E501,E704,W503,W504,I202 --max-line-length=88
```

### Adding futher dependencies

Do not add dependencies by editing the requirements.txt file.

Please edit the pyproject.toml file.

For end-user dependencies edit the project.dependencies section.

For dev-only edit project.optional-dependencies.dev section.

### Update requirements.txt

Do not manually update requirements.txt

Use a pip-tools command to sync pyproject.toml to requirements.txt
```shell
pip-compile pyproject.toml
```

### Update the version number of the package

Use bumpver to incrase the verion number

A MAJOR.MINOR.PATCH approach is used to versioning

E.g. to preview an increase to minor 

```shell
bumpver update --minor --dry
```

E.g. to actually increase minor 

```shell
bumpver update --minor
```

bumpver will go and update the verion number wherever it appears in the package.