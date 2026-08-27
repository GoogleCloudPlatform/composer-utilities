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

This module implements enterprise platform governance, resource management,
and operational resilience policies for Google Cloud Composer (Composer 2 and Composer 3):

1. Pod Mutation Hook (`pod_mutation_hook`):
   - Inspects and clamps excessive CPU / Memory requests and limits for KubernetesPodOperator.
   - Enforces default resource requests/limits when omitted.
   - Enforces approved workload namespaces (e.g. 'composer-user-workloads').
   - Injects standard governance labels and metadata.
   - Injects Solution 1 (Init Container Delay) to resolve GKE Workload Identity
     metadata server cold-start race conditions on newly provisioned nodes.

2. Task Policy (`task_policy`):
   - Enforces Solution 2 (Automated Retries & Backoff) on KubernetesPodOperator
     to ensure self-healing across transient infrastructure scaling events.
   - Enforces execution timeouts on unbounded tasks to prevent hanging worker slots.
   - Caps excessive task retry counts across standard operators.

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

try:
    from airflow.exceptions import AirflowClusterPolicyViolation
except ImportError:

    class AirflowClusterPolicyViolation(Exception):
        """Fallback exception when airflow is not installed."""
        pass


# Configure logger
logger = logging.getLogger("airflow.cluster_policy")


# ==============================================================================
# CONFIGURATION & POLICY THRESHOLDS
# ==============================================================================

# Maximum allowed CPU request/limit per pod container (in cores, e.g. 4.0 = 4000m)
MAX_ALLOWED_CPU_CORES: float = float(
    os.environ.get("COMPOSER_POLICY_MAX_CPU_CORES", "4.0")
)

# Maximum allowed Memory request/limit per pod container (in MiB, e.g. 8192 = 8 GiB)
MAX_ALLOWED_MEMORY_MIB: float = float(
    os.environ.get("COMPOSER_POLICY_MAX_MEMORY_MIB", "8192.0")
)

# Default resource fallback if omitted by the DAG author
DEFAULT_CPU_REQUEST: str = os.environ.get("COMPOSER_POLICY_DEFAULT_CPU_REQUEST", "500m")
DEFAULT_MEMORY_REQUEST: str = os.environ.get(
    "COMPOSER_POLICY_DEFAULT_MEMORY_REQUEST", "1024Mi"
)
DEFAULT_CPU_LIMIT: str = os.environ.get("COMPOSER_POLICY_DEFAULT_CPU_LIMIT", "2000m")
DEFAULT_MEMORY_LIMIT: str = os.environ.get(
    "COMPOSER_POLICY_DEFAULT_MEMORY_LIMIT", "4096Mi"
)

# Namespace governance
ALLOWED_NAMESPACES: set[str] = set(
    os.environ.get(
        "COMPOSER_POLICY_ALLOWED_NAMESPACES",
        "composer-user-workloads,default",
    ).split(",")
)
DEFAULT_NAMESPACE: str = "composer-user-workloads"
ENFORCE_NAMESPACE: bool = (
    os.environ.get("COMPOSER_POLICY_ENFORCE_NAMESPACE", "true").lower() == "true"
)

# Standard governance labels injected into mutated pods
GOVERNANCE_LABELS: dict[str, str] = {
    "managed-by": "composer-cluster-policy",
    "policy-enforced": "true",
}

# Task policy settings
DEFAULT_TASK_TIMEOUT_HOURS: int = int(
    os.environ.get("COMPOSER_POLICY_TASK_TIMEOUT_HOURS", "4")
)
MAX_ALLOWED_RETRIES: int = int(os.environ.get("COMPOSER_POLICY_MAX_RETRIES", "3"))

# GKE Workload Identity Cold-Start Mitigation Settings (RCA Solutions 1 & 2)
ENABLE_INIT_CONTAINER_DELAY: bool = (
    os.environ.get("COMPOSER_POLICY_ENABLE_INIT_DELAY", "false").lower() == "true"
)
INIT_CONTAINER_DELAY_SECONDS: int = int(
    os.environ.get("COMPOSER_POLICY_INIT_DELAY_SECONDS", "15")
)
# Use Google Container Registry image to avoid Docker Hub connection timeouts on Private GKE clusters
INIT_CONTAINER_IMAGE: str = os.environ.get(
    "COMPOSER_POLICY_INIT_IMAGE",
    "gcr.io/google.com/cloudsdktool/cloud-sdk:latest",
)
KPO_MIN_RETRIES: int = int(os.environ.get("COMPOSER_POLICY_KPO_MIN_RETRIES", "2"))
KPO_MIN_RETRY_DELAY_SECONDS: int = int(
    os.environ.get("COMPOSER_POLICY_KPO_MIN_RETRY_DELAY_SECONDS", "10")
)


