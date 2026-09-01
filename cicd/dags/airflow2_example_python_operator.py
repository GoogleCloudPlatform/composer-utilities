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

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago

# Airflow 3 Breaking Changes demonstrated here:
# 1. airflow.operators.python_operator is removed (moved to airflow.operators.python in Airflow 2).
# 2. provide_context=True in PythonOperator is removed (deprecated in Airflow 2).
# 3. execution_date in kwargs is removed (deprecated in Airflow 2, replaced by logical_date).


def print_execution_date(**kwargs):
    # execution_date is no longer passed in Airflow 3
    print(f"The execution date is: {kwargs.get('execution_date')}")


with DAG(
    dag_id="airflow2_example_python_operator",
    schedule_interval="@daily",
    start_date=days_ago(2),
    catchup=False,
    tags=["airflow2", "compatibility_test"],
) as dag:
    print_date = PythonOperator(
        task_id="print_execution_date_task",
        python_callable=print_execution_date,
        provide_context=True,
    )
