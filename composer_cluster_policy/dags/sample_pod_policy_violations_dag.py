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

"""Sample DAG demonstrating Pod-Level (KubernetesPodOperator) Anti-Patterns.

Demonstrates 3 classic pod-level operational & FinOps anti-patterns:
1. Unapproved Namespace: Targets an unmanaged/unauthorized tenant namespace.
2. Runaway Container Sizing: Requests 8 cores (8000m) and 16 GiB RAM (16000Mi),
   risking GKE node pool exhaustion and massive compute bills.
3. Missing FinOps Metadata: Zero corporate tracking labels on the pod spec.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
import os

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get(
    "GOOGLE_CLOUD_PROJECT", "composer-utils"
)

DEFAULT_ARGS = {
    "owner": "data-engineering-team",
    "depends_on_past": False,
    "retries": 0,  # Anti-pattern: No retries for container lifecycle events
}


@dag(
    dag_id="composer_sample_unprotected_pod_violations",
    description="Demonstrates 3 pod-level anti-patterns: unapproved namespace, runaway CPU/RAM, missing labels",
    schedule=None,
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["domain:data-platform", "pattern:unprotected-baseline", "level:pod"],
)
def sample_pod_policy_violations_dag():

    KubernetesPodOperator(
        task_id="unprotected_container_workload",
        name="kpo-unprotected-workload",
        image="gcr.io/google.com/cloudsdktool/cloud-sdk:latest",
        cmds=["bash"],
        arguments=[
            "-c",
            f"echo 'Running unshielded container workload on {PROJECT_ID}' && sleep 5",
        ],
        # Anti-Pattern 1: Disallowed or unmanaged namespace
        namespace="unauthorized-tenant-namespace",
        is_delete_operator_pod=True,
        get_logs=True,
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        # Anti-Pattern 2: Runaway resource sizing (8 cores, 16 GiB)
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
        # Anti-Pattern 3: Zero labels provided (omitted)
    )


sample_pod_policy_violations_dag()
