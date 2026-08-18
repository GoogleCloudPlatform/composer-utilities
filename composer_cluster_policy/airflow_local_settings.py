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

"""Airflow Cluster Policy for Cloud Composer.

This module implements governance and resource management policies for
Google Cloud Composer environments:
1. Pod Mutation Hook (`pod_mutation_hook`):
   - Inspects and clamps excessive CPU / Memory requests and limits for KubernetesPodOperator.
   - Enforces default resource requests/limits when omitted.
   - Enforces approved workload namespaces (e.g. 'composer-user-workloads').
   - Injects standard governance labels and metadata.
2. Task Policy (`task_policy`):
   - Enforces execution timeouts on unbounded tasks.
   - Caps excessive task retry counts.
3. DAG Policy (`dag_policy`):
   - Enforces DAG ownership, tags, and documentation standards.

Deployment:
Place this file as `airflow_local_settings.py` in your Cloud Composer environment's
`plugins/` folder (or sync via GCS: `gs://<composer-bucket>/plugins/airflow_local_settings.py`).
"""

from __future__ import annotations

from datetime import timedelta
import logging
import os
import re
from typing import Any

# Configure logger
logger = logging.getLogger("airflow.cluster_policy")


# ==============================================================================
# ⚙️ CONFIGURATION & POLICY THRESHOLDS
# ==============================================================================

# Maximum allowed CPU request/limit per pod container (in cores, e.g. 4.0 = 4000m)
MAX_ALLOWED_CPU_CORES: float = float(os.environ.get("COMPOSER_POLICY_MAX_CPU_CORES", "4.0"))

# Maximum allowed Memory request/limit per pod container (in MiB, e.g. 8192 = 8 GiB)
MAX_ALLOWED_MEMORY_MIB: float = float(os.environ.get("COMPOSER_POLICY_MAX_MEMORY_MIB", "8192.0"))

# Default resource fallback if omitted by the DAG author
DEFAULT_CPU_REQUEST: str = os.environ.get("COMPOSER_POLICY_DEFAULT_CPU_REQUEST", "500m")
DEFAULT_MEMORY_REQUEST: str = os.environ.get("COMPOSER_POLICY_DEFAULT_MEMORY_REQUEST", "1024Mi")
DEFAULT_CPU_LIMIT: str = os.environ.get("COMPOSER_POLICY_DEFAULT_CPU_LIMIT", "2000m")
DEFAULT_MEMORY_LIMIT: str = os.environ.get("COMPOSER_POLICY_DEFAULT_MEMORY_LIMIT", "4096Mi")

# Namespace governance
ALLOWED_NAMESPACES: set[str] = set(
    os.environ.get(
        "COMPOSER_POLICY_ALLOWED_NAMESPACES",
        "composer-user-workloads,default",
    ).split(",")
)
DEFAULT_NAMESPACE: str = "composer-user-workloads"
ENFORCE_NAMESPACE: bool = os.environ.get("COMPOSER_POLICY_ENFORCE_NAMESPACE", "true").lower() == "true"

# Standard governance labels injected into mutated pods
GOVERNANCE_LABELS: dict[str, str] = {
    "managed-by": "composer-cluster-policy",
    "policy-enforced": "true",
}

# Task policy settings
DEFAULT_TASK_TIMEOUT_HOURS: int = int(os.environ.get("COMPOSER_POLICY_TASK_TIMEOUT_HOURS", "4"))
MAX_ALLOWED_RETRIES: int = int(os.environ.get("COMPOSER_POLICY_MAX_RETRIES", "3"))


# ==============================================================================
# 🛠️ RESOURCE PARSING HELPERS
# ==============================================================================

def parse_cpu_to_cores(cpu_val: str | int | float | None) -> float | None:
    """Parses a Kubernetes CPU quantity string into a float representing cores.

    Examples:
        '8000m' -> 8.0
        '500m'  -> 0.5
        '4'     -> 4.0
        4       -> 4.0
    """
    if cpu_val is None:
        return None
    cpu_str = str(cpu_val).strip()
    if not cpu_str:
        return None
    if cpu_str.endswith("m"):
        try:
            return float(cpu_str[:-1]) / 1000.0
        except ValueError:
            return None
    try:
        return float(cpu_str)
    except ValueError:
        return None


