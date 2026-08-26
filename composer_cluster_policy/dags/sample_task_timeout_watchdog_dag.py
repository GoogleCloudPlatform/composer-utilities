# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Sample Cloud Composer DAG demonstrating Task Execution Timeout Watchdog Policy Enforcement.

This DAG simulates a slow or hanging query (30s duration) where the developer omitted
an `execution_timeout`. When deployed to an environment with `airflow_local_settings.py`,
the cluster policy automatically injects a watchdog timeout to protect worker slots.
"""

from __future__ import annotations

import datetime
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

@dag(
    dag_id="sample_task_timeout_watchdog",
    description="Demonstrates cluster policy automatic execution_timeout watchdog enforcement",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    tags=["domain:data-platform", "pattern:timeout-watchdog", "policy:enforced"],
)
def sample_task_timeout_watchdog_dag():
    # Simulates an unindexed database query or frozen API socket that runs for 30s.
    # The developer omitted 'execution_timeout'.
    # The Cluster Policy (task_policy) automatically injects a 10s execution_timeout watchdog!
    BashOperator(
        task_id="sample_timeout_hanging_query",
        bash_command=(
            "echo 'Starting long-running database query...' && "
            "sleep 30 && "
            "echo 'Query finished successfully!'"
        ),
    )

sample_task_timeout_watchdog_dag()
