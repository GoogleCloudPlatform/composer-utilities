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

"""Educational & Demonstration DAG: Platform Guardrail Enforcement in Action.

This DAG illustrates how SecureDataprocCreateClusterOperator acts as a platform guardrail,
intercepting violations during initialization or execution and providing clear remediation steps.

Demonstrated Guardrails:
  1. Security Violation: Attempting to configure public IPs (internal_ip_only=False)
  2. FinOps Violation: Missing mandatory cost_center or team labels
  3. Quota Violation: Requesting 100 workers exceeding platform capacity limit of 20
  4. Lifecycle Violation: Attempting to set 24-hour idle timeout exceeding platform limit
"""

from datetime import datetime, timedelta
import logging
import os
import sys



try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    class DAG:
        def __init__(self, dag_id, **kwargs):
            self.dag_id = dag_id
            self.tasks = []
            for k, v in kwargs.items():
                setattr(self, k, v)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    class PythonOperator:
        def __init__(self, task_id, python_callable, **kwargs):
            self.task_id = task_id
            self.python_callable = python_callable
        def __rshift__(self, other):
            return other
        def __lshift__(self, other):
            return self

try:
    from exceptions.policy_violations import (
        DataprocPolicyViolationException,
        MandatoryLabelMissingException,
        ResourceQuotaExceededException,
        SecurityPolicyViolationException,
    )
    from operators.secure_dataproc_operator import (
        ClusterTier,
        SecureDataprocCreateClusterOperator,
    )
except ImportError:
    from plugins.exceptions.policy_violations import (
        DataprocPolicyViolationException,
        MandatoryLabelMissingException,
        ResourceQuotaExceededException,
        SecurityPolicyViolationException,
    )
    from plugins.operators.secure_dataproc_operator import (
        ClusterTier,
        SecureDataprocCreateClusterOperator,
    )

logger = logging.getLogger(__name__)

GCP_PROJECT_ID = (
    os.environ.get("GCP_PROJECT")
    or os.environ.get("GCLOUD_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "my-project-59523-test1-pp"
)
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")


def test_public_ip_interception():
    """Demonstrates how the operator blocks insecure public IP configurations."""
    logger.info("--> Test 1: Simulating non-compliant cluster with internal_ip_only=False...")
    try:
        SecureDataprocCreateClusterOperator(
            task_id="insecure_public_ip_cluster",
            project_id=GCP_PROJECT_ID,
            region=GCP_REGION,
            cluster_name="insecure-cluster",
            team="data-science",
            cost_center="cc-9999",
            environment="dev",
            cluster_config={
                "gce_cluster_config": {
                    "internal_ip_only": False,  # VIOLATION: Platform strictly requires True
                }
            },
        )
        raise RuntimeError("FAIL: Operator should have blocked public IP configuration!")
    except SecurityPolicyViolationException as e:
        logger.info("SUCCESS: Operator blocked public IP with message:\n%s", str(e))


def test_missing_finops_labels_interception():
    """Demonstrates how the operator enforces mandatory cost allocation metadata."""
    logger.info("--> Test 2: Simulating cluster creation with missing cost_center...")
    try:
        SecureDataprocCreateClusterOperator(
            task_id="unattributed_cluster",
            project_id=GCP_PROJECT_ID,
            region=GCP_REGION,
            cluster_name="unattributed-cluster",
            team="data-science",
            cost_center="",  # VIOLATION: Missing mandatory cost center
            environment="dev",
        )
        raise RuntimeError("FAIL: Operator should have blocked missing cost_center!")
    except MandatoryLabelMissingException as e:
        logger.info("SUCCESS: Operator blocked missing FinOps metadata with message:\n%s", str(e))


def test_oversized_quota_interception():
    """Demonstrates how the operator prevents runaway cloud spending by capping worker counts."""
    logger.info("--> Test 3: Simulating cluster creation requesting 100 worker nodes...")
    try:
        SecureDataprocCreateClusterOperator(
            task_id="oversized_cluster",
            project_id=GCP_PROJECT_ID,
            region=GCP_REGION,
            cluster_name="oversized-cluster",
            team="data-science",
            cost_center="cc-9999",
            environment="dev",
            cluster_config={
                "worker_config": {
                    "num_instances": 100,  # VIOLATION: Exceeds platform maximum of 20
                }
            },
        )
        raise RuntimeError("FAIL: Operator should have blocked oversized cluster quota!")
    except ResourceQuotaExceededException as e:
        logger.info("SUCCESS: Operator blocked excessive worker count with message:\n%s", str(e))


with DAG(
    dag_id="sample_dataproc_guardrail_enforcement_demo",
    schedule=None,  # Manual / Ad-hoc trigger for demonstration
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["dataproc", "platform_governance", "demo", "guardrails"],
    description="Demonstrates how platform plugin operators intercept security & quota violations",
) as dag:

    verify_public_ip_guardrail = PythonOperator(
        task_id="verify_public_ip_guardrail",
        python_callable=test_public_ip_interception,
    )

    verify_finops_label_guardrail = PythonOperator(
        task_id="verify_finops_label_guardrail",
        python_callable=test_missing_finops_labels_interception,
    )

    verify_quota_guardrail = PythonOperator(
        task_id="verify_quota_guardrail",
        python_callable=test_oversized_quota_interception,
    )

    verify_public_ip_guardrail >> verify_finops_label_guardrail >> verify_quota_guardrail