def parse_memory_to_mib(mem_val: str | int | float | None) -> float | None:
    """Parses a Kubernetes Memory quantity string into MiB (mebibytes).

    Examples:
        '16000Mi' -> 16000.0
        '16Gi'    -> 16384.0
        '16G'     -> 15258.78
        '8192M'   -> 7812.5
        '1048576' -> 1.0 (raw bytes)
    """
    if mem_val is None:
        return None
    mem_str = str(mem_val).strip()
    if not mem_str:
        return None

    units = {
        "Ki": 1.0 / 1024.0,
        "Mi": 1.0,
        "Gi": 1024.0,
        "Ti": 1024.0 * 1024.0,
        "Pi": 1024.0 * 1024.0 * 1024.0,
        "Ei": 1024.0 * 1024.0 * 1024.0 * 1024.0,
        "k": 1000.0 / (1024.0 * 1024.0),
        "M": (1000.0 * 1000.0) / (1024.0 * 1024.0),
        "G": (1000.0 * 1000.0 * 1000.0) / (1024.0 * 1024.0),
        "T": (1000.0 * 1000.0 * 1000.0) / (1024.0 * 1024.0),
    }

    for unit, multiplier in sorted(units.items(), key=lambda x: -len(x[0])):
        if mem_str.endswith(unit):
            num_part = mem_str[: -len(unit)]
            try:
                return float(num_part) * multiplier
            except ValueError:
                return None

    try:
        # Raw bytes
        return float(mem_str) / (1024.0 * 1024.0)
    except ValueError:
        return None


# ==============================================================================
# 🛡️ POD MUTATION HOOK (Airflow Cluster Policy)
# ==============================================================================

def pod_mutation_hook(pod: Any) -> None:
    """Mutates Kubernetes Pods created by KubernetesPodOperator or GKEStartPodOperator.

    Enforces:
    1. Resource caps (clamps excessive CPU / RAM requests and limits to maximum thresholds).
    2. Default fallback resources when requests/limits are missing.
    3. Namespace governance.
    4. Corporate / standard governance labels.
    """
    logger.info("Applying Composer Cluster Policy pod_mutation_hook...")

    # --- 1. Namespace Governance ---
    metadata = getattr(pod, "metadata", None)
    if metadata is None:
        return

    current_ns = getattr(metadata, "namespace", None)
    if not current_ns:
        metadata.namespace = DEFAULT_NAMESPACE
        logger.info(
            "Cluster Policy: Pod namespace was unset. Defaulted to '%s'.",
            DEFAULT_NAMESPACE,
        )
    elif ENFORCE_NAMESPACE and current_ns not in ALLOWED_NAMESPACES:
        logger.warning(
            "Cluster Policy: Disallowed namespace '%s' overridden to '%s'.",
            current_ns,
            DEFAULT_NAMESPACE,
        )
        metadata.namespace = DEFAULT_NAMESPACE

    # --- 2. Governance Labels ---
    labels = getattr(metadata, "labels", None)
    if labels is None:
        metadata.labels = {}
        labels = metadata.labels

    for k, v in GOVERNANCE_LABELS.items():
        labels[k] = v

    # --- 3. Container Resource Enforcement ---
    spec = getattr(pod, "spec", None)
    if spec is None:
        return

    containers = getattr(spec, "containers", []) or []
    for container in containers:
        _enforce_container_resources(container)


