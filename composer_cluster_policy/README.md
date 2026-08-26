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

3. **DAG Metadata & Governance Standards (`dag_policy`):**
   * **Catchup Stampede Gatekeeping:** Raises `AirflowClusterPolicyViolation` if `catchup=True` is specified with an unmanaged timetable, preventing scheduler and metadata database saturation.
   * **Ownership Enforcement:** Blocks unassigned pipelines (`owner="root"` or `"airflow"`).
   * **Concurrency Clamping:** Clamps `max_active_runs` to a safe threshold (default 2) to protect database connection pools.
   * **Global Run Duration Ceiling:** Injects `dagrun_timeout` (default 4 hours) to prevent cascade task deadlocks.
   * **Catalog Tags:** Injects default tags (`["unassigned-domain", "policy:remediated"]`) for FinOps cost allocation and UI searchability.

---

## Architectural Insights & Pitfalls Encountered

When deploying custom cluster policies to modern Cloud Composer (Composer 2.9+ and Composer 3 / Airflow 3), central platform teams encounter several critical platform constraints:

### 1. Why `airflow_local_settings.py` in GCS Fails (Bug `b/381815171`)
* In Composer 1 and early Composer 2, users placed `airflow_local_settings.py` in `dags/` or `plugins/`.
* **The Pitfall**: Google Cloud Composer relies on internal `airflow_local_settings` hooks for GKE worker telemetry, environment variable management, and Kubernetes executor initialization. Overwriting `airflow_local_settings.py` directly is explicitly unsupported and can break internal Composer services.
* **The Fix**: Policies must be packaged as an isolated Python package with entry points registered under `[airflow.policy]`.

### 2. Airflow 3 Task SDK Process Isolation
* In Airflow 3, worker execution runs in a decoupled Task SDK process (`RuntimeTaskInstance`).
* **The Pitfall**: On the worker, `task.dag` does not exist in memory. Therefore, `dag_policy` **cannot** be evaluated inside worker hooks (`task_policy` or task execution listeners).
* **The Fix**: `dag_policy` is strictly evaluated during DAG parsing inside the **`dag-processor`** container. The `dag-processor` does not read GCS `plugins/`, making PyPI package entry points the only viable mechanism to enforce DAG-level policies.

### 3. Cloud Build Container Isolation (Why GCS Wheels Fail)
* When updating dependencies via `gcloud composer environments update --update-pypi-packages`, `pip install` runs inside an ephemeral **Google Cloud Build** container, not on the live GKE cluster.
* **The Pitfall**: Cloud Build does not have Cloud Storage FUSE mounted. Specifying paths like `/home/airflow/gcs/data/package.whl` in `requirements.txt` fails with `FileNotFoundError`.
* **The Pitfall (PEP-508 Direct URLs)**: Specifying `package @ git+https://...` fails with an invalid PEP-508 package identifier in Composer's API validation.
* **The Fix**: Host wheels in **Google Cloud Artifact Registry** (a private Python repository within your GCP project) and point Composer to it via `gs://<bucket>/config/pip/pip.conf`.

### 4. Pluggy Interface Requirements (`@hookimpl` & Module Entrypoint)
* Apache Airflow uses the `Pluggy` plugin engine to discover cluster policies from `[airflow.policy]`.
* **The Pitfall**: If policy functions do not have the `@hookimpl` decorator (`from airflow.policies import hookimpl`), Pluggy loads the package but discovers 0 hook implementations, silently ignoring the policy.
* **The Fix**:
  1. Decorate all policy functions with `@hookimpl`:
     ```python
     from airflow.policies import hookimpl


     @hookimpl
     def dag_policy(dag: Any) -> None:
       ...
```
  2. Point the entry point in `pyproject.toml` or `setup.py` to the **module**, not individual function names:
     ```toml
     [project.entry-points."airflow.policy"]
     composer_cluster_policy = "composer_cluster_policy.policies"
     ```

---

## Deployment Guide: Enterprise Artifact Registry Method

### Option A: Turn-Key Automated Deployment (Recommended)

Run the included deployment script to build the wheel, upload to Artifact Registry, configure `pip.conf`, and trigger the Composer update in a single command:

```bash
# Usage: ./deploy_policy.sh <ENV_NAME> <LOCATION> <ARTIFACT_REGISTRY_REPO>
./deploy_policy.sh composer-3-airflow-3 us-central1 composer-packages
```

