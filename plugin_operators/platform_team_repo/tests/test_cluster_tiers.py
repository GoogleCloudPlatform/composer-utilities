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

"""Unit tests for Cluster Tier definitions and Configuration Builder."""

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
    from config.cluster_tiers import (
        ClusterConfigBuilder,
        ClusterTier,
        TIER_DEFINITIONS,
        TierSpecification,
    )
    from config.governance_rules import DEFAULT_PLATFORM_RULES, PlatformGovernanceRules
except ImportError:
    from plugins.config.cluster_tiers import (
        ClusterConfigBuilder,
        ClusterTier,
        TIER_DEFINITIONS,
        TierSpecification,
    )
    from plugins.config.governance_rules import DEFAULT_PLATFORM_RULES, PlatformGovernanceRules


class TestClusterTiers(unittest.TestCase):
    """Tests for predefined cluster tier templates and configuration builder."""

    def setUp(self):
        self.rules = PlatformGovernanceRules()
        self.project_id = "test-project-123"
        self.region = "us-central1"

    def test_tier_enum_values(self):
        """Validates all expected tier enum values exist."""
        self.assertEqual(ClusterTier.DEV_SINGLE_NODE.value, "dev_single_node")
        self.assertEqual(ClusterTier.SMALL_ANALYTICS.value, "small_analytics")
        self.assertEqual(ClusterTier.STANDARD_ANALYTICS.value, "standard_analytics")
        self.assertEqual(ClusterTier.HIGH_MEMORY_ETL.value, "high_memory_etl")
        self.assertEqual(ClusterTier.CUSTOM_GUARDED.value, "custom_guarded")

    def test_dev_single_node_tier_config(self):
        """Validates single node dev tier builds with 0 workers and tight TTLs."""
        config = ClusterConfigBuilder.build_config(
            tier=ClusterTier.DEV_SINGLE_NODE,
            project_id=self.project_id,
            region=self.region,
            rules=self.rules,
        )

        # Master config
        self.assertEqual(config["master_config"]["num_instances"], 1)
        self.assertEqual(config["master_config"]["machine_type_uri"], "e2-standard-4")
        self.assertEqual(config["master_config"]["disk_config"]["boot_disk_size_gb"], 50)

        # Worker config should be absent for single-node
        self.assertNotIn("worker_config", config)

        # Security & Network
        self.assertTrue(config["gce_cluster_config"]["internal_ip_only"])
        self.assertIn("projects/test-project-123/regions/us-central1/subnetworks/", config["gce_cluster_config"]["subnetwork_uri"])
        self.assertEqual(config["endpoint_config"]["enable_http_port_access"], True)

        # Lifecycle
        self.assertEqual(config["lifecycle_config"]["idle_delete_ttl"], "1800s")
        self.assertEqual(config["lifecycle_config"]["auto_delete_ttl"], "14400s")

    def test_standard_analytics_tier_config(self):
        """Validates standard analytics tier with 4 primary + 2 spot workers."""
        config = ClusterConfigBuilder.build_config(
            tier=ClusterTier.STANDARD_ANALYTICS,
            project_id=self.project_id,
            region=self.region,
            rules=self.rules,
        )

        self.assertEqual(config["master_config"]["num_instances"], 1)
        self.assertEqual(config["master_config"]["machine_type_uri"], "n2-standard-8")
        self.assertEqual(config["worker_config"]["num_instances"], 4)
        self.assertEqual(config["worker_config"]["machine_type_uri"], "n2-standard-8")
        self.assertEqual(config["secondary_worker_config"]["num_instances"], 2)
        self.assertTrue(config["secondary_worker_config"]["is_preemptible"])

    def test_high_memory_etl_tier_config(self):
        """Validates HA 3-master high-memory ETL tier."""
        config = ClusterConfigBuilder.build_config(
            tier=ClusterTier.HIGH_MEMORY_ETL,
            project_id=self.project_id,
            region=self.region,
            rules=self.rules,
        )

        self.assertEqual(config["master_config"]["num_instances"], 3)
        self.assertEqual(config["master_config"]["machine_type_uri"], "n2-highmem-8")
        self.assertEqual(config["worker_config"]["num_instances"], 8)
        self.assertEqual(config["secondary_worker_config"]["num_instances"], 4)

    def test_custom_overrides_deep_merge(self):
        """Validates that custom overrides are merged cleanly into the config."""
        custom_overrides = {
            "software_config": {
                "properties": {
                    "spark:spark.executor.cores": "4",
                }
            },
            "gce_cluster_config": {
                "metadata": {
                    "custom-env": "staging",
                }
            }
        }
        config = ClusterConfigBuilder.build_config(
            tier=ClusterTier.SMALL_ANALYTICS,
            project_id=self.project_id,
            region=self.region,
            rules=self.rules,
            custom_overrides=custom_overrides,
        )

        self.assertEqual(config["software_config"]["properties"]["spark:spark.executor.cores"], "4")
        self.assertEqual(config["gce_cluster_config"]["metadata"]["custom-env"], "staging")
        self.assertEqual(config["gce_cluster_config"]["metadata"]["enable-oslogin"], "true")


if __name__ == "__main__":
    unittest.main()
