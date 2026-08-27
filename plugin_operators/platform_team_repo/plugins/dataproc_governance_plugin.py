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

"""Airflow Plugin exposing Governed Dataproc Operators in Managed Service for Apache Airflow (formerly Cloud Composer)."""

from typing import Any, List

try:
    from airflow.plugins_manager import AirflowPlugin
except ImportError:
    class AirflowPlugin:
        name: str = ""
        operators: List[Any] = []

try:
    from operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
    from operators.secure_dataproc_operator import (
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
    )
except ImportError:
    try:
        from plugins.operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
        from plugins.operators.secure_dataproc_operator import (
            SecureDataprocCreateClusterOperator,
            SecureDataprocDeleteClusterOperator,
        )
    except (ImportError, ValueError):
        from .operators.dataproc_job_operator import SecureDataprocSubmitJobOperator
        from .operators.secure_dataproc_operator import (
            SecureDataprocCreateClusterOperator,
            SecureDataprocDeleteClusterOperator,
        )


class DataprocGovernancePlugin(AirflowPlugin):
    """Managed Service for Apache Airflow Plugin exposing Enterprise Governed Dataproc Operators."""

    name = "dataproc_governance_plugin"
    operators = [
        SecureDataprocCreateClusterOperator,
        SecureDataprocDeleteClusterOperator,
        SecureDataprocSubmitJobOperator,
    ]
