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

"""Platform governance rules and policy definitions for Google Cloud Dataproc."""

from dataclasses import dataclass, field


@dataclass
class PlatformGovernanceRules:
    """Enterprise governance rules enforced by the Platform Engineering team.

    These rules guarantee security compliance, cost control, networking boundaries,
    and metadata standardization across all Dataproc clusters spawned from Airflow.
    """

    # --------------------------------------------------------------------------
    # 1. Cost & Resource Quota Limits
    # --------------------------------------------------------------------------
    max_primary_workers: int = 20
    max_secondary_workers: int = 20
    max_master_nodes: int = 3
    max_boot_disk_size_gb: int = 500
    disallowed_machine_type_prefixes: list[str] = field(
        default_factory=lambda: ["a2-", "g2-", "m1-", "m2-", "m3-"]
    )
    allowed_machine_type_families: list[str] = field(
        default_factory=lambda: ["e2-", "n2-", "n2d-", "n1-", "c2-", "c2d-"]
    )

    # --------------------------------------------------------------------------
    # 2. Security & Network Isolation
    # --------------------------------------------------------------------------
    require_internal_ip_only: bool = True
    enforce_component_gateway: bool = True
    allowed_subnetwork_regex: str = (
        r"^projects/[a-z0-9-]+/regions/[a-z0-9-]+/subnetworks/[a-z0-9-]+$"
    )
    default_subnetwork_template: str = (
        "projects/{project_id}/regions/{region}/subnetworks/default"
    )
    default_service_account_template: str | None = None
    disallowed_service_account_patterns: list[str] = field(
        default_factory=lambda: [
            r".*-compute@developer\.gserviceaccount\.com$",
            r".*@appspot\.gserviceaccount\.com$",
        ]
    )
    mandatory_network_tags: list[str] = field(
        default_factory=lambda: ["dataproc-managed-node", "vpc-analytics-egress"]
    )
    environments_requiring_cmek: list[str] = field(default_factory=list)
    default_cmek_key_template: str | None = None

    # --------------------------------------------------------------------------
    # 3. FinOps & Mandatory Metadata Labels
    # --------------------------------------------------------------------------
    mandatory_labels: list[str] = field(
        default_factory=lambda: [
            "cost_center",
            "team",
            "environment",
            "data_classification",
        ]
    )
    allowed_environments: list[str] = field(
        default_factory=lambda: [
            "dev",
            "development",
            "staging",
            "stage",
            "test",
            "prod",
            "production",
        ]
    )
    allowed_data_classifications: list[str] = field(
        default_factory=lambda: [
            "public",
            "internal",
            "confidential",
            "restricted",
        ]
    )
    platform_injected_labels: dict[str, str] = field(
        default_factory=lambda: {
            "managed_by": "airflow_platform_plugin",
            "platform_version": "1.0.0",
            "provisioner": "cloud_composer",
        }
    )

    # --------------------------------------------------------------------------
    # 4. Lifecycle & Auto-Termination (Idle Cleanup & Max Lifespan)
    # --------------------------------------------------------------------------
    max_idle_delete_ttl_seconds: int = 7200  # 2 Hours max idle
    default_idle_delete_ttl_seconds: int = 3600  # 1 Hour default idle
    max_auto_delete_ttl_seconds: int = 43200  # 12 Hours max absolute lifetime
    default_auto_delete_ttl_seconds: int = 28800  # 8 Hours default lifetime

    # --------------------------------------------------------------------------
    # 5. Software, Image & Initialization Actions
    # --------------------------------------------------------------------------
    allowed_image_versions: list[str] = field(
        default_factory=lambda: [
            "2.2-debian12",
            "2.2-ubuntu22",
            "2.1-debian11",
            "2.1-ubuntu20",
            "2.0-debian10",
        ]
    )
    default_image_version: str = "2.2-debian12"
    mandatory_initialization_actions: list[dict[str, str]] = field(default_factory=list)


# Singleton default platform rules instance
DEFAULT_PLATFORM_RULES = PlatformGovernanceRules()