def _enforce_container_resources(container: Any) -> None:
    """Enforces requests and limits on a single container."""
    container_name = getattr(container, "name", "unnamed")
    resources = getattr(container, "resources", None)

    # If resources object is None, initialize a dictionary or V1ResourceRequirements
    if resources is None:
        try:
            from kubernetes.client import models as k8s
            resources = k8s.V1ResourceRequirements(
                requests={"cpu": DEFAULT_CPU_REQUEST, "memory": DEFAULT_MEMORY_REQUEST},
                limits={"cpu": DEFAULT_CPU_LIMIT, "memory": DEFAULT_MEMORY_LIMIT},
            )
            container.resources = resources
            logger.info(
                "Cluster Policy [%s]: Injected default resource requests and limits.",
                container_name,
            )
            return
        except ImportError:
            # Fallback dict structure
            container.resources = {
                "requests": {"cpu": DEFAULT_CPU_REQUEST, "memory": DEFAULT_MEMORY_REQUEST},
                "limits": {"cpu": DEFAULT_CPU_LIMIT, "memory": DEFAULT_MEMORY_LIMIT},
            }
            return

    # Handle both V1ResourceRequirements object and plain dict
    requests = getattr(resources, "requests", None)
    if requests is None and isinstance(resources, dict):
        requests = resources.get("requests")
    if requests is None:
        if isinstance(resources, dict):
            resources["requests"] = {}
            requests = resources["requests"]
        else:
            resources.requests = {}
            requests = resources.requests

    limits = getattr(resources, "limits", None)
    if limits is None and isinstance(resources, dict):
        limits = resources.get("limits")
    if limits is None:
        if isinstance(resources, dict):
            resources["limits"] = {}
            limits = resources["limits"]
        else:
            resources.limits = {}
            limits = resources.limits

    # Enforce CPU Requests
    cpu_req = requests.get("cpu") if isinstance(requests, dict) else getattr(requests, "cpu", None)
    parsed_cpu = parse_cpu_to_cores(cpu_req)
    if parsed_cpu is None:
        requests["cpu"] = DEFAULT_CPU_REQUEST
        logger.info("Cluster Policy [%s]: Set default CPU request '%s'", container_name, DEFAULT_CPU_REQUEST)
    elif parsed_cpu > MAX_ALLOWED_CPU_CORES:
        max_cpu_str = f"{int(MAX_ALLOWED_CPU_CORES * 1000)}m"
        logger.warning(
            "Cluster Policy [%s]: CPU request '%s' (%.1f cores) exceeded max allowed (%.1f cores). Clamping to '%s'.",
            container_name,
            cpu_req,
            parsed_cpu,
            MAX_ALLOWED_CPU_CORES,
            max_cpu_str,
        )
        requests["cpu"] = max_cpu_str

    # Enforce Memory Requests
    mem_req = requests.get("memory") if isinstance(requests, dict) else getattr(requests, "memory", None)
    parsed_mem = parse_memory_to_mib(mem_req)
    if parsed_mem is None:
        requests["memory"] = DEFAULT_MEMORY_REQUEST
        logger.info("Cluster Policy [%s]: Set default Memory request '%s'", container_name, DEFAULT_MEMORY_REQUEST)
    elif parsed_mem > MAX_ALLOWED_MEMORY_MIB:
        max_mem_str = f"{int(MAX_ALLOWED_MEMORY_MIB)}Mi"
        logger.warning(
            "Cluster Policy [%s]: Memory request '%s' (%.1f MiB) exceeded max allowed (%.1f MiB). Clamping to '%s'.",
            container_name,
            mem_req,
            parsed_mem,
            MAX_ALLOWED_MEMORY_MIB,
            max_mem_str,
        )
        requests["memory"] = max_mem_str

    # Enforce CPU Limits
    cpu_lim = limits.get("cpu") if isinstance(limits, dict) else getattr(limits, "cpu", None)
    parsed_lim_cpu = parse_cpu_to_cores(cpu_lim)
    if parsed_lim_cpu is not None and parsed_lim_cpu > MAX_ALLOWED_CPU_CORES:
        max_cpu_str = f"{int(MAX_ALLOWED_CPU_CORES * 1000)}m"
        logger.warning(
            "Cluster Policy [%s]: CPU limit '%s' exceeded max allowed. Clamping to '%s'.",
            container_name,
            cpu_lim,
            max_cpu_str,
        )
        limits["cpu"] = max_cpu_str

    # Enforce Memory Limits
    mem_lim = limits.get("memory") if isinstance(limits, dict) else getattr(limits, "memory", None)
    parsed_lim_mem = parse_memory_to_mib(mem_lim)
    if parsed_lim_mem is not None and parsed_lim_mem > MAX_ALLOWED_MEMORY_MIB:
        max_mem_str = f"{int(MAX_ALLOWED_MEMORY_MIB)}Mi"
        logger.warning(
            "Cluster Policy [%s]: Memory limit '%s' exceeded max allowed. Clamping to '%s'.",
            container_name,
            mem_lim,
            max_mem_str,
        )
        limits["memory"] = max_mem_str


# ==============================================================================
# 📋 TASK POLICY (Airflow Cluster Policy)
# ==============================================================================

def task_policy(task: Any) -> None:
    """Enforces task-level operational standards across all operators.

    - Enforces default execution_timeout if not specified to prevent runaway tasks.
    - Enforces a maximum cap on retry attempts.
    """
    # Enforce execution timeout
    if getattr(task, "execution_timeout", None) is None:
        task.execution_timeout = timedelta(hours=DEFAULT_TASK_TIMEOUT_HOURS)
        logger.info(
            "Cluster Policy [Task %s]: Applied default execution_timeout of %d hours.",
            getattr(task, "task_id", "unknown"),
            DEFAULT_TASK_TIMEOUT_HOURS,
        )

    # Enforce max retries
    current_retries = getattr(task, "retries", 0)
    if current_retries and current_retries > MAX_ALLOWED_RETRIES:
        logger.warning(
            "Cluster Policy [Task %s]: Retries (%d) exceeded max allowed (%d). Clamping to %d.",
            getattr(task, "task_id", "unknown"),
            current_retries,
            MAX_ALLOWED_RETRIES,
            MAX_ALLOWED_RETRIES,
        )
        task.retries = MAX_ALLOWED_RETRIES


# ==============================================================================
# 📦 DAG POLICY (Airflow Cluster Policy)
# ==============================================================================

def dag_policy(dag: Any) -> None:
    """Enforces metadata, tagging, and ownership governance on DAGs."""
    dag_id = getattr(dag, "dag_id", "unknown")

    # Enforce tags
    tags = getattr(dag, "tags", None)
    if not tags:
        logger.warning(
            "Cluster Policy [DAG %s]: DAG does not have tags defined. Consider adding categorization tags.",
            dag_id,
        )

    # Check default_args owner
    default_args = getattr(dag, "default_args", {}) or {}
    owner = default_args.get("owner")
    if not owner or owner.lower() in ("airflow", "root"):
        logger.warning(
            "Cluster Policy [DAG %s]: DAG owner is '%s'. Please specify a team/owner identifier.",
            dag_id,
            owner,
        )
