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
import re
import tempfile
import os
import sys

from composer_migration.lib.strategies.migrate_kubernetes_pod_operator_ast import (
    CheckKubernetesPodOperator,
)
from composer_migration.lib.comparator import DAGComparator


def run_checks(gcp_project, composer_environment, location):
    # get bucket where dags are stored
    try:
        composer_env_info = subprocess.run(
            [
                "gcloud",
                "composer",
                "environments",
                "describe",
                composer_environment,
                "--project",
                gcp_project,
                "--location",
                location,
            ],
            capture_output=True,
        )
        # using the format filter does not work properly with subprocess so we have to use regex
        logging.debug(composer_env_info)
        dags_bucket = re.findall(r"gs:\/\/\S*\/dags", str(composer_env_info.stdout))
        logging.debug(dags_bucket)
        dags_bucket = dags_bucket[0]
    except subprocess.CalledProcessError:
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

    comparator: DAGComparator = DAGComparator(temp_dag_dir)
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
        run_checks(args.project, args.source_env, args.location)