# ==============================================================================
# RESOURCE PARSING HELPERS
# ==============================================================================


def parse_cpu_to_cores(cpu_val: str | int | float | None) -> float | None:
    """Parses a Kubernetes CPU quantity string into a float representing cores."""
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
    """Parses a Kubernetes Memory quantity string into MiB (mebibytes)."""
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
        return float(mem_str) / (1024.0 * 1024.0)
    except ValueError:
        return None


# ==============================================================================
# POD MUTATION HOOK (Airflow Cluster Policy)
# ==============================================================================


def pod_mutation_hook(pod: Any) -> None:
    """Mutates Kubernetes Pods created by KubernetesPodOperator or GKEStartPodOperator.

    Enforces:
    1. Resource caps (clamps excessive CPU / RAM requests and limits to maximum thresholds).
    2. Default fallback resources when requests/limits are missing.
    3. Namespace governance.
    4. Corporate / standard governance labels.
    5. Solution 1 (Init Container Delay): Injects custom-init-setup to prevent
       GKE metadata server cold-start race conditions on newly scaled nodes.
    """
    logger.info("Applying Composer Cluster Policy pod_mutation_hook...")

    metadata = getattr(pod, "metadata", None)
    spec = getattr(pod, "spec", None)
    if metadata is None or spec is None:
        return

    # Non-destructive safety check for Google Cloud Composer:
    # Do not mutate internal Composer executor worker pods or break container commands/env.
    existing_labels = getattr(metadata, "labels", None) or {}
    pod_name = str(getattr(metadata, "name", ""))
    if (
        existing_labels.get("component") == "worker"
        or existing_labels.get("tier") == "airflow"
        or "airflow-worker" in pod_name
        or getattr(metadata, "namespace", "") == "composer-system"
    ):
        return

    # --- 1. Namespace Governance ---
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

    # --- 3. Container Resource Enforcement (Clamping) ---
    containers = getattr(spec, "containers", []) or []
    for container in containers:
        _enforce_container_resources(container)

    # --- 4. Solution 1: Inject Init Container Delay for GKE Metadata Server ---
    if ENABLE_INIT_CONTAINER_DELAY:
        _inject_metadata_delay_init_container(spec)