---

### Option B: Manual Step-by-Step Deployment

#### Step 1: Create Private Artifact Registry Python Repository
```bash
gcloud artifacts repositories create composer-packages \
    --repository-format=python \
    --location=us-central1 \
    --description="Private repository for Cloud Composer cluster policies"
```

#### Step 2: Grant Permissions to Composer & Cloud Build
```bash
COMPOSER_SA=$(gcloud composer environments describe composer-3-airflow-3 \
    --location=us-central1 \
    --format="value(config.nodeConfig.serviceAccount)")
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUM=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUDBUILD_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"

gcloud artifacts repositories add-iam-policy-binding composer-packages \
    --location=us-central1 \
    --member="serviceAccount:${COMPOSER_SA}" \
    --role="roles/artifactregistry.reader"

gcloud artifacts repositories add-iam-policy-binding composer-packages \
    --location=us-central1 \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/artifactregistry.reader"
```

#### Step 3: Build & Upload the Wheel
```bash
# 1. Build
pip3 wheel --no-deps -w dist/ .

# 2. Upload with twine using OAuth2 access token
python3 -m twine upload \
    --username oauth2accesstoken \
    --password "$(gcloud auth print-access-token)" \
    --repository-url https://us-central1-python.pkg.dev/$PROJECT_ID/composer-packages/ \
    dist/composer_cluster_policy-*.whl
```

#### Step 4: Configure `pip.conf` in Environment Cloud Storage
```bash
BUCKET=$(gcloud composer environments describe composer-3-airflow-3 \
    --location=us-central1 \
    --format="value(config.storageConfig.bucket)")

cat << EOF > pip.conf
[global]
extra-index-url = https://us-central1-python.pkg.dev/${PROJECT_ID}/composer-packages/simple/
EOF

gcloud storage cp pip.conf gs://${BUCKET}/config/pip/pip.conf
rm pip.conf
```

#### Step 5: Update Cloud Composer Environment
```bash
echo "composer-cluster-policy==1.0.1" > requirements.txt

gcloud composer environments update composer-3-airflow-3 \
    --location=us-central1 \
    --update-pypi-packages-from-file=requirements.txt \
    --async
```

---

## Participant Guide: Testing & Verifying with Your Repo

For workshop participants running DAGs against the governed cluster:

### 1. Run Unit Tests Locally (Shift-Left Validation)
Before deploying any DAG, verify policies locally:
```bash
python3 -m unittest discover -s tests
# Ran 16 tests in 0.001s, OK
```

### 2. Deploy Sample Verification DAGs
```bash
# Upload sample demonstration DAGs
gcloud storage cp dags/sample_dag_policy_violations_dag.py gs://${BUCKET}/dags/
gcloud storage cp dags/sample_task_timeout_watchdog_dag.py gs://${BUCKET}/dags/
gcloud storage cp dags/sample_kpo_resource_enforcement_dag.py gs://${BUCKET}/dags/
```

### 3. Verify Live Governance Across the 3 Levels

1. **DAG-Level (`sample_dag_policy_violations_dag.py`)**:
   * **Anti-Pattern Tested**: `catchup=True`, `owner="root"`, `max_active_runs=16`, `tags=[]`.
   * **Observed Result**: The DAG Processor flags the DAG. `AirflowClusterPolicyViolation` blocks the catchup stampede at the front door with a bright red banner in the Airflow UI, scheduling 0 runs.

2. **Task-Level (`sample_task_timeout_watchdog_dag.py`)**:
   * **Anti-Pattern Tested**: Unbounded 30-second hanging query without an `execution_timeout`.
   * **Observed Result**: `task_policy` injects a 10s watchdog. The query is terminated at 10.3s via `SIGTERM` / `AirflowTaskTimeout`, immediately freeing the Celery worker slot.

3. **Pod-Level (`sample_kpo_resource_enforcement_dag.py`)**:
   * **Anti-Pattern Tested**: Excessive 8-core CPU and 16 GiB RAM request on `KubernetesPodOperator`.
   * **Observed Result**: `pod_mutation_hook` intercepts the pod prior to GKE scheduling, clamping CPU to 4000m and RAM to 8192Mi, and attaching `managed-by: composer-cluster-policy` labels.
