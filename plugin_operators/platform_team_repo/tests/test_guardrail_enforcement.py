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

"""Unit tests for platform guardrail and policy enforcement."""

import os
import sys
import unittest

# Ensure plugin paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

try:
    from config.cluster_tiers import ClusterTier
    from config.governance_rules import DEFAULT_PLATFORM_RULES, PlatformGovernanceRules
    from exceptions.policy_violations import (
        DataprocPolicyViolationException,
        LifecyclePolicyViolationException,
        MandatoryLabelMissingException,
        NetworkPolicyViolationException,
        ResourceQuotaExceededException,
        SecurityPolicyViolationException,
    )
    from operators.secure_dataproc_operator import SecureDataprocCreateClusterOperator
except ImportError:
    from plugins.config.cluster_tiers import ClusterTier
    from plugins.config.governance_rules import DEFAULT_PLATFORM_RULES, PlatformGovernanceRules
    from plugins.exceptions.policy_violations import (
        DataprocPolicyViolationException,
        LifecyclePolicyViolationException,
        MandatoryLabelMissingException,
        NetworkPolicyViolationException,
        ResourceQuotaExceededException,
        SecurityPolicyViolationException,
    )
    from plugins.operators.secure_dataproc_operator import SecureDataprocCreateClusterOperator


