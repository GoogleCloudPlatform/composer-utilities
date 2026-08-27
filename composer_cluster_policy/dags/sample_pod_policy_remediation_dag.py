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

"""Sample DAG demonstrating Pod-Level (pod_mutation_hook) Auto-Remediation.

Demonstrates how the Airflow Cluster Policy `pod_mutation_hook` intercepts
KubernetesPodOperator tasks pre-GKE submission and transparently remediates them:
1. Namespace Overridden: Rerouted from 'unauthorized-tenant-namespace' to 'composer-user-workloads'.
2. Resource Clamping: 8 cores (8000m) clamped to 4 cores (4000m); 16 GiB clamped to 8 GiB (8192Mi).
3. Corporate FinOps Labels: Injects 'managed-by: composer-cluster-policy' and 'policy-enforced: true'.
4. Task Resilience: Retries automatically upgraded to minimum 2 via `task_policy`.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
import os

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT", "composer-utils")

DEFAULT_ARGS = {
    "owner": "data-engineering-team",
    "depends_on_past": False,
    "retries": 1,  # Upgraded to 2 by task_policy for KPO resilience
}

@dag(
    dag_id="sample_pod_policy_remediation",
    description="Demonstrates pod_mutation_hook auto-remediation (namespace override, CPU/RAM clamping, FinOps labels)",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["domain:data-platform", "level:pod", "policy:remediated"],
)
def sample_pod_policy_remediation_dag():

    KubernetesPodOperator(
        task_id="remediated_container_workload",
        name="kpo-remediated-workload",
        image="gcr.io/google.com/cloudsdktool/cloud-sdk:latest",
        cmds=["bash"],
        arguments=[
            "-c",
            f"echo 'Running remediated container workload on project: {PROJECT_ID}' && sleep 5",
        ],
        # Anti-Pattern: Submitted with unauthorized namespace
        # Remediated by pod_mutation_hook -> Overridden to 'composer-user-workloads'
        namespace="unauthorized-tenant-namespace",
        is_delete_operator_pod=True,
        get_logs=True,
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        # Anti-Pattern: Submitted with runaway requests (8 cores, 16 GiB)
        # Remediated by pod_mutation_hook -> Clamped to 4 cores (4000m) and 8 GiB (8192Mi)
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
        # Anti-Pattern: Missing labels
        # Remediated by pod_mutation_hook -> Auto-injected with corporate FinOps labels
    )

sample_pod_policy_remediation_dag()
