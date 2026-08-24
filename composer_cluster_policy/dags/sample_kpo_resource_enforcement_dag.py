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

"""Sample Cloud Composer DAG demonstrating KubernetesPodOperator Resource Policy Enforcement.

This DAG runs a containerized task using the KubernetesPodOperator (KPO).
When deployed to a Cloud Composer environment equipped with `airflow_local_settings.py`,
the Airflow Cluster Policy (`pod_mutation_hook`) intercepts this task before execution,
inspects its requested container resources, clamps any excessive allocations to safe maximums,
and applies corporate governance labels.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

DOC_MD = """
### Sample KubernetesPodOperator Resource Policy Enforcement DAG

This DAG demonstrates:
1. **Standardized Naming Conventions**: Verb-noun task identifiers and categorized metadata tags.
2. **Cluster Policy Interception**: Shows how high CPU (`8000m`) and memory (`16000Mi`) requests
   are intercepted and capped to safe cluster limits by `airflow_local_settings.pod_mutation_hook`.
3. **Cloud Composer Best Practices**:
   - Automated pod cleanup (`is_delete_operator_pod=True`)
   - Direct log streaming (`get_logs=True`)
   - Execution in the isolated `composer-user-workloads` namespace
"""

DEFAULT_ARGS = {
    "owner": "data-platform-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(hours=1),
}


@dag(
    dag_id="sample_kpo_resource_enforcement",
    description="Demonstrates cluster policy enforcement on KubernetesPodOperator workloads",
    doc_md=DOC_MD,
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["domain:data-platform", "pattern:kpo", "policy:enforced"],
    default_args=DEFAULT_ARGS,
)
def sample_kpo_resource_enforcement_dag():
    """Defines the sample KPO workload workflow."""
    KubernetesPodOperator(
        task_id="extract_gcs_storage_metadata",
        name="kpo-extract-storage-metadata",
        image="gcr.io/google.com/cloudsdktool/cloud-sdk:latest",
        cmds=["bash"],
        arguments=[
            "-c",
            "gcloud storage ls --long",
        ],
        namespace="composer-user-workloads",
        is_delete_operator_pod=True,
        get_logs=True,
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        # Example intentional high request to demonstrate policy clamping:
        # 8 cores and 16 GiB memory requested -> clamped by pod_mutation_hook
        container_resources=k8s.V1ResourceRequirements(
            requests={
                "cpu": "8000m",
                "memory": "16000Mi",
            },
            limits={
                "cpu": "8000m",
                "memory": "16000Mi",
            },
        ),
    )


# Instantiate the DAG
sample_kpo_resource_enforcement_dag()
