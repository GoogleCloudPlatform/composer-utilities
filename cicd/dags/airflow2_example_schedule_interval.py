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
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.dates import days_ago

# Airflow 3 Breaking Changes demonstrated here:
# 1. schedule_interval argument is removed in Airflow 3. Use schedule instead.
# 2. airflow.utils.dates.days_ago is removed in Airflow 3.
# 3. DummyOperator from airflow.operators.dummy_operator is removed in Airflow 3.
with DAG(
    dag_id="airflow2_example_schedule_interval",
    schedule_interval="@daily",
    start_date=days_ago(2),
    catchup=False,
    tags=["airflow2", "compatibility_test"],
) as dag:
    start = DummyOperator(task_id="start_task")

    end = DummyOperator(task_id="end_task")

    start >> end
