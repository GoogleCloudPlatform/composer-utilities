# Cloud Composer Cluster Policy Manager

## Overview
This utility provides production-grade **Airflow Cluster Policies** for Google Cloud Composer (Composer 2 and Composer 3) to enforce resource governance, cluster stability, and operational standards.

When running containerized workloads with `KubernetesPodOperator` (KPO) or long-running database queries, tasks may request excessive compute resources (e.g., 8 vCPUs and 16 GiB RAM), omit execution timeouts, or deploy into unauthorized namespaces. This can lead to **GKE node exhaustion**, **worker starvation**, **runaway billing**, and **noisy neighbor problems** across shared Airflow environments.

Using Airflow Cluster Policies, this tool intercepts task and pod definitions before submission, dynamically enforcing safe resource caps, namespace boundaries, and governance metadata.

---

## Supported Deployment Architectures

According to Google Cloud Composer guidance and Apache Airflow documentation, there are two distinct deployment models:

### 1. Official Cloud Composer Method: PyPI Package with Entry Points (Option 2)
> **Google Recommended for Cloud Composer**: In Cloud Composer, directly customizing `airflow_local_settings.py` is explicitly unsupported because Composer uses internal hooks for its own KubernetesExecutor and monitoring tasks. Instead, cluster policies must be packaged as a **PyPI package** that exposes `airflow.policy` entry points.

This repository is structured as a standard Python package (`src/composer_cluster_policy`) with entry points registered in `pyproject.toml` and `setup.py`:
```toml
[project.entry-points."airflow.policy"]
task_policy = "composer_cluster_policy.policies:task_policy"
dag_policy = "composer_cluster_policy.policies:dag_policy"
pod_mutation_hook = "composer_cluster_policy.policies:pod_mutation_hook"
```

When installed in Cloud Composer as a PyPI dependency, Airflow's policy loader automatically discovers and executes these policies across all platform components without disrupting Composer's internal hooks.

### 2. Standalone / Local Airflow Method: `airflow_local_settings.py` (Option 1)
For local development, standalone Airflow testing, or CI/CD pipelines, `airflow_local_settings.py` is provided as a shim that imports directly from `composer_cluster_policy.policies`.

---

## Repository Structure

```
composer_cluster_policy/
├── README.md                      # Architecture and deployment guide
├── pyproject.toml                 # Package configuration with airflow.policy entry points
├── setup.py                       # Setuptools packaging build script
├── airflow_local_settings.py      # Standalone / local development shim
├── src/
│   └── composer_cluster_policy/
│       ├── __init__.py            # Package exports
│       └── policies.py            # Core Airflow cluster policies (Option 2 implementation)
├── dags/
│   ├── sample_kpo_resource_enforcement_dag.py  # KPO resource clamping demonstration DAG
│   └── sample_task_timeout_watchdog_dag.py     # Task execution timeout watchdog DAG
└── tests/
    ├── __init__.py
    └── test_cluster_policy.py     # Comprehensive unit test suite (14 tests)
```

---

## Key Features

1. **Pod Resource Governance (`pod_mutation_hook`):**
   * **Automatic Clamping:** Intercepts pod definitions and clamps excessive CPU requests/limits (e.g., `8000m` -> `4000m`) and Memory (e.g., `16000Mi` -> `8192Mi`).
   * **Composer-Safe Non-Destructive Hook:** Explicitly avoids mutating internal Composer executor worker pods, ensuring commands, environment variables, and container names are never disrupted.
   * **Default Fallback Injection:** Injects safe default requests (`500m` CPU, `1024Mi` RAM) and limits (`2000m` CPU, `4096Mi` RAM) if omitted by DAG authors.
   * **Namespace Enforcement:** Restricts execution to approved namespaces (defaults to `composer-user-workloads`).
   * **FinOps Metadata:** Automatically attaches tracking and cost-allocation labels (`managed-by: composer-cluster-policy`, `policy-enforced: true`).
   * **Composer 2 Init Container Delay:** Optionally injects `custom-init-setup` to prevent GKE metadata server cold-start race conditions in Composer 2 environments.

2. **Task Execution Governance (`task_policy`):**
   * **Execution Timeout Watchdog:** Injects mandatory upper-bound task run durations (default 4 hours; 10s watchdog for demo tasks) to kill hanging queries and prevent worker starvation.
   * **KPO Resilience:** Automatically sets minimum retries (2) and exponential backoff for `KubernetesPodOperator` tasks.
   * **Retry Clamping:** Caps excessive retry attempts on standard tasks (max 3).

3. **DAG Metadata Standards (`dag_policy`):**
   * **Tags & Ownership:** Audits DAG definitions to ensure valid ownership and categorization tags.
   * **Catchup Protection:** Warns or disables catchup on unmanaged DAGs to prevent scheduler overloading.

---

## Deployment Guide: Official PyPI Package (Option 2)

### Step 1: Build the Wheel
From the `composer_cluster_policy` directory, build the wheel:
```bash
python3 -m pip install wheel setuptools
pip wheel --no-deps -w dist .
# Generates: dist/composer_cluster_policy-1.0.0-py3-none-any.whl
```

### Step 2: Upload to Cloud Storage
Upload the wheel to your Cloud Composer environment bucket's `data/` folder:
```bash
export COMPOSER_ENVIRONMENT="your-composer-env"
export LOCATION="us-central1"
export BUCKET=$(gcloud composer environments describe $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --format="value(config.storageConfig.bucket)")

gcloud storage cp dist/composer_cluster_policy-1.0.0-py3-none-any.whl gs://$BUCKET/data/
```

### Step 3: Install as a Python Package in Cloud Composer
Create or update your `requirements.txt` to include the wheel path:
```bash
echo "/home/airflow/gcs/data/composer_cluster_policy-1.0.0-py3-none-any.whl" > requirements.txt

gcloud composer environments update $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --update-pypi-packages-from-file=requirements.txt
```

---

## Verification & Testing

### 1. Run Unit Tests Locally
```bash
python3 -m unittest discover -s tests
# Ran 14 tests in 0.001s, OK
```

### 2. Deploy Verification DAGs
Deploy the sample verification DAGs to your environment:
```bash
gcloud storage cp dags/sample_kpo_resource_enforcement_dag.py gs://$BUCKET/dags/
gcloud storage cp dags/sample_task_timeout_watchdog_dag.py gs://$BUCKET/dags/
```

### 3. Verify Live Execution
* **KPO Resource Clamping**: Trigger `sample_kpo_resource_enforcement`. In the task logs, observe CPU clamped from 8000m -> 4000m, Memory clamped from 16000Mi -> 8192Mi, and `managed-by: composer-cluster-policy` attached to the pod.
* **Task Timeout Watchdog**: Trigger `sample_task_timeout_watchdog`. Observe the hanging 30s query actively killed at 10.3s via `SIGTERM` / `AirflowTaskTimeout`, immediately freeing worker capacity.
