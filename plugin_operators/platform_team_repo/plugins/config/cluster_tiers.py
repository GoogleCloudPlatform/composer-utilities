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

"""Standardized cluster tier definitions and configuration builders."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from config.governance_rules import PlatformGovernanceRules
except ImportError:
    try:
        from plugins.config.governance_rules import PlatformGovernanceRules
    except ImportError:
        try:
            from governance_rules import PlatformGovernanceRules
        except (ImportError, ValueError):
            from .governance_rules import PlatformGovernanceRules


class ClusterTier(str, Enum):
    """Predefined, platform-approved cluster sizing templates."""

    DEV_SINGLE_NODE = "dev_single_node"
    SMALL_ANALYTICS = "small_analytics"
    STANDARD_ANALYTICS = "standard_analytics"
    HIGH_MEMORY_ETL = "high_memory_etl"
    CUSTOM_GUARDED = "custom_guarded"


@dataclass
class TierSpecification:
    """Detailed specifications for a cluster tier template."""

    master_num_instances: int
    master_machine_type: str
    master_disk_size_gb: int
    worker_num_instances: int
    worker_machine_type: str
    worker_disk_size_gb: int
    secondary_worker_num_instances: int = 0
    secondary_worker_is_preemptible: bool = True
    default_idle_delete_ttl_seconds: int = 3600
    default_auto_delete_ttl_seconds: int = 28800
    description: str = ""


TIER_DEFINITIONS: dict[ClusterTier, TierSpecification] = {
    ClusterTier.DEV_SINGLE_NODE: TierSpecification(
        master_num_instances=1,
        master_machine_type="e2-standard-4",
        master_disk_size_gb=50,
        worker_num_instances=0,
        worker_machine_type="e2-standard-4",
        worker_disk_size_gb=50,
        secondary_worker_num_instances=0,
        default_idle_delete_ttl_seconds=1800,  # 30 mins
        default_auto_delete_ttl_seconds=14400,  # 4 hours
        description="Single-node dev cluster for unit testing, script prototyping, and low-cost development.",
    ),
    ClusterTier.SMALL_ANALYTICS: TierSpecification(
        master_num_instances=1,
        master_machine_type="n2-standard-4",
        master_disk_size_gb=100,
        worker_num_instances=2,
        worker_machine_type="n2-standard-4",
        worker_disk_size_gb=100,
        secondary_worker_num_instances=0,
        default_idle_delete_ttl_seconds=3600,  # 1 hour
        default_auto_delete_ttl_seconds=28800,  # 8 hours
        description="Lightweight 2-worker cluster for hourly batch jobs and light analytical queries.",
    ),
    ClusterTier.STANDARD_ANALYTICS: TierSpecification(
        master_num_instances=1,
        master_machine_type="n2-standard-8",
        master_disk_size_gb=200,
        worker_num_instances=4,
        worker_machine_type="n2-standard-8",
        worker_disk_size_gb=200,
        secondary_worker_num_instances=2,  # 2 spot/preemptible workers for cost optimization
        secondary_worker_is_preemptible=True,
        default_idle_delete_ttl_seconds=5400,  # 90 mins
        default_auto_delete_ttl_seconds=28800,  # 8 hours
        description="Standard production tier with 4 primary + 2 spot workers for enterprise ETL pipelines.",
    ),
    ClusterTier.HIGH_MEMORY_ETL: TierSpecification(
        master_num_instances=3,  # High Availability (HA) master setup
        master_machine_type="n2-highmem-8",
        master_disk_size_gb=300,
        worker_num_instances=8,
        worker_machine_type="n2-highmem-8",
        worker_disk_size_gb=300,
        secondary_worker_num_instances=4,
        secondary_worker_is_preemptible=True,
        default_idle_delete_ttl_seconds=7200,  # 2 hours
        default_auto_delete_ttl_seconds=43200,  # 12 hours
        description="High-availability, high-memory cluster for heavy Spark aggregations, ML feature engineering.",
    ),
}


class ClusterConfigBuilder:
    """Builds a compliant GCP Dataproc v1 cluster_config dictionary from platform tier templates and overrides."""

    @staticmethod
    def build_config(
        tier: ClusterTier,
        project_id: str,
        region: str,
        rules: PlatformGovernanceRules,
        subnetwork_uri: str | None = None,
        service_account: str | None = None,
        idle_delete_ttl_seconds: int | None = None,
        auto_delete_ttl_seconds: int | None = None,
        image_version: str | None = None,
        cmek_kms_key: str | None = None,
        optional_components: list[str] | None = None,
        spark_properties: dict[str, str] | None = None,
        custom_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assembles a hardened, standardized cluster configuration."""

        # 1. Resolve subnetwork and service account
        resolved_subnetwork = subnetwork_uri
        if not resolved_subnetwork and rules.default_subnetwork_template and project_id:
            resolved_subnetwork = rules.default_subnetwork_template.format(
                project_id=project_id, region=region
            )

        resolved_service_account = service_account
        if (
            not resolved_service_account
            and rules.default_service_account_template
            and project_id
        ):
            resolved_service_account = rules.default_service_account_template.format(
                project_id=project_id
            )

        # 2. Base configuration dictionary
        gce_cluster_config: dict[str, Any] = {
            "internal_ip_only": rules.require_internal_ip_only,
            "tags": list(rules.mandatory_network_tags),
            "metadata": {
                "enable-oslogin": "true",
                "managed-by": "airflow-platform-plugin",
            },
        }
        if resolved_subnetwork:
            gce_cluster_config["subnetwork_uri"] = resolved_subnetwork
        if resolved_service_account:
            gce_cluster_config["service_account"] = resolved_service_account
            gce_cluster_config["service_account_scopes"] = [
                "https://www.googleapis.com/auth/cloud-platform"
            ]

        config: dict[str, Any] = {
            "endpoint_config": {
                "enable_http_port_access": rules.enforce_component_gateway,
            },
            "gce_cluster_config": gce_cluster_config,
            "software_config": {
                "image_version": image_version or rules.default_image_version,
                "optional_components": list(optional_components or []),
                "properties": {
                    "dataproc:dataproc.conscrypt.provider.enable": "false",
                    **(spark_properties or {}),
                },
            },
        }

        # 3. Apply Tier or Custom sizing
        if tier in TIER_DEFINITIONS:
            spec = TIER_DEFINITIONS[tier]
            config["master_config"] = {
                "disk_config": {
                    "boot_disk_size_gb": spec.master_disk_size_gb,
                    "boot_disk_type": "pd-standard",
                },
                "machine_type_uri": spec.master_machine_type,
                "num_instances": spec.master_num_instances,
            }

            if spec.worker_num_instances > 0:
                config["worker_config"] = {
                    "disk_config": {
                        "boot_disk_size_gb": spec.worker_disk_size_gb,
                        "boot_disk_type": "pd-standard",
                    },
                    "machine_type_uri": spec.worker_machine_type,
                    "num_instances": spec.worker_num_instances,
                }

            if spec.secondary_worker_num_instances > 0:
                config["secondary_worker_config"] = {
                    "is_preemptible": spec.secondary_worker_is_preemptible,
                    "num_instances": spec.secondary_worker_num_instances,
                }

            # Lifecycle TTL resolution
            resolved_idle_ttl = (
                idle_delete_ttl_seconds or spec.default_idle_delete_ttl_seconds
            )
            resolved_auto_ttl = (
                auto_delete_ttl_seconds or spec.default_auto_delete_ttl_seconds
            )
        else:
            # CUSTOM_GUARDED - start with minimum defaults
            config["master_config"] = {
                "disk_config": {
                    "boot_disk_size_gb": 100,
                    "boot_disk_type": "pd-standard",
                },
                "machine_type_uri": "n2-standard-4",
                "num_instances": 1,
            }
            config["worker_config"] = {
                "disk_config": {
                    "boot_disk_size_gb": 100,
                    "boot_disk_type": "pd-standard",
                },
                "machine_type_uri": "n2-standard-4",
                "num_instances": 2,
            }
            resolved_idle_ttl = (
                idle_delete_ttl_seconds or rules.default_idle_delete_ttl_seconds
            )
            resolved_auto_ttl = (
                auto_delete_ttl_seconds or rules.default_auto_delete_ttl_seconds
            )

        # 4. Enforce Lifecycle policy (Idle TTL + Auto-Delete TTL)
        config["lifecycle_config"] = {
            "auto_delete_ttl": f"{resolved_auto_ttl}s",
            "idle_delete_ttl": f"{resolved_idle_ttl}s",
        }

        # 5. Inject mandatory platform initialization actions
        init_actions = []
        for action in rules.mandatory_initialization_actions:
            exec_file = action.get("executable_file", "").format(region=region)
            timeout = action.get("execution_timeout", "300s")
            init_actions.append(
                {"executable_file": exec_file, "execution_timeout": timeout}
            )
        if init_actions:
            config["initialization_actions"] = init_actions

        # 6. Apply CMEK encryption if provided
        if cmek_kms_key:
            config["encryption_config"] = {"gce_pd_kms_key_name": cmek_kms_key}

        # 7. Deep merge custom overrides if supplied
        if custom_overrides:
            ClusterConfigBuilder._deep_merge(config, custom_overrides)

        return config

    @staticmethod
    def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> None:
        """Recursively merge overrides into the base dictionary."""
        for key, value in overrides.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                ClusterConfigBuilder._deep_merge(base[key], value)
            else:
                base[key] = value
