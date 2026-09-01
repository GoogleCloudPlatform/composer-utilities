# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryInsertJobOperator,
    BigQueryValueCheckOperator,
)


def get_destination_table(job_id: str) -> str:
    from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

    hook = BigQueryHook()
    client = hook.get_client()
    job = client.get_job(job_id)
    dest = job.destination
    return f"{dest.project}.{dest.dataset_id}.{dest.table_id}"


with DAG(
    dag_id="bq_1000_queries_slow_parse",
    schedule=None,
    start_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
    catchup=False,
    tags=["bigquery", "load_test", "antipattern"],
    user_defined_macros={"get_destination_table": get_destination_table},
) as dag:
    # Antipattern: Using a Python loop to statically generate 1000 separate tasks
    # This bloats the DAG definition size and makes the Airflow UI very slow to load
    # The purpose of this DAG is to show how NOT to write this type of DAG.
    for i in range(1000):
        emit_number = BashOperator(
            task_id=f"emit_number_{i}",
            bash_command=f"echo {i}",
            do_xcom_push=True,
        )

        run_query = BigQueryInsertJobOperator(
            task_id=f"run_select_{i}",
            configuration={
                "query": {
                    "query": f"SELECT {{{{ ti.xcom_pull(task_ids='emit_number_{i}') }}}}",
                    "useLegacySql": False,
                }
            },
        )

        check_value = BigQueryValueCheckOperator(
            task_id=f"check_value_{i}",
            sql=f"SELECT * FROM `{{{{ get_destination_table(ti.xcom_pull(task_ids='run_select_{i}')) }}}}`",
            pass_value=i,
            use_legacy_sql=False,
        )

        print_result = BashOperator(
            task_id=f"print_result_{i}",
            bash_command=f"echo {{{{ ti.xcom_pull(task_ids='run_select_{i}') }}}}",
        )

        emit_number >> run_query >> check_value >> print_result
