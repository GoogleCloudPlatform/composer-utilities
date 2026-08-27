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

"""Sample DAG demonstrating automated task-level cluster policy remediation.

This DAG demonstrates what happens when the cluster policy intercepts task-level anti-patterns:
1. Runaway Retries: Retries clamped from 50 down to 3 to prevent API DDoSing.
2. Standard Step: Injected with default 4-hour execution timeout watchdog.
3. Hanging Task: Injected with a 10s watchdog ceiling, actively killing hung queries at 10s.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "data-engineering-team",
    "depends_on_past": False,
}


@dag(
    dag_id="sample_task_policy_remediation",
    description="Demonstrates task-level cluster policy auto-remediation (watchdogs, retry clamping)",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=25,  # Clamped to 2 by dag_policy
    default_args=DEFAULT_ARGS,
    tags=[],  # Injected with default tags by dag_policy
)
def sample_task_policy_remediation_dag():

    # --------------------------------------------------------------------------
    # 1. Runaway Retries Clamping Showcase
    # Developer set retries=50 with 0s delay.
    # task_policy intercepts this on the worker and clamps retries to 3!
    # --------------------------------------------------------------------------
    clamped_retries = BashOperator(
        task_id="runaway_retries_clamped",
        bash_command="echo 'Executing task originally configured with 50 retries...' && sleep 2",
        retries=50,
        retry_delay=timedelta(seconds=0),
    )

    # --------------------------------------------------------------------------
    # 2. Resilient Standard Task
    # Developer omitted execution_timeout.
    # task_policy injects a safe 4-hour ceiling to prevent hung slots.
    # --------------------------------------------------------------------------
    resilient_task = BashOperator(
        task_id="resilient_standard_task",
        bash_command="echo 'Running standard processing task with auto-injected 4h timeout watchdog...' && sleep 2",
    )

    # --------------------------------------------------------------------------
    # 3. Hanging Task Timeout Watchdog Showcase
    # Simulates an unindexed DB query or frozen socket (sleep 30).
    # task_policy detects 'timeout' in task_id and injects a 10s watchdog!
    # At 10.2s, Airflow sends SIGTERM (AirflowTaskTimeout), killing the hang!
    # --------------------------------------------------------------------------
    watchdog_timeout = BashOperator(
        task_id="hanging_query_timeout_watchdog",
        bash_command=(
            "echo 'Starting long-running database query (simulating 30s hang)...' && "
            "sleep 30 && "
            "echo 'Should not reach here!'"
        ),
    )

    clamped_retries >> resilient_task >> watchdog_timeout


sample_task_policy_remediation_dag()