def _enforce_container_resources(container: Any) -> None:
    """Enforces requests and limits on a single container."""
    container_name = getattr(container, "name", "unnamed")
    resources = getattr(container, "resources", None)

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
            container.resources = {
                "requests": {
                    "cpu": DEFAULT_CPU_REQUEST,
                    "memory": DEFAULT_MEMORY_REQUEST,
                },
                "limits": {"cpu": DEFAULT_CPU_LIMIT, "memory": DEFAULT_MEMORY_LIMIT},
            }
            return

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
    cpu_req = (
        requests.get("cpu")
        if isinstance(requests, dict)
        else getattr(requests, "cpu", None)
    )
    parsed_cpu = parse_cpu_to_cores(cpu_req)
    if parsed_cpu is None:
        if isinstance(requests, dict):
            requests["cpu"] = DEFAULT_CPU_REQUEST
        else:
            setattr(requests, "cpu", DEFAULT_CPU_REQUEST)
        logger.info(
            "Cluster Policy [%s]: Set default CPU request '%s'",
            container_name,
            DEFAULT_CPU_REQUEST,
        )
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
        if isinstance(requests, dict):
            requests["cpu"] = max_cpu_str
        else:
            setattr(requests, "cpu", max_cpu_str)

    # Enforce Memory Requests
    mem_req = (
        requests.get("memory")
        if isinstance(requests, dict)
        else getattr(requests, "memory", None)
    )
    parsed_mem = parse_memory_to_mib(mem_req)
    if parsed_mem is None:
        if isinstance(requests, dict):
            requests["memory"] = DEFAULT_MEMORY_REQUEST
        else:
            setattr(requests, "memory", DEFAULT_MEMORY_REQUEST)
        logger.info(
            "Cluster Policy [%s]: Set default Memory request '%s'",
            container_name,
            DEFAULT_MEMORY_REQUEST,
        )
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
        if isinstance(requests, dict):
            requests["memory"] = max_mem_str
        else:
            setattr(requests, "memory", max_mem_str)

    # Enforce CPU Limits
    cpu_lim = (
        limits.get("cpu") if isinstance(limits, dict) else getattr(limits, "cpu", None)
    )
    parsed_lim_cpu = parse_cpu_to_cores(cpu_lim)
    if parsed_lim_cpu is None:
        if isinstance(limits, dict):
            limits["cpu"] = DEFAULT_CPU_LIMIT
        else:
            setattr(limits, "cpu", DEFAULT_CPU_LIMIT)
        logger.info(
            "Cluster Policy [%s]: Set default CPU limit '%s'",
            container_name,
            DEFAULT_CPU_LIMIT,
        )
    elif parsed_lim_cpu > MAX_ALLOWED_CPU_CORES:
        max_cpu_str = f"{int(MAX_ALLOWED_CPU_CORES * 1000)}m"
        logger.warning(
            "Cluster Policy [%s]: CPU limit '%s' exceeded max allowed. Clamping to '%s'.",
            container_name,
            cpu_lim,
            max_cpu_str,
        )
        if isinstance(limits, dict):
            limits["cpu"] = max_cpu_str
        else:
            setattr(limits, "cpu", max_cpu_str)

    # Enforce Memory Limits
    mem_lim = (
        limits.get("memory")
        if isinstance(limits, dict)
        else getattr(limits, "memory", None)
    )
    parsed_lim_mem = parse_memory_to_mib(mem_lim)
    if parsed_lim_mem is None:
        if isinstance(limits, dict):
            limits["memory"] = DEFAULT_MEMORY_LIMIT
        else:
            setattr(limits, "memory", DEFAULT_MEMORY_LIMIT)
        logger.info(
            "Cluster Policy [%s]: Set default Memory limit '%s'",
            container_name,
            DEFAULT_MEMORY_LIMIT,
        )
    elif parsed_lim_mem > MAX_ALLOWED_MEMORY_MIB:
        max_mem_str = f"{int(MAX_ALLOWED_MEMORY_MIB)}Mi"
        logger.warning(
            "Cluster Policy [%s]: Memory limit '%s' exceeded max allowed. Clamping to '%s'.",
            container_name,
            mem_lim,
            max_mem_str,
        )
        if isinstance(limits, dict):
            limits["memory"] = max_mem_str
        else:
            setattr(limits, "memory", max_mem_str)


def _inject_metadata_delay_init_container(spec: Any) -> None:
    """Solution 1: Injects custom-init-setup container to delay for GKE metadata server readiness."""
    init_containers = getattr(spec, "init_containers", None)
    if init_containers is None:
        init_containers = []
        spec.init_containers = init_containers

    # Check if already injected
    has_init = any(
        getattr(c, "name", "") == "custom-init-setup" for c in init_containers
    )
    if has_init:
        return

    delay_cmd = (
        f"echo 'Sleeping for {INIT_CONTAINER_DELAY_SECONDS} seconds to allow time for "
        f"metadata server to start receiving requests from new GKE node...' && "
        f"sleep {INIT_CONTAINER_DELAY_SECONDS}"
    )

    try:
        from kubernetes.client import models as k8s

        custom_init = k8s.V1Container(
            name="custom-init-setup",
            image=INIT_CONTAINER_IMAGE,
            command=["sh", "-c", delay_cmd],
        )
    except (ImportError, Exception):
        # Fallback dict or Mock for environments without kubernetes package installed
        class _GenericInitContainer:
            def __init__(self, name, image, command):
                self.name = name
                self.image = image
                self.command = command

        custom_init = _GenericInitContainer(
            name="custom-init-setup",
            image=INIT_CONTAINER_IMAGE,
            command=["sh", "-c", delay_cmd],
        )

    init_containers.append(custom_init)
    logger.info(
        "Cluster Policy [pod_mutation_hook]: Successfully injected 'custom-init-setup' "
        "(%ds delay) for GKE metadata server readiness.",
        INIT_CONTAINER_DELAY_SECONDS,
    )


# ==============================================================================
# TASK POLICY (Airflow Cluster Policy)
# ==============================================================================


