"""
 Copyright 2022 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

import click
from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.comparator import EnvironmentComparator
from cloudcomposerdiff.lib.service import GCPComposerService
from cloudcomposerdiff.lib.strategies.diff_airflow_config import \
    DiffAirflowConfig
from cloudcomposerdiff.lib.strategies.diff_env_image import DiffEnvImage
from cloudcomposerdiff.lib.strategies.diff_env_variables import \
    DiffEnvVariables
from cloudcomposerdiff.lib.strategies.diff_pypi_packages import \
    DiffPyPiPackages

from . import __version__


@click.option(
    "--env1_project_id",
    type=str,
    help="Project ID for Cloud Composer Environment #1",
    required=True,
)
@click.option(
    "--env1_location",
    type=str,
    help="Compute Engine region for Cloud Composer Environment #1",
    required=True,
)
@click.option(
    "--env1_name",
    type=str,
    help="Name for Cloud Composer Environment #1",
    required=True,
)
@click.option(
    "--env2_project_id",
    type=str,
    help="Project ID for Cloud Composer Environment #2",
    required=True,
)
@click.option(
    "--env2_location",
    type=str,
    help="Compute Engine region for Cloud Composer Environment #2",
    required=True,
)
@click.option(
    "--env2_name",
    type=str,
    help="Name for Cloud Composer Environment #2",
    required=True,
)
@click.option(
    "--json_output", is_flag=True, help="If provided, the output will be JSON"
)
@click.version_option(version=__version__)
@click.command()
def main(
    env1_project_id: str,
    env1_location: str,
    env1_name: str,
    env2_project_id: str,
    env2_location: str,
    env2_name: str,
    json_output: bool,
):
    """The cloudcomposerdiff tool for comparing Cloud Composer environments."""

    env1_service: GCPComposerService = GCPComposerService(
        env1_project_id, env1_location, env1_name
    )
    env1: service_v1.types.Environment = env1_service.fetch_env()
    env2_service: GCPComposerService = GCPComposerService(
        env2_project_id, env2_location, env2_name
    )
    env2: service_v1.types.Environment = env2_service.fetch_env()
    comparator: EnvironmentComparator = EnvironmentComparator(env1, env2)
    comparator.compare_environments(strategy=DiffEnvImage())
    comparator.compare_environments(strategy=DiffAirflowConfig())
    comparator.compare_environments(strategy=DiffPyPiPackages())
    comparator.compare_environments(strategy=DiffEnvVariables())

    if json_output:
        # user has selected to get output as JSON for storage or piping elsewhere
        comparator.output_diffs_as_json()
    else:
        # user has chosen to get human readable output in the terminal
        click.echo("Welcome to Cloud Composer Diff")
        click.echo(
            f"Composer Environment 1 : {env1_project_id} {env1_location} {env1_name}"
        )
        click.echo(
            f"Composer Environment 2 : {env2_project_id} {env2_location} {env2_name}"
        )
        comparator.output_diffs_to_console()


if __name__ == "__main__":
    # When executing this package via
    # python -m cloudcomposerdiff
    # __main__.py acts as the entry point of this program
    main()
