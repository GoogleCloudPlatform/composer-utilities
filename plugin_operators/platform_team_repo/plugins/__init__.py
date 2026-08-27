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

"""Airflow Dataproc Platform Governance Plugin Package."""

import sys

# Prevent generation of __pycache__ / .pyc files across all developer environments
sys.dont_write_bytecode = True

try:
    from config.cluster_tiers import ClusterConfigBuilder, ClusterTier
    from config.governance_rules import DEFAULT_PLATFORM_RULES, PlatformGovernanceRules
    from dataproc_governance_plugin import DataprocGovernancePlugin
    from operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
    from operators.secure_dataproc_operator import (
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )
except ImportError:
    try:
        from plugins.config.cluster_tiers import ClusterConfigBuilder, ClusterTier
        from plugins.config.governance_rules import (
            DEFAULT_PLATFORM_RULES,
            PlatformGovernanceRules,
        )
        from plugins.dataproc_governance_plugin import DataprocGovernancePlugin
        from plugins.operators.dataproc_job_operator import (
            SecureDataprocSubmitJobOperator,
        )
        from plugins.operators.secure_dataproc_operator import (
            SecureDataprocCreateClusterOperator,
            SecureDataprocDeleteClusterOperator,
        )
    except (ImportError, ValueError):
        from .config.cluster_tiers import ClusterConfigBuilder, ClusterTier
        from .config.governance_rules import (
            DEFAULT_PLATFORM_RULES,
            PlatformGovernanceRules,
        )
        from .dataproc_governance_plugin import DataprocGovernancePlugin
        from .operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
        from .operators.secure_dataproc_operator import (
            SecureDataprocCreateClusterOperator,
            SecureDataprocDeleteClusterOperator,
        )

__all__ = [
    "DataprocGovernancePlugin",
    "SecureDataprocCreateClusterOperator",
    "SecureDataprocDeleteClusterOperator",
    "SecureDataprocSubmitJobOperator",
    "ClusterTier",
    "ClusterConfigBuilder",
    "PlatformGovernanceRules",
    "DEFAULT_PLATFORM_RULES",
]
