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

"""Sample DAG demonstrating automated silent cluster policy remediation.

This DAG complies with hard gatekeeping rules (catchup=False, valid owner),
but intentionally introduces 3 soft operational anti-patterns:
1. Excessive Concurrency: max_active_runs=16 (clamped to 2)
2. Missing Catalog Tags: tags=[] (auto-injected with 'unassigned-domain', 'policy:remediated')
3. Missing Total Duration Ceiling: dagrun_timeout=None (auto-injected with 4h)
"""

from __future__ import annotations

import datetime
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "data-engineering-team",  # Compliant owner
    "retries": 1,
}


@dag(
    dag_id="sample_dag_policy_remediation",
    description="Demonstrates silent cluster policy auto-remediation (concurrency, tags, timeout)",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,  # Compliant catchup
    max_active_runs=16,  # [Anti-Pattern 1] Clamped to 2 by dag_policy
    tags=[],  # [Anti-Pattern 2] Injected with tags by dag_policy
    default_args=DEFAULT_ARGS,
    # dagrun_timeout omitted  # [Anti-Pattern 3] Injected with 4h by dag_policy
)
def sample_dag_policy_remediation_dag():
    BashOperator(
        task_id="demonstrate_remediated_execution",
        bash_command=(
            "echo 'Running pipeline with auto-remediated concurrency, tags, and timeout ceilings!' && sleep 2"
        ),
    )


sample_dag_policy_remediation_dag()

