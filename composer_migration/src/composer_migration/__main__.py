# Copyright 2023 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import logging
import subprocess
import tempfile
import os
import sys

from composer_migration.lib.strategies.migrate_kubernetes_pod_operator_ast import (
    CheckKubernetesPodOperator,
)
from composer_migration.lib.comparator import DAGsComparator
from google.cloud.orchestration.airflow import service_v1
from google.api_core.exceptions import InvalidArgument


def run_checks(gcp_project: str, composer_environment: str, location: str) -> None:
    # get bucket where dags are stored with the Composer client library
    try:
        composer_env_info = service_v1.EnvironmentsClient().get_environment(
            request=service_v1.GetEnvironmentRequest(
                name=f"projects/{gcp_project}/locations/{location}/environments/{composer_environment}"
            )
        )
        logging.debug(composer_env_info)
        dags_bucket = composer_env_info.config.dag_gcs_prefix
        logging.debug(dags_bucket)
    except InvalidArgument:
        raise

    # store dags locally in a temp directory
    temp_dag_dir = tempfile.mkdtemp()
    try:
        # Use the gsutil -m flag to parallelize the cp process
        subprocess.check_call(
            ["gsutil", "-m", "cp", "-r", f"{dags_bucket}/*.py", temp_dag_dir]
        )
        # remove Airflow monitoring dag - this is not user maintained
        os.remove(f"{temp_dag_dir}/airflow_monitoring.py")
    except subprocess.CalledProcessError:
        raise

    comparator: DAGsComparator = DAGsComparator(temp_dag_dir)
    comparator.check_dag_files(strategy=CheckKubernetesPodOperator)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="What Composer environment to check?")
    parser.add_argument(
        "--project",
        type=str,
        help="Name of GCP project containing your Composer environment",
    )
    parser.add_argument(
        "--source_env", type=str, help="Name of the Composer environment to upgrade"
    )
    parser.add_argument(
        "--location",
        type=str,
        help="GCE region where the Composer environment is located",
    )

    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        logging.basicConfig(level=logging.DEBUG)
        run_checks(args.project, args.source_env, args.location)