class TestGuardrailEnforcement(unittest.TestCase):
    """Tests verification and rejection of policy-violating configurations."""

    def setUp(self):
        self.project_id = "analytics-prod-123"
        self.region = "us-central1"
        self.cluster_name = "test-governed-cluster"

    # --------------------------------------------------------------------------
    # 1. Security Guardrails
    # --------------------------------------------------------------------------

    def test_reject_public_ip_configuration(self):
        """Guardrail: Prohibits clusters configured with external/public IPs."""
        with self.assertRaises(SecurityPolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_public_ip",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                cluster_config={
                    "gce_cluster_config": {
                        "internal_ip_only": False,
                    }
                },
            )
        self.assertIn("RULE_SEC_001", str(ctx.exception))
        self.assertIn("internal_ip_only", str(ctx.exception))

    def test_reject_default_compute_service_account(self):
        """Guardrail: Rejects default GCE Compute Engine service account."""
        with self.assertRaises(SecurityPolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_bad_sa",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                service_account="123456789-compute@developer.gserviceaccount.com",
            )
        self.assertIn("RULE_SEC_002", str(ctx.exception))
        self.assertIn("DISALLOWED_DEFAULT_SERVICE_ACCOUNT", str(ctx.exception))

    def test_reject_unapproved_image_version(self):
        """Guardrail: Rejects unapproved or legacy Dataproc image versions."""
        with self.assertRaises(SecurityPolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_bad_image",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                image_version="1.5-debian10",  # Legacy / unsupported version
            )
        self.assertIn("RULE_SEC_004", str(ctx.exception))
        self.assertIn("UNAPPROVED_IMAGE_VERSION", str(ctx.exception))

    def test_cmek_injection_when_configured(self):
        """Guardrail: Injects enterprise CMEK encryption key when configured."""
        custom_rules = PlatformGovernanceRules(
            environments_requiring_cmek=["production"],
            default_cmek_key_template="projects/{project_id}/locations/{region}/keyRings/dataproc-keyring/cryptoKeys/dataproc-cmek-key",
        )
        op = SecureDataprocCreateClusterOperator(
            task_id="test_prod_cmek",
            project_id=self.project_id,
            region=self.region,
            cluster_name=self.cluster_name,
            team="analytics",
            cost_center="cc-100",
            environment="production",
            governance_rules=custom_rules,
        )
        encryption = op.cluster_config.get("encryption_config", {})
        self.assertIn("gce_pd_kms_key_name", encryption)
        self.assertIn("dataproc-cmek-key", encryption["gce_pd_kms_key_name"])

    # --------------------------------------------------------------------------
    # 2. Resource Quotas & Sizing Guardrails
    # --------------------------------------------------------------------------

    def test_reject_excessive_primary_workers(self):
        """Guardrail: Caps primary worker count at platform maximum (20)."""
        with self.assertRaises(ResourceQuotaExceededException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_excess_workers",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                cluster_config={
                    "worker_config": {
                        "num_instances": 50,
                    }
                },
            )
        self.assertIn("RULE_QUOTA_002", str(ctx.exception))
        self.assertIn("EXCESSIVE_WORKER_COUNT", str(ctx.exception))

    def test_reject_disallowed_gpu_machine_types(self):
        """Guardrail: Rejects unauthorized expensive GPU/TPU machine types."""
        with self.assertRaises(ResourceQuotaExceededException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_gpu_machine",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                cluster_config={
                    "worker_config": {
                        "machine_type_uri": "a2-highgpu-1g",
                    }
                },
            )
        self.assertIn("RULE_QUOTA_004", str(ctx.exception))
        self.assertIn("DISALLOWED_MACHINE_TYPE", str(ctx.exception))

    def test_reject_invalid_master_node_count(self):
        """Guardrail: Rejects invalid master node counts (must be 1 or 3)."""
        with self.assertRaises(ResourceQuotaExceededException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_invalid_masters",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                cluster_config={
                    "master_config": {
                        "num_instances": 2,  # Invalid: must be 1 or 3
                    }
                },
            )
        self.assertIn("RULE_QUOTA_001", str(ctx.exception))
        self.assertIn("INVALID_MASTER_NODE_COUNT", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 3. FinOps & Metadata Labels Guardrails
    # --------------------------------------------------------------------------

    def test_reject_missing_team_label(self):
        """Guardrail: Requires non-empty team metadata."""
        with self.assertRaises(MandatoryLabelMissingException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_missing_team",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="",
                cost_center="cc-100",
                environment="dev",
            )
        self.assertIn("RULE_FIN_001", str(ctx.exception))
        self.assertIn("MANDATORY_TEAM_LABEL", str(ctx.exception))

    def test_reject_missing_cost_center_label(self):
        """Guardrail: Requires non-empty cost center code."""
        with self.assertRaises(MandatoryLabelMissingException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_missing_cc",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="",
                environment="dev",
            )
        self.assertIn("RULE_FIN_002", str(ctx.exception))
        self.assertIn("MANDATORY_COST_CENTER_LABEL", str(ctx.exception))

    def test_reject_invalid_environment(self):
        """Guardrail: Validates environment matches approved values."""
        with self.assertRaises(MandatoryLabelMissingException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_invalid_env",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="invalid_sandbox_env",
            )
        self.assertIn("RULE_FIN_003", str(ctx.exception))
        self.assertIn("INVALID_ENVIRONMENT_LABEL", str(ctx.exception))

    def test_label_sanitization(self):
        """Validates that labels with uppercase/special chars are sanitized for GCP."""
        op = SecureDataprocCreateClusterOperator(
            task_id="test_label_sanitization",
            project_id=self.project_id,
            region=self.region,
            cluster_name=self.cluster_name,
            team="Marketing Analytics Team!",
            cost_center="CC-9080_US",
            environment="DEV",
            labels={"Custom_Key": "Value 123!"},
        )
        self.assertEqual(op.labels["team"], "marketing-analytics-team-")
        self.assertEqual(op.labels["cost_center"], "cc-9080_us")
        self.assertEqual(op.labels["environment"], "dev")
        self.assertEqual(op.labels["custom_key"], "value-123-")
        self.assertEqual(op.labels["managed_by"], "airflow_platform_plugin")

    # --------------------------------------------------------------------------
    # 4. Lifecycle & Auto-Delete Guardrails
    # --------------------------------------------------------------------------

    def test_reject_excessive_idle_ttl(self):
        """Guardrail: Rejects idle delete TTL exceeding platform maximum (2 hours)."""
        with self.assertRaises(LifecyclePolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_excess_ttl",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                idle_delete_ttl_minutes=180,  # 3 hours > 2 hours max
            )
        self.assertIn("RULE_LIFE_002", str(ctx.exception))
        self.assertIn("IDLE_TTL_EXCEEDS_MAXIMUM", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 5. Network & Subnetwork Guardrails
    # --------------------------------------------------------------------------

    def test_reject_invalid_subnetwork_format(self):
        """Guardrail: Rejects non-compliant subnetwork URI format."""
        with self.assertRaises(NetworkPolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="test_invalid_subnet",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="analytics",
                cost_center="cc-100",
                environment="dev",
                subnetwork="default",  # Not a fully qualified subnetwork URI
            )
        self.assertIn("RULE_NET_001", str(ctx.exception))
        self.assertIn("SUBNETWORK_VALIDATION", str(ctx.exception))


class TestActionableErrorMessagesDisplay(unittest.TestCase):
    """Tests that verify fail-fast guardrails intercept violations and print structured remediation messages."""

    def setUp(self):
        self.project_id = "analytics-prod-123"
        self.region = "us-central1"
        self.cluster_name = "test-fail-fast-cluster"

    def test_print_actionable_error_message_public_ip_violation(self):
        """Demonstrates the formatted Actionable Error Message printed when Public IP is requested."""
        with self.assertRaises(SecurityPolicyViolationException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="insecure_public_ip_cluster",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="marketing-analytics",
                cost_center="cc-10492",
                environment="dev",
                cluster_config={
                    "gce_cluster_config": {
                        "internal_ip_only": False,
                    }
                },
            )
        # Print the formatted message if SHOW_BANNER=1 is requested
        if os.getenv("SHOW_BANNER") == "1":
            print(f"\n[DEMO ACTIONABLE ERROR OUTPUT - RULE_SEC_001]:{ctx.exception}\n")
        self.assertIn("RULE_SEC_001", str(ctx.exception))
        self.assertIn("PRIVATE_IP_ONLY_ENFORCEMENT", str(ctx.exception))
        self.assertIn("internal_ip_only must be True", str(ctx.exception))

    def test_print_actionable_error_message_missing_finops_label(self):
        """Demonstrates the formatted Actionable Error Message printed when FinOps labels are missing."""
        with self.assertRaises(MandatoryLabelMissingException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="unattributed_cluster",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="marketing-analytics",
                cost_center="",  # Missing required FinOps cost center
                environment="dev",
            )
        if os.getenv("SHOW_BANNER") == "1":
            print(f"\n[DEMO ACTIONABLE ERROR OUTPUT - RULE_FIN_002]:{ctx.exception}\n")
        self.assertIn("RULE_FIN_002", str(ctx.exception))
        self.assertIn("MANDATORY_COST_CENTER_LABEL", str(ctx.exception))

    def test_print_actionable_error_message_oversized_quota(self):
        """Demonstrates the formatted Actionable Error Message printed when resource quota is exceeded."""
        with self.assertRaises(ResourceQuotaExceededException) as ctx:
            SecureDataprocCreateClusterOperator(
                task_id="oversized_cluster",
                project_id=self.project_id,
                region=self.region,
                cluster_name=self.cluster_name,
                team="marketing-analytics",
                cost_center="cc-10492",
                environment="dev",
                cluster_config={
                    "worker_config": {
                        "num_instances": 100,  # Exceeds platform limit of 20
                    }
                },
            )
        if os.getenv("SHOW_BANNER") == "1":
            print(f"\n[DEMO ACTIONABLE ERROR OUTPUT - RULE_QUOTA_002]:{ctx.exception}\n")
        self.assertIn("RULE_QUOTA_002", str(ctx.exception))
        self.assertIn("EXCESSIVE_WORKER_COUNT", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

