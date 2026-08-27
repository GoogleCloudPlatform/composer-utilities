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

"""Secure Dataproc cluster operators enforcing platform guardrails and governance standards."""

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Union

# Handle imports whether executing inside Airflow or in standalone/test environments
try:
    from airflow.models.baseoperator import BaseOperator
    from airflow.providers.google.cloud.operators.dataproc import (
        DataprocCreateClusterOperator,
        DataprocDeleteClusterOperator,
    )
    from airflow.utils.trigger_rule import TriggerRule
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

    class BaseOperator:
        template_fields: Sequence[str] = ()
        template_ext: Sequence[str] = ()
        ui_color: str = "#fff"

        def __init__(self, task_id: str = "task", **kwargs: Any) -> None:
            self.task_id = task_id
            self.upstream_list: List[Any] = []
            self.downstream_list: List[Any] = []
            for k, v in kwargs.items():
                setattr(self, k, v)

        def execute(self, context: Any) -> Any:
            pass

        def __rshift__(self, other: Any) -> Any:
            return other

        def __lshift__(self, other: Any) -> Any:
            return self

    class DataprocCreateClusterOperator(BaseOperator):
        template_fields: Sequence[str] = (
            "project_id",
            "region",
            "cluster_name",
            "cluster_config",
            "labels",
        )
        ui_color: str = "#1E88E5"

        def __init__(
            self,
            *,
            project_id: Optional[str] = None,
            region: Optional[str] = None,
            cluster_name: Optional[str] = None,
            cluster_config: Optional[Dict[str, Any]] = None,
            labels: Optional[Dict[str, str]] = None,
            **kwargs: Any,
        ) -> None:
            super().__init__(**kwargs)
            self.project_id = project_id
            self.region = region
            self.cluster_name = cluster_name
            self.cluster_config = cluster_config or {}
            self.labels = labels or {}

        def execute(self, context: Any) -> Any:
            return {"cluster_name": self.cluster_name}

    class DataprocDeleteClusterOperator(BaseOperator):
        template_fields: Sequence[str] = ("project_id", "region", "cluster_name")
        ui_color: str = "#D32F2F"

        def __init__(
            self,
            *,
            project_id: Optional[str] = None,
            region: Optional[str] = None,
            cluster_name: Optional[str] = None,
            **kwargs: Any,
        ) -> None:
            super().__init__(**kwargs)
            self.project_id = project_id
            self.region = region
            self.cluster_name = cluster_name

        def execute(self, context: Any) -> Any:
            return None

    class TriggerRule:
        ALL_DONE = "all_done"
        ALL_SUCCESS = "all_success"


try:
    from config.cluster_tiers import (
        ClusterConfigBuilder,
        ClusterTier,
        TIER_DEFINITIONS,
    )
    from config.governance_rules import (
        DEFAULT_PLATFORM_RULES,
        PlatformGovernanceRules,
    )
    from exceptions.policy_violations import (
        LifecyclePolicyViolationException,
        MandatoryLabelMissingException,
        NetworkPolicyViolationException,
        ResourceQuotaExceededException,
        SecurityPolicyViolationException,
    )
except ImportError:
    try:
        from plugins.config.cluster_tiers import (
            ClusterConfigBuilder,
            ClusterTier,
            TIER_DEFINITIONS,
        )
        from plugins.config.governance_rules import (
            DEFAULT_PLATFORM_RULES,
            PlatformGovernanceRules,
        )
        from plugins.exceptions.policy_violations import (
            LifecyclePolicyViolationException,
            MandatoryLabelMissingException,
            NetworkPolicyViolationException,
            ResourceQuotaExceededException,
            SecurityPolicyViolationException,
        )
    except (ImportError, ValueError):
        from ..config.cluster_tiers import (
            ClusterConfigBuilder,
            ClusterTier,
            TIER_DEFINITIONS,
        )
        from ..config.governance_rules import (
            DEFAULT_PLATFORM_RULES,
            PlatformGovernanceRules,
        )
        from ..exceptions.policy_violations import (
            LifecyclePolicyViolationException,
            MandatoryLabelMissingException,
            NetworkPolicyViolationException,
            ResourceQuotaExceededException,
            SecurityPolicyViolationException,
        )

