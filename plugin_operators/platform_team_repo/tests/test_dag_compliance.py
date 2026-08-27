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

"""Platform Governance Test Suite: Domain DAG Compliance & Raw Operator Linter.

Maintained 100% by the Platform Engineering team in platform_team_repo.
Enforces via CI/CD static scanning that domain DAGs cannot bypass plugin operators.
"""

import os
import sys
import unittest

# Prevent bytecode generation
sys.dont_write_bytecode = True

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)


class TestPlatformDAGCompliance(unittest.TestCase):
    """Platform-owned test suite verifying static policy enforcement on domain DAGs."""

    def setUp(self):
        self.domain_dags_dir = os.path.abspath(
            os.path.join(BASE_DIR, "..", "data_team_repo", "dags")
        )

    def _get_domain_dag_contents(self):
        """Helper to retrieve Python files and their contents from the domain DAGs directory."""
        if not os.path.exists(self.domain_dags_dir):
            return []
        dag_files = []
        for root, _, files in os.walk(self.domain_dags_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        dag_files.append((file, f.read()))
        return dag_files

    def test_scan_domain_dags_for_raw_cluster_operator_imports(self):
        """Platform Policy Linter: Blocks raw DataprocCreateClusterOperator imports in domain DAGs."""
        for file_name, content in self._get_domain_dag_contents():
            if (
                "airflow.providers.google.cloud.operators.dataproc" in content
                and "DataprocCreateClusterOperator" in content
                and "SecureDataprocCreateClusterOperator" not in content
            ):
                self.fail(
                    f"Platform Policy Violation in {file_name}: Direct use of DataprocCreateClusterOperator is forbidden. "
                    f"Please import and use SecureDataprocCreateClusterOperator."
                )

    def test_scan_domain_dags_for_raw_job_operator_imports(self):
        """Platform Policy Linter: Blocks raw DataprocSubmitJobOperator imports without secure plugin."""
        for file_name, content in self._get_domain_dag_contents():
            if (
                "airflow.providers.google.cloud.operators.dataproc" in content
                and "DataprocSubmitJobOperator" in content
                and "SecureDataprocSubmitJobOperator" not in content
            ):
                self.fail(
                    f"Platform Policy Violation in {file_name}: Direct use of DataprocSubmitJobOperator is forbidden. "
                    f"Please import and use SecureDataprocSubmitJobOperator."
                )

    def test_scan_domain_dags_for_hardcoded_security_bypass(self):
        """Platform Policy Linter: Ensures no domain DAGs hardcode public IP bypasses."""
        for file_name, content in self._get_domain_dag_contents():
            # In sample_guardrail_violation_dag.py, this is tested inside a test function that asserts an exception
            # Real DAG definitions outside violation demo functions should not have raw public IP configs
            if (
                file_name != "sample_guardrail_violation_dag.py"
                and "internal_ip_only=False" in content.replace(" ", "")
            ):
                self.fail(
                    f"Platform Policy Violation in {file_name}: Attempting to disable private IP enforcement "
                    f"(internal_ip_only=False) is forbidden."
                )


if __name__ == "__main__":
    unittest.main()
