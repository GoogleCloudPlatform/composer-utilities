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

"""Sample DAG demonstrating 3 core Task-Level anti-patterns for cluster governance.

This DAG complies with DAG-level policies (catchup=False, valid owner),
but demonstrates 3 classic task-level operational anti-patterns:
1. The Hanging Task: Omitted execution_timeout (runs for 30s, hogs worker slot)
2. The Runaway Retries: retries=50 with 0s delay (hammers down external APIs)
3. The Fragile Single-Shot Task: retries=0 on network call (fails on transient GKE glitches)
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
    dag_id="composer_sample_unprotected_task_violations",
    description="Demonstrates 3 classic task-level anti-patterns: hanging timeout, runaway retries, fragile single-shot (Unshielded Baseline)",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=25,
    default_args=DEFAULT_ARGS,
    tags=["domain:data-platform", "pattern:unprotected-baseline"],
)
def sample_task_policy_violations_dag():

    # --------------------------------------------------------------------------
    # Anti-Pattern 1: The Hanging Task (No Execution Timeout)
    # Simulates an unindexed DB query or frozen socket running for 30s.
    # Without task_policy, this runs unchecked, locking the Celery worker slot.
    # With task_policy, it is killed at 10s via AirflowTaskTimeout (SIGTERM).
    # --------------------------------------------------------------------------
    hanging_query = BashOperator(
        task_id="hanging_database_query",
        bash_command=(
            "echo 'Starting long-running database query (simulating 30s lock)...' && "
            "sleep 30 && "
            "echo 'Query finished!'"
        ),
        # execution_timeout intentionally omitted!
    )

    # --------------------------------------------------------------------------
    # Anti-Pattern 2: The Runaway Retries (API DDoS Hammer)
    # Sets 50 retries with 0s retry delay. In an outage, this floods backend APIs.
    # With task_policy, retries are clamped to max 3 with exponential backoff.
    # --------------------------------------------------------------------------
    runaway_retries = BashOperator(
        task_id="runaway_retry_hammer",
        bash_command="echo 'Executing task configured with 50 immediate retries...'",
        retries=50,
        retry_delay=timedelta(seconds=0),
    )

    # --------------------------------------------------------------------------
    # Anti-Pattern 3: Fragile Single-Shot Task (Zero Retries on Network Call)
    # Configured with 0 retries. A single transient GKE node scale-out or network
    # blip fails the entire pipeline.
    # With task_policy, minimum retries (2) are injected for resilience.
    # --------------------------------------------------------------------------
    fragile_call = BashOperator(
        task_id="fragile_transient_call",
        bash_command="echo 'Executing critical network call with zero retry safety net...'",
        retries=0,
    )

    hanging_query >> runaway_retries >> fragile_call


sample_task_policy_violations_dag()
