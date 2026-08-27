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

"""Unit tests for Secure Dataproc Operators execution and lifecycle."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure plugin paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

try:
    from config.cluster_tiers import ClusterTier
    from operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
    from operators.secure_dataproc_operator import (
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )
except ImportError:
    from plugins.config.cluster_tiers import ClusterTier
    from plugins.operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
    from plugins.operators.secure_dataproc_operator import (
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )


class TestSecureDataprocOperators(unittest.TestCase):
    """Tests operator initialization, templating, and execution behavior."""

    def setUp(self):
        self.project_id = "test-project-123"
        self.region = "us-central1"
        self.cluster_name = "test-dataproc-cluster"

    def test_create_cluster_operator_instantiation(self):
        """Verifies operator initializes with compliant defaults."""
        op = SecureDataprocCreateClusterOperator(
            task_id="create_cluster_task",
            project_id=self.project_id,
            region=self.region,
            cluster_name=self.cluster_name,
            tier=ClusterTier.STANDARD_ANALYTICS,
            team="marketing-analytics",
            cost_center="cc-10492",
            environment="production",
            data_classification="confidential",
            idle_delete_ttl_minutes=60,
        )

        self.assertEqual(op.task_id, "create_cluster_task")
        self.assertEqual(op.project_id, self.project_id)
        self.assertEqual(op.region, self.region)
        self.assertEqual(op.cluster_name, self.cluster_name)
        self.assertEqual(op.tier, ClusterTier.STANDARD_ANALYTICS)
        self.assertEqual(op.labels["team"], "marketing-analytics")
        self.assertEqual(op.labels["cost_center"], "cc-10492")
        self.assertEqual(op.labels["environment"], "production")

        # Verify cluster_config generated contains security & lifecycle configurations
        self.assertTrue(op.cluster_config["gce_cluster_config"]["internal_ip_only"])
        self.assertEqual(op.cluster_config["lifecycle_config"]["idle_delete_ttl"], "3600s")

    def test_create_cluster_operator_execution(self):
        """Verifies operator execute method logs audit summary and succeeds."""
        op = SecureDataprocCreateClusterOperator(
            task_id="create_cluster_task",
            project_id=self.project_id,
            region=self.region,
            cluster_name=self.cluster_name,
            tier=ClusterTier.SMALL_ANALYTICS,
            team="marketing-analytics",
            cost_center="cc-10492",
            environment="dev",
        )

        mock_context = MagicMock()
        result = op.execute(mock_context)
        self.assertIsNotNone(result)

    def test_delete_cluster_operator_defaults(self):
        """Verifies delete cluster operator uses trigger_rule='all_done'."""
        op = SecureDataprocDeleteClusterOperator(
            task_id="delete_cluster_task",
            project_id=self.project_id,
            region=self.region,
            cluster_name=self.cluster_name,
        )

        self.assertEqual(op.trigger_rule, "all_done")
        mock_context = MagicMock()
        op.execute(mock_context)

    def test_job_operator_label_injection(self):
        """Verifies submit job operator auto-injects provenance & cost tracking labels."""
        raw_job = {
            "pyspark_job": {
                "main_python_file_uri": "gs://bucket/script.py",
            }
        }
        op = SecureDataprocSubmitJobOperator(
            task_id="submit_job_task",
            project_id=self.project_id,
            region=self.region,
            job=raw_job,
            team="marketing-analytics",
            cost_center="cc-10492",
        )

        self.assertIn("labels", op.job)
        self.assertEqual(op.job["labels"]["team"], "marketing-analytics")
        self.assertEqual(op.job["labels"]["cost_center"], "cc-10492")
        self.assertEqual(op.job["labels"]["managed_by"], "airflow_platform_plugin")


if __name__ == "__main__":
    unittest.main()
