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

"""Sample Anti-Pattern DAG demonstrating Level 1 (dag_policy) governance violations.

This DAG intentionally violates all 5 major DAG-level governance standards:
1. Missing DAG-level run timeout (`dagrun_timeout=None`): Risks unbounded multi-task hangs.
2. Excessive concurrency (`max_active_runs=16`): Risks bombarding databases with simultaneous runs.
3. Invalid owner (`owner="root"`): Unattributable orphan DAG with no team contact.
4. Missing tags (`tags=[]`): Completely untagged, cluttering multi-tenant UI.
5. Dangerous catchup flood (`catchup=True` with past start_date): Triggers historical backfills.
"""

from __future__ import annotations

import datetime

from airflow.decorators import dag
from airflow.operators.bash import BashOperator

# Anti-Pattern 1 & 3: Invalid root owner, no dagrun_timeout
DEFAULT_ARGS = {
    "owner": "root",  # Violation 3: Unapproved root ownership
    "retries": 0,
}


@dag(
    dag_id="sample_dag_policy_violations",
    description="Anti-pattern DAG demonstrating 5 major Level 1 governance violations",
    schedule="@daily",
    start_date=datetime.datetime(2026, 8, 20),
    catchup=True,  # Violation 5: Dangerous backfill flood
    max_active_runs=16,  # Violation 2: Excessive active concurrent runs
    tags=[],  # Violation 4: Zero ownership/domain tags
    default_args=DEFAULT_ARGS,
    # dagrun_timeout omitted (Violation 1: Uncapped total pipeline runtime)
)
def sample_dag_policy_violations_dag():
    BashOperator(
        task_id="sample_audit_step",
        bash_command="echo 'Executing partition step for date: {{ ds }}' && sleep 2",
    )


sample_dag_policy_violations_dag()