def task_policy(task: Any) -> None:
    """Enforces task-level operational standards across all operators.

    1. Enforces default execution_timeout if not specified.
    2. Enforces Solution 2 (Automated Retries & Backoff) on KubernetesPodOperator.
    3. Caps excessive retries across standard operators.
    """
    task_id = getattr(task, "task_id", "unknown")
    task_type = task.__class__.__name__

    # 1. Enforce execution timeout
    if getattr(task, "execution_timeout", None) is None:
        if "timeout" in str(task_id).lower():
            task.execution_timeout = timedelta(seconds=10)
            logger.info(
                "Cluster Policy [Task %s]: Applied demo execution_timeout of 10 seconds.",
                task_id,
            )
        else:
            task.execution_timeout = timedelta(hours=DEFAULT_TASK_TIMEOUT_HOURS)
            logger.info(
                "Cluster Policy [Task %s]: Applied default execution_timeout of %d hours.",
                task_id,
                DEFAULT_TASK_TIMEOUT_HOURS,
            )

    # 2. Enforce KPO Governance & Resource Clamping
    if task_type in ("KubernetesPodOperator", "GKEStartPodOperator"):
        # Enforce governance labels on the operator
        if getattr(task, "labels", None) is None:
            task.labels = {}
        task.labels.update(GOVERNANCE_LABELS)

        # Enforce resource clamping directly on operator container_resources
        res = getattr(task, "container_resources", None)
        if res is not None:
            reqs = getattr(res, "requests", None)
            if reqs:
                cpu_val = (
                    reqs.get("cpu")
                    if isinstance(reqs, dict)
                    else getattr(reqs, "cpu", None)
                )
                parsed_cpu = parse_cpu_to_cores(cpu_val)
                if parsed_cpu and parsed_cpu > MAX_ALLOWED_CPU_CORES:
                    max_cpu_str = f"{int(MAX_ALLOWED_CPU_CORES * 1000)}m"
                    logger.warning(
                        "Cluster Policy [Task %s]: CPU request '%s' (%.1f cores) exceeded max allowed (%.1f cores). Clamping to '%s'.",
                        task_id,
                        cpu_val,
                        parsed_cpu,
                        MAX_ALLOWED_CPU_CORES,
                        max_cpu_str,
                    )
                    if isinstance(reqs, dict):
                        reqs["cpu"] = max_cpu_str
                    else:
                        setattr(reqs, "cpu", max_cpu_str)

                mem_val = (
                    reqs.get("memory")
                    if isinstance(reqs, dict)
                    else getattr(reqs, "memory", None)
                )
                parsed_mem = parse_memory_to_mib(mem_val)
                if parsed_mem and parsed_mem > MAX_ALLOWED_MEMORY_MIB:
                    max_mem_str = f"{int(MAX_ALLOWED_MEMORY_MIB)}Mi"
                    logger.warning(
                        "Cluster Policy [Task %s]: Memory request '%s' (%.1f MiB) exceeded max allowed (%.1f MiB). Clamping to '%s'.",
                        task_id,
                        mem_val,
                        parsed_mem,
                        MAX_ALLOWED_MEMORY_MIB,
                        max_mem_str,
                    )
                    if isinstance(reqs, dict):
                        reqs["memory"] = max_mem_str
                    else:
                        setattr(reqs, "memory", max_mem_str)

            lims = getattr(res, "limits", None)
            if lims:
                cpu_lim = (
                    lims.get("cpu")
                    if isinstance(lims, dict)
                    else getattr(lims, "cpu", None)
                )
                parsed_lim_cpu = parse_cpu_to_cores(cpu_lim)
                if parsed_lim_cpu and parsed_lim_cpu > MAX_ALLOWED_CPU_CORES:
                    max_cpu_str = f"{int(MAX_ALLOWED_CPU_CORES * 1000)}m"
                    if isinstance(lims, dict):
                        lims["cpu"] = max_cpu_str
                    else:
                        setattr(lims, "cpu", max_cpu_str)

                mem_lim = (
                    lims.get("memory")
                    if isinstance(lims, dict)
                    else getattr(lims, "memory", None)
                )
                parsed_lim_mem = parse_memory_to_mib(mem_lim)
                if parsed_lim_mem and parsed_lim_mem > MAX_ALLOWED_MEMORY_MIB:
                    max_mem_str = f"{int(MAX_ALLOWED_MEMORY_MIB)}Mi"
                    if isinstance(lims, dict):
                        lims["memory"] = max_mem_str
                    else:
                        setattr(lims, "memory", max_mem_str)

        current_retries = getattr(task, "retries", 0) or 0
        if current_retries < KPO_MIN_RETRIES:
            task.retries = KPO_MIN_RETRIES
            logger.info(
                "Cluster Policy [Task %s]: Enforced minimum %d retries for %s.",
                task_id,
                KPO_MIN_RETRIES,
                task_type,
            )

        current_delay = getattr(task, "retry_delay", timedelta(0))
        min_delay = timedelta(seconds=KPO_MIN_RETRY_DELAY_SECONDS)
        if not current_delay or current_delay < min_delay:
            task.retry_delay = min_delay

        setattr(task, "retry_exponential_backoff", True)
        setattr(task, "max_retry_delay", timedelta(minutes=30))
    else:
        # Standard cap on other operator retries
        current_retries = getattr(task, "retries", 0) or 0
        if current_retries > MAX_ALLOWED_RETRIES:
            logger.warning(
                "Cluster Policy [Task %s]: Retries (%d) exceeded max allowed (%d). Clamping to %d.",
                task_id,
                current_retries,
                MAX_ALLOWED_RETRIES,
                MAX_ALLOWED_RETRIES,
            )
            task.retries = MAX_ALLOWED_RETRIES


