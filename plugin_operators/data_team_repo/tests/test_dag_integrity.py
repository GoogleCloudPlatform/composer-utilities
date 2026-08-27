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

"""Unit tests for Data Engineering Team DAG integrity & compliance verification."""

import importlib.util
import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Note: Platform plugins must be provided via PYTHONPATH (e.g. export PYTHONPATH=../platform_team_repo/plugins:$PYTHONPATH)
DAGS_DIR = os.path.join(BASE_DIR, "dags")


class TestDataTeamDAGIntegrity(unittest.TestCase):
    """Verifies that all domain data pipelines parse cleanly and comply with platform policies."""

    def test_sample_secure_dataproc_dag_import(self):
        """Loads and verifies sample_secure_dataproc_dag.py."""
        dag_file = os.path.join(DAGS_DIR, "sample_secure_dataproc_dag.py")
        self.assertTrue(os.path.exists(dag_file), f"File {dag_file} does not exist")

        spec = importlib.util.spec_from_file_location(
            "sample_secure_dataproc_dag", dag_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(hasattr(module, "dag"))
        dag_obj = module.dag
        self.assertEqual(dag_obj.dag_id, "sample_secure_dataproc_etl_pipeline")

    def test_sample_guardrail_violation_dag_import(self):
        """Loads and verifies sample_guardrail_violation_dag.py."""
        dag_file = os.path.join(DAGS_DIR, "sample_guardrail_violation_dag.py")
        self.assertTrue(os.path.exists(dag_file), f"File {dag_file} does not exist")

        spec = importlib.util.spec_from_file_location(
            "sample_guardrail_violation_dag", dag_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(hasattr(module, "dag"))
        dag_obj = module.dag
        self.assertEqual(dag_obj.dag_id, "sample_dataproc_guardrail_enforcement_demo")

    def test_guardrail_violation_functions_execute(self):
        """Executes the test callable functions in sample_guardrail_violation_dag to verify guardrails."""
        dag_file = os.path.join(DAGS_DIR, "sample_guardrail_violation_dag.py")
        spec = importlib.util.spec_from_file_location(
            "sample_guardrail_violation_dag", dag_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Execute test functions - should pass without raising unhandled errors
        module.test_public_ip_interception()
        module.test_missing_finops_labels_interception()
        module.test_oversized_quota_interception()


if __name__ == "__main__":
    unittest.main()