logger = logging.getLogger(__name__)


class SecureDataprocCreateClusterOperator(DataprocCreateClusterOperator):
    """Enterprise-governed Dataproc cluster creation operator.

    Subclasses DataprocCreateClusterOperator to enforce non-negotiable platform guardrails:
      1. Security: Forces private IP (internal_ip_only=True), approved subnets, and dedicated SAs.
      2. FinOps: Requires mandatory organizational labels (team, cost_center, environment, data_classification).
      3. Lifecycle: Mandates idle auto-deletion (idle_delete_ttl) and maximum lifetime (auto_delete_ttl).
      4. Resource Quotas: Prevents oversized clusters or prohibited GPU/expensive machine types.
      5. Observability & DevEx: Predefined cluster tiers (DEV, SMALL, STANDARD, HIGH_MEM) with automatic
         Component Gateway and platform monitoring hooks.
    """

    template_fields: Sequence[str] = (
        "project_id",
        "region",
        "cluster_name",
        "team",
        "cost_center",
        "environment",
        "cluster_config",
        "labels",
    )
    ui_color: str = "#0F9D58"  # Google Green for governed operators

    def __init__(
        self,
        *,
        task_id: str,
        project_id: str,
        region: str,
        cluster_name: str,
        team: str,
        cost_center: str,
        environment: str = "dev",
        data_classification: str = "internal",
        tier: Union[ClusterTier, str] = ClusterTier.STANDARD_ANALYTICS,
        owner: Optional[str] = None,
        subnetwork: Optional[str] = None,
        service_account: Optional[str] = None,
        idle_delete_ttl_minutes: Optional[int] = None,
        auto_delete_ttl_hours: Optional[int] = None,
        cmek_kms_key: Optional[str] = None,
        image_version: Optional[str] = None,
        optional_components: Optional[List[str]] = None,
        spark_properties: Optional[Dict[str, str]] = None,
        cluster_config: Optional[Dict[str, Any]] = None,
        labels: Optional[Dict[str, str]] = None,
        governance_rules: Optional[PlatformGovernanceRules] = None,
        **kwargs: Any,
    ) -> None:
        self.rules = governance_rules or DEFAULT_PLATFORM_RULES
        self.raw_tier = tier
        self.tier = ClusterTier(tier) if isinstance(tier, str) else tier
        self.team = team
        self.cost_center = cost_center
        self.environment = environment.lower() if environment else "dev"
        self.data_classification = data_classification.lower() if data_classification else "internal"
        self.owner = owner
        self.cmek_kms_key = cmek_kms_key

        # Convert TTL parameters to seconds
        idle_ttl_sec = idle_delete_ttl_minutes * 60 if idle_delete_ttl_minutes else None
        auto_ttl_sec = auto_delete_ttl_hours * 3600 if auto_delete_ttl_hours else None

        # 1. Validate mandatory FinOps & governance metadata
        validated_labels = self._validate_and_assemble_labels(labels or {})

        # 2. Build or merge cluster configuration
        built_config = ClusterConfigBuilder.build_config(
            tier=self.tier,
            project_id=project_id,
            region=region,
            rules=self.rules,
            subnetwork_uri=subnetwork,
            service_account=service_account,
            idle_delete_ttl_seconds=idle_ttl_sec,
            auto_delete_ttl_seconds=auto_ttl_sec,
            image_version=image_version,
            cmek_kms_key=cmek_kms_key,
            optional_components=optional_components,
            spark_properties=spark_properties,
            custom_overrides=cluster_config,
        )

        # 3. Apply platform-level security & CMEK injection
        self._apply_platform_defaults(built_config, project_id, region)

        # 4. Strict guardrail verification (Fail-fast validation)
        self._enforce_platform_guardrails(built_config, validated_labels)

        super().__init__(
            task_id=task_id,
            project_id=project_id,
            region=region,
            cluster_name=cluster_name,
            cluster_config=built_config,
            labels=validated_labels,
            **kwargs,
        )

    # --------------------------------------------------------------------------
    # Validation & Policy Enforcement Logic
    # --------------------------------------------------------------------------

    def _validate_and_assemble_labels(self, user_labels: Dict[str, str]) -> Dict[str, str]:
        """Validates mandatory labels and formats labels according to GCP standards."""
        # Check required fields
        if not self.team:
            raise MandatoryLabelMissingException(
                rule_id="RULE_FIN_001",
                rule_name="MANDATORY_TEAM_LABEL",
                message="The 'team' parameter is required for all Dataproc clusters.",
                current_value=self.team,
                allowed_range_or_value="Non-empty team identifier (e.g., 'marketing-analytics', 'data-platform')",
                remediation="Specify team='<your-team-name>' in SecureDataprocCreateClusterOperator.",
            )

        if not self.cost_center:
            raise MandatoryLabelMissingException(
                rule_id="RULE_FIN_002",
                rule_name="MANDATORY_COST_CENTER_LABEL",
                message="The 'cost_center' parameter is required for FinOps cost attribution.",
                current_value=self.cost_center,
                allowed_range_or_value="Valid cost center code (e.g., 'cc-10492', 'engineering')",
                remediation="Specify cost_center='<cost-center-code>' in SecureDataprocCreateClusterOperator.",
            )

        if self.environment not in self.rules.allowed_environments:
            raise MandatoryLabelMissingException(
                rule_id="RULE_FIN_003",
                rule_name="INVALID_ENVIRONMENT_LABEL",
                message=f"Environment '{self.environment}' is not recognized by platform governance.",
                current_value=self.environment,
                allowed_range_or_value=self.rules.allowed_environments,
                remediation=f"Set environment to one of: {self.rules.allowed_environments}",
            )

        if self.data_classification not in self.rules.allowed_data_classifications:
            raise MandatoryLabelMissingException(
                rule_id="RULE_FIN_004",
                rule_name="INVALID_DATA_CLASSIFICATION",
                message=f"Data classification '{self.data_classification}' is invalid.",
                current_value=self.data_classification,
                allowed_range_or_value=self.rules.allowed_data_classifications,
                remediation=f"Set data_classification to one of: {self.rules.allowed_data_classifications}",
            )

        # Assemble sanitized labels
        sanitized: Dict[str, str] = {}

        # 1. Mandatory governance labels
        sanitized["team"] = self._sanitize_label_value(self.team)
        sanitized["cost_center"] = self._sanitize_label_value(self.cost_center)
        sanitized["environment"] = self._sanitize_label_value(self.environment)
        sanitized["data_classification"] = self._sanitize_label_value(self.data_classification)
        sanitized["cluster_tier"] = self._sanitize_label_value(self.tier.value)

        if self.owner:
            sanitized["owner"] = self._sanitize_label_value(self.owner)

        # 2. Platform injected tracking labels
        for k, v in self.rules.platform_injected_labels.items():
            sanitized[k] = self._sanitize_label_value(v)

        # 3. User supplied additional labels
        for k, v in user_labels.items():
            clean_k = self._sanitize_label_key(k)
            clean_v = self._sanitize_label_value(str(v))
            sanitized[clean_k] = clean_v

        return sanitized

    @staticmethod
    def _sanitize_label_key(key: str) -> str:
        """Sanitizes GCP label key to match regex: ^[a-z][a-z0-9_-]{0,62}$"""
        cleaned = re.sub(r"[^a-z0-9_-]", "-", key.lower())
        if not cleaned or not cleaned[0].isalpha():
            cleaned = "lbl-" + cleaned
        return cleaned[:63]

    @staticmethod
    def _sanitize_label_value(val: str) -> str:
        """Sanitizes GCP label value to match regex: ^[a-z0-9_-]{0,63}$"""
        cleaned = re.sub(r"[^a-z0-9_-]", "-", val.lower())
        return cleaned[:63]

    def _apply_platform_defaults(self, config: Dict[str, Any], project_id: str, region: str) -> None:
        """Applies automated platform policy defaults like CMEK injection when configured."""
        if self.cmek_kms_key:
            config["encryption_config"] = {"gce_pd_kms_key_name": self.cmek_kms_key}
        elif self.environment in self.rules.environments_requiring_cmek and self.rules.default_cmek_key_template:
            if "encryption_config" not in config or not config["encryption_config"].get("gce_pd_kms_key_name"):
                default_cmek = self.rules.default_cmek_key_template.format(
                    project_id=project_id, region=region
                )
                config["encryption_config"] = {"gce_pd_kms_key_name": default_cmek}
                logger.info("Automatically injected production CMEK encryption key: %s", default_cmek)

    def _enforce_platform_guardrails(self, config: Dict[str, Any], labels: Dict[str, str]) -> None:
        """Strictly validates the finalized configuration against platform security and quota rules."""
        gce_config = config.get("gce_cluster_config", {})

        # ----------------------------------------------------------------------
        # Guardrail 1: Network Security - Private IP Only (No Public IPs)
        # ----------------------------------------------------------------------
        if not gce_config.get("internal_ip_only", False):
            raise SecurityPolicyViolationException(
                rule_id="RULE_SEC_001",
                rule_name="PRIVATE_IP_ONLY_ENFORCEMENT",
                message="Dataproc clusters must NOT have public IP addresses. internal_ip_only must be True.",
                current_value="internal_ip_only=False",
                allowed_range_or_value="internal_ip_only=True",
                remediation="Ensure gce_cluster_config.internal_ip_only is set to True (enforced automatically by tier).",
            )

        # ----------------------------------------------------------------------
        # Guardrail 2: Network Boundary - Subnetwork Validation
        # ----------------------------------------------------------------------
        subnet = gce_config.get("subnetwork_uri", "")
        if subnet and not re.match(self.rules.allowed_subnetwork_regex, subnet):
            raise NetworkPolicyViolationException(
                rule_id="RULE_NET_001",
                rule_name="SUBNETWORK_VALIDATION",
                message=f"Subnetwork '{subnet}' does not match the approved enterprise format.",
                current_value=subnet,
                allowed_range_or_value=self.rules.allowed_subnetwork_regex,
                remediation="Provide a valid subnetwork URI in format: projects/{project}/regions/{region}/subnetworks/{subnet}",
            )

        # ----------------------------------------------------------------------
        # Guardrail 3: IAM Security - Block Default Compute Engine Service Accounts
        # ----------------------------------------------------------------------
        sa = gce_config.get("service_account", "")
        for pattern in self.rules.disallowed_service_account_patterns:
            if re.match(pattern, sa):
                raise SecurityPolicyViolationException(
                    rule_id="RULE_SEC_002",
                    rule_name="DISALLOWED_DEFAULT_SERVICE_ACCOUNT",
                    message=(
                        f"Service account '{sa}' is a default Compute Engine service account with excessive permissions. "
                        "A dedicated least-privilege service account is required."
                    ),
                    current_value=sa,
                    allowed_range_or_value="Dedicated custom IAM service account (e.g. dataproc-worker-sa@...)",
                    remediation="Specify a dedicated service_account or use the platform default.",
                )

        # ----------------------------------------------------------------------
        # Guardrail 4: Resource Quotas - Master & Worker Instance Limits
        # ----------------------------------------------------------------------
        master_config = config.get("master_config", {})
        worker_config = config.get("worker_config", {})
        sec_worker_config = config.get("secondary_worker_config", {})

        num_masters = master_config.get("num_instances", 1)
        if num_masters not in (1, 3) or num_masters > self.rules.max_master_nodes:
            raise ResourceQuotaExceededException(
                rule_id="RULE_QUOTA_001",
                rule_name="INVALID_MASTER_NODE_COUNT",
                message=f"Master node count of {num_masters} is invalid. Dataproc requires 1 (standard) or 3 (HA).",
                current_value=num_masters,
                allowed_range_or_value=f"1 or 3 (max {self.rules.max_master_nodes})",
                remediation="Set master_config.num_instances to 1 (single/standard) or 3 (high-availability).",
            )

        num_workers = worker_config.get("num_instances", 0)
        if num_workers > self.rules.max_primary_workers:
            raise ResourceQuotaExceededException(
                rule_id="RULE_QUOTA_002",
                rule_name="EXCESSIVE_WORKER_COUNT",
                message=f"Requested {num_workers} primary workers, exceeding the platform limit of {self.rules.max_primary_workers}.",
                current_value=num_workers,
                allowed_range_or_value=f"<= {self.rules.max_primary_workers} workers",
                remediation=f"Reduce worker count to {self.rules.max_primary_workers} or submit a quota increase request.",
            )

        num_sec_workers = sec_worker_config.get("num_instances", 0)
        if num_sec_workers > self.rules.max_secondary_workers:
            raise ResourceQuotaExceededException(
                rule_id="RULE_QUOTA_003",
                rule_name="EXCESSIVE_SECONDARY_WORKER_COUNT",
                message=f"Requested {num_sec_workers} secondary/spot workers, exceeding limit of {self.rules.max_secondary_workers}.",
                current_value=num_sec_workers,
                allowed_range_or_value=f"<= {self.rules.max_secondary_workers} secondary workers",
                remediation=f"Reduce secondary worker count to {self.rules.max_secondary_workers}.",
            )

        # ----------------------------------------------------------------------
        # Guardrail 5: Resource Quotas - Machine Type Restrictions
        # ----------------------------------------------------------------------
        for role, c in [("master", master_config), ("worker", worker_config)]:
            machine_type = c.get("machine_type_uri", "")
            for prefix in self.rules.disallowed_machine_type_prefixes:
                if machine_type.startswith(prefix):
                    raise ResourceQuotaExceededException(
                        rule_id="RULE_QUOTA_004",
                        rule_name="DISALLOWED_MACHINE_TYPE",
                        message=f"Machine type '{machine_type}' for {role} belongs to restricted family '{prefix}'.",
                        current_value=machine_type,
                        allowed_range_or_value=self.rules.allowed_machine_type_families,
                        remediation=f"Choose an approved machine type from families: {self.rules.allowed_machine_type_families}",
                    )

        # ----------------------------------------------------------------------
        # Guardrail 6: Cost Governance - Lifecycle & Idle Timeout Enforcement
        # ----------------------------------------------------------------------
        lifecycle = config.get("lifecycle_config", {})
        idle_ttl_str = lifecycle.get("idle_delete_ttl", "")
        if not idle_ttl_str:
            raise LifecyclePolicyViolationException(
                rule_id="RULE_LIFE_001",
                rule_name="MANDATORY_IDLE_TTL",
                message="All Dataproc clusters must have an idle_delete_ttl configured to prevent zombie cluster spend.",
                current_value="None",
                allowed_range_or_value=f"<= {self.rules.max_idle_delete_ttl_seconds}s",
                remediation="Specify idle_delete_ttl_minutes or rely on tier defaults.",
            )

        idle_seconds = int(idle_ttl_str.rstrip("s"))
        if idle_seconds > self.rules.max_idle_delete_ttl_seconds:
            raise LifecyclePolicyViolationException(
                rule_id="RULE_LIFE_002",
                rule_name="IDLE_TTL_EXCEEDS_MAXIMUM",
                message=f"Idle delete TTL of {idle_seconds}s exceeds the platform limit of {self.rules.max_idle_delete_ttl_seconds}s.",
                current_value=f"{idle_seconds}s",
                allowed_range_or_value=f"<= {self.rules.max_idle_delete_ttl_seconds}s (max {self.rules.max_idle_delete_ttl_seconds // 60} mins)",
                remediation=f"Reduce idle_delete_ttl_minutes to {self.rules.max_idle_delete_ttl_seconds // 60} mins or less.",
            )

        # ----------------------------------------------------------------------
        # Guardrail 7: Software & Security - Approved Image Version
        # ----------------------------------------------------------------------
        software_config = config.get("software_config", {})
        image_version = software_config.get("image_version", "")
        if image_version not in self.rules.allowed_image_versions:
            raise SecurityPolicyViolationException(
                rule_id="RULE_SEC_004",
                rule_name="UNAPPROVED_IMAGE_VERSION",
                message=f"Dataproc image version '{image_version}' is not approved for enterprise workloads.",
                current_value=image_version,
                allowed_range_or_value=self.rules.allowed_image_versions,
                remediation=f"Use one of the approved image versions: {self.rules.allowed_image_versions}",
            )

    def execute(self, context: Any) -> Any:
        """Logs comprehensive platform governance audit details before cluster creation."""
        lifecycle = self.cluster_config.get("lifecycle_config", {})
        gce = self.cluster_config.get("gce_cluster_config", {})
        master = self.cluster_config.get("master_config", {})
        worker = self.cluster_config.get("worker_config", {})
        encryption = self.cluster_config.get("encryption_config", {})

        cmek_status = (
            f"Enabled ({encryption.get('gce_pd_kms_key_name', 'Default')})"
            if encryption.get("gce_pd_kms_key_name")
            else "Standard Google-Managed"
        )

        logger.info(
            "\n"
            "╔═══════════════════════════════════════════════════════════════════════════════════════════\n"
            "║ [PLATFORM GOVERNANCE AUDIT] Provisioning Hardened Dataproc Cluster\n"
            "╠═══════════════════════════════════════════════════════════════════════════════════════════\n"
            "║ Cluster Name        : %s\n"
            "║ Tier Template       : %s\n"
            "║ Project / Region    : %s / %s\n"
            "║ Team / Cost Center  : %s / %s\n"
            "║ Environment         : %s (Classification: %s)\n"
            "║ Master Nodes        : %s x %s (%s GB Disk)\n"
            "║ Primary Workers     : %s x %s (%s GB Disk)\n"
            "║ Network Security    : Private IP Only (internal_ip_only=True)\n"
            "║ Subnetwork URI      : %s\n"
            "║ Service Account     : %s\n"
            "║ Idle Auto-Delete    : %s\n"
            "║ Max Lifespan        : %s\n"
            "║ CMEK Encryption     : %s\n"
            "║ Component Gateway   : Enabled (Secure Web UI via Cloud Console)\n"
            "╚═══════════════════════════════════════════════════════════════════════════════════════════",
            self.cluster_name,
            self.tier.value,
            self.project_id,
            self.region,
            self.team,
            self.cost_center,
            self.environment,
            self.data_classification,
            master.get("num_instances", 1),
            master.get("machine_type_uri", "default"),
            master.get("disk_config", {}).get("boot_disk_size_gb", 100),
            worker.get("num_instances", 0),
            worker.get("machine_type_uri", "n/a"),
            worker.get("disk_config", {}).get("boot_disk_size_gb", 100),
            gce.get("subnetwork_uri", "default"),
            gce.get("service_account", "default"),
            lifecycle.get("idle_delete_ttl", "None"),
            lifecycle.get("auto_delete_ttl", "None"),
            cmek_status,
        )

        return super().execute(context)


class SecureDataprocDeleteClusterOperator(DataprocDeleteClusterOperator):
    """Governed Dataproc cluster deletion operator.

    Enforces platform teardown reliability best practices:
      1. Sets default trigger_rule to 'all_done' to guarantee cluster cleanup even if prior ETL tasks fail.
      2. Logs lifecycle cleanup metrics for cost auditing.
    """

    ui_color: str = "#E53935"  # Google Red for deletion

    def __init__(
        self,
        *,
        task_id: str,
        project_id: str,
        region: str,
        cluster_name: str,
        trigger_rule: str = TriggerRule.ALL_DONE,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task_id=task_id,
            project_id=project_id,
            region=region,
            cluster_name=cluster_name,
            trigger_rule=trigger_rule,
            **kwargs,
        )

    def execute(self, context: Any) -> Any:
        logger.info(
            "[PLATFORM TEARDOWN] Initiating teardown for Dataproc cluster '%s' in %s/%s",
            self.cluster_name,
            self.project_id,
            self.region,
        )
        result = super().execute(context)
        logger.info(
            "[PLATFORM TEARDOWN] Teardown complete for Dataproc cluster '%s'. Compute spend ceased.",
            self.cluster_name,
        )
        return result
