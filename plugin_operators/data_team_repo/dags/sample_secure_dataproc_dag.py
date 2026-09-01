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

"""Sample Production DAG for Managed Service for Apache Airflow (formerly Cloud Composer).

Demonstrates the business value of Platform Plugin Operators:
  1. Zero Boilerplate: Data engineers specify only high-level parameters (tier, team, cost center).
  2. Automatic Governance: Operator injects Private IP, VPC Subnet, Service Account, and CMEK.
  3. Automatic Cost Control: Mandatory idle auto-deletion (idle_delete_ttl) prevents zombie cluster spend.
  4. Reliable Teardown: Governed delete operator guarantees cleanup with trigger_rule='all_done'.
"""

import os
from datetime import datetime, timedelta, timezone

try:
    from airflow import DAG
    from airflow.operators.empty import EmptyOperator
except ImportError:
    # Standalone mock fallback for parsing / unit testing
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

    class EmptyOperator:
        def __init__(self, task_id, **kwargs):
            self.task_id = task_id

        def __rshift__(self, other):
            return other

        def __lshift__(self, other):
            return self


try:
    from operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
    from operators.secure_dataproc_operator import (
        ClusterTier,
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )
except ImportError:
    from plugins.operators.dataproc_job_operator import (
        SecureDataprocSubmitJobOperator,
    )
    from plugins.operators.secure_dataproc_operator import (
        ClusterTier,
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )

# ------------------------------------------------------------------------------
# DAG Configuration
# ------------------------------------------------------------------------------
GCP_PROJECT_ID = (
    os.environ.get("GCP_PROJECT")
    or os.environ.get("GCLOUD_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "my-project-59523-test1-pp"
)
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")
CLUSTER_NAME = "analytics-batch-{{ ds_nodash }}"

default_args = {
    "owner": "marketing-analytics-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ------------------------------------------------------------------------------
# PySpark Job Definition (Uses built-in Dataproc SparkPi script)
# ------------------------------------------------------------------------------
PYSPARK_JOB = {
    "reference": {"project_id": GCP_PROJECT_ID},
    "placement": {
        # Using templated CLUSTER_NAME guarantees 100% compatibility across Airflow 2.x and 3.x
        "cluster_name": CLUSTER_NAME,
    },
    "pyspark_job": {
        # file:// points to the standard PySpark Pi example pre-installed on all Dataproc nodes
        "main_python_file_uri": "file:///usr/lib/spark/examples/src/main/python/pi.py",
        "args": ["1000"],
        "properties": {
            "spark.executor.memory": "2g",
            "spark.driver.memory": "2g",
            "spark.dynamicAllocation.enabled": "true",
        },
    },
}

# ------------------------------------------------------------------------------
# Governed Pipeline Definition
# ------------------------------------------------------------------------------
with DAG(
    dag_id="sample_secure_dataproc_etl_pipeline",
    default_args=default_args,
    description="Enterprise Governed Dataproc ETL Pipeline in Managed Service for Apache Airflow",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    tags=["dataproc", "platform_governed", "marketing_analytics", "etl"],
) as dag:
    start_pipeline = EmptyOperator(task_id="start_pipeline")

    # 1. Platform-Governed Dataproc Cluster Creation
    # Notice: DAG author writes 10 lines instead of 120 lines of raw Protobuf/dictionary.
    # Security (Private IP, Subnet, SA), FinOps labels, and Idle TTL are enforced by the plugin operator!
    create_dataproc_cluster = SecureDataprocCreateClusterOperator(
        task_id="create_governed_dataproc_cluster",
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
        cluster_name=CLUSTER_NAME,
        tier=ClusterTier.STANDARD_ANALYTICS,  # Standard 4-worker + 2-spot-worker tier
        team="marketing-analytics",
        cost_center="cc-10492",
        environment="production",
        data_classification="confidential",
        idle_delete_ttl_minutes=60,  # Auto-terminate if idle for 60 minutes
        auto_delete_ttl_hours=8,  # Max absolute lifetime of 8 hours
        optional_components=["JUPYTER"],
    )

    # 2. Governed PySpark Job Submission
    # Automatically injects provenance tracking labels (DAG ID, Task ID, Cost Center)
    run_pyspark_transformation = SecureDataprocSubmitJobOperator(
        task_id="run_pyspark_daily_aggregation",
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
        job=PYSPARK_JOB,
        cost_center="cc-10492",
        team="marketing-analytics",
    )

    # 3. Guaranteed Teardown
    # Uses trigger_rule="all_done" to guarantee deletion even if the PySpark job fails
    delete_dataproc_cluster = SecureDataprocDeleteClusterOperator(
        task_id="delete_dataproc_cluster",
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
        cluster_name=CLUSTER_NAME,
        trigger_rule="all_done",
    )

    end_pipeline = EmptyOperator(task_id="end_pipeline")

    # Task Dependencies
    (
        start_pipeline
        >> create_dataproc_cluster
        >> run_pyspark_transformation
        >> delete_dataproc_cluster
        >> end_pipeline
    )
