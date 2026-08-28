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

"""Custom exception hierarchy for Dataproc Platform Governance violations."""

from typing import Any

try:
    from airflow.exceptions import AirflowException
except ImportError:

    class AirflowException(Exception):
        """Fallback AirflowException base class when airflow is not installed."""


class DataprocPolicyViolationException(AirflowException):
    """Base exception for all Dataproc platform policy and guardrail violations.

    Provides structured diagnostic information including rule name, current value,
    allowed range/value, and step-by-step remediation instructions for DAG authors.
    """

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        message: str,
        current_value: Any | None = None,
        allowed_range_or_value: Any | None = None,
        remediation: str | None = None,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.message = message
        self.current_value = current_value
        self.allowed_range_or_value = allowed_range_or_value
        self.remediation = remediation

        formatted_msg = (
            f"\n"
            f"╔═══════════════════════════════════════════════════════════════════════════════════════════\n"
            f"║ [PLATFORM GOVERNANCE VIOLATION] {rule_id}: {rule_name}\n"
            f"╠═══════════════════════════════════════════════════════════════════════════════════════════\n"
            f"║ Description : {message}\n"
        )
        if current_value is not None:
            formatted_msg += f"║ Provided    : {current_value}\n"
        if allowed_range_or_value is not None:
            formatted_msg += f"║ Permitted   : {allowed_range_or_value}\n"
        if remediation:
            formatted_msg += f"║ Remediation : {remediation}\n"
        formatted_msg += "╚═══════════════════════════════════════════════════════════════════════════════════════════"
        super().__init__(formatted_msg)


class SecurityPolicyViolationException(DataprocPolicyViolationException):
    """Raised when a security guardrail is breached (e.g., public IP, unauthorized service account, CMEK)."""


class ResourceQuotaExceededException(DataprocPolicyViolationException):
    """Raised when resource allocations exceed platform limits (e.g., worker count, disk size, disallowed GPU)."""


class MandatoryLabelMissingException(DataprocPolicyViolationException):
    """Raised when required FinOps or compliance metadata labels are missing or malformed."""


class LifecyclePolicyViolationException(DataprocPolicyViolationException):
    """Raised when cluster lifecycle configurations (idle TTL, max lifetime) violate platform limits."""


class NetworkPolicyViolationException(DataprocPolicyViolationException):
    """Raised when cluster network or subnetwork configurations violate platform network policies."""
