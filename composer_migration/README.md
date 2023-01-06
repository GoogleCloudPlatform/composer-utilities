# Composer DAG migration
Date readme last updated: January 5, 2023

## As CLI
### Assumptions
* Assumes Python 3.9 is being used - versions below 3.9 are not tested
* Assumes authentication to gcloud

### Usage
Install the package locally with
`pip install .`

Run `python -m composer_migration --project <YOUR_PROJECT> --source_env <COMPOSER_ENVIRONMENT> --location <GCE_REGION>`

Error message will occur if "affinity" is configured in a dag and will show which dag objects are the problem



### Tests
* Dags used by tests are in the `test_resources` directory

Install pytest with `pip install pytest`

From the top level directory run
`pip install .` to install the package locally
`pytest` to run the tests

### Lint
To run a lint check, install flake8 and flake8 import order
`pip install flake8 flake8-import-order`

then run 
`flake8 src tests --show-source --builtin=gettext --max-complexity=29 --import-order-style=pep8 --ignore=E121,E123,E126,E203,E226,E24,E266,E501,E704,W503,W504,I202 --max-line-length=88`