# ==============================================================================
# DAG POLICY (Airflow Cluster Policy)
# ==============================================================================


def dag_policy(dag: Any) -> None:
    """Enforces metadata, concurrency, and gatekeeping governance on DAGs."""
    dag_id = getattr(dag, "dag_id", "unknown")

    # 1. Hard Gatekeeper: Catchup Flood Protection
    # Mutating catchup in memory does not recalculate the timetable;
    # therefore we reject the DAG at the front door.
    if getattr(dag, "catchup", False) is True:
        raise AirflowClusterPolicyViolation(
            f"Cluster Policy Violation [DAG {dag_id}]: 'catchup=True' is strictly forbidden "
            "on this cluster to prevent database overloading. Please set catchup=False."
        )

    # 2. Hard Gatekeeper: Ownership Validation
    default_args = getattr(dag, "default_args", {}) or {}
    owner = default_args.get("owner")
    if not owner or str(owner).lower() in ("airflow", "root"):
        raise AirflowClusterPolicyViolation(
            f"Cluster Policy Violation [DAG {dag_id}]: Owner cannot be '{owner}'. "
            "Every DAG must specify a valid team or contact email."
        )

    # 3. Soft Guardrail: Concurrency Clamping
    max_active_runs = getattr(dag, "max_active_runs", None)
    if max_active_runs is not None and max_active_runs > 2:
        dag.max_active_runs = 2
        logger.warning(
            "Cluster Policy [DAG %s]: Clamped max_active_runs from %s to 2 to prevent database overload.",
            dag_id,
            max_active_runs,
        )

    # 4. Soft Guardrail: Total Pipeline Duration Ceiling
    if getattr(dag, "dagrun_timeout", None) is None:
        dag.dagrun_timeout = timedelta(hours=4)
        logger.info(
            "Cluster Policy [DAG %s]: Injected default dagrun_timeout of 4 hours.",
            dag_id,
        )

    # 5. Soft Guardrail: Catalog Governance Tags
    tags = getattr(dag, "tags", None)
    if not tags:
        dag.tags = ["unassigned-domain", "policy:remediated"]
        logger.warning(
            "Cluster Policy [DAG %s]: Injected default categorization tags.",
            dag_id,
        )


# ==============================================================================
# RUNTIME WORKER LISTENER & AIRFLOW PLUGIN REGISTRATION
# ==============================================================================
_listener = None
try:
    from airflow.listeners import hookimpl

    class ClusterPolicyListener:
        """Enforces cluster policies at task execution time on Airflow workers."""

        @hookimpl
        def on_task_instance_running(self, previous_state, task_instance, session=None):
            task = getattr(task_instance, "task", None)
            if task:
                try:
                    task_policy(task)
                except Exception as e:
                    logger.error(
                        "Failed to apply task_policy in runtime listener: %s", e
                    )

    _listener = ClusterPolicyListener()
except Exception:
    _listener = None

try:
    from airflow.plugins_manager import AirflowPlugin

    class ComposerClusterPolicyPlugin(AirflowPlugin):
        name = "composer_cluster_policy_plugin"
        listeners = [_listener] if _listener else []
except Exception:
    pass
