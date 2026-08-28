# Cloud Composer Cluster Policy Governance Suite

## Overview
This repository provides an enterprise-grade, production-ready **Airflow Cluster Policy Framework** for Google Cloud Composer (supporting both Composer 2 and Composer 3 / Airflow 3). It enables platform engineering and cloud operations teams to enforce operational guardrails, prevent cluster resource exhaustion, protect Celery worker slots, control Kubernetes container sizing, and enforce enterprise FinOps metadata across shared, multi-tenant Airflow environments.

---

## 3-Tier Multi-Layer Governance Architecture

Modern data orchestration platforms face risks across three distinct execution phases. This framework enforces governance across all three:

```
                            Airflow Cluster Policy Architecture
                                             │
            ┌────────────────────────────────┼────────────────────────────────┐
            ▼                                ▼                                ▼
     [1. DAG LEVEL]                   [2. TASK LEVEL]                  [3. POD LEVEL]
   Parse-Time Perimeter             Worker Slot Resilience           Container Infrastructure
   Evaluated in dag-processor       Evaluated in Celery Workers      Evaluated Pre-GKE Dispatch
   ─────────────────────────        ───────────────────────────      ──────────────────────────
   • Catchup stampede gatekeeper    • Hanging query watchdog         • Autonomous CPU/RAM clamping
   • Ownership validation           • Runaway retry throttling       • Namespace boundary routing
   • In-memory concurrency limits   • Global task duration ceiling   • FinOps metadata injection
   • Automated FinOps cataloging    • Spot/preemption resilience     • GKE Workload Identity guard
```

1. **DAG-Level Governance (`dag_policy`)**:
   * **Catchup Stampede Defense**: Intercepts unmanaged historical backfills (`catchup=True`), raising an `AirflowClusterPolicyViolation` that halts parsing at the perimeter before tasks can saturate the metadata database.
   * **Mandatory Ownership**: Rejects unassigned or default ownership (`owner="root"`, `"airflow"`, or `None`).
   * **Concurrency Clamping**: Transparently throttles `max_active_runs` in memory to prevent downstream database connection exhaustion.
   * **FinOps Cataloging**: Automatically injects business-unit and policy tracking tags into the DAG metadata.

2. **Task-Level Governance (`task_policy`)**:
   * **Hanging Query Watchdog**: Intercepts long-running or frozen database queries and unindexed network calls, actively terminating them via `SIGTERM` (`AirflowTaskTimeout`) to prevent worker slot starvation.
   * **Runaway Retry Throttling**: Caps high retry counts (e.g. `retries=50` -> `3`) and enforces exponential backoff, preventing outage amplification (DDoS) against third-party APIs.
   * **Production Duration Ceilings**: Injects an upper-bound execution timeout (default 4 hours) on every task lacking duration boundaries.
   * **Container Task Resilience**: Automatically enforces minimum retries (2) on containerized operators (`KubernetesPodOperator`) to gracefully recover from transient GKE node scale-outs and spot evictions.

3. **Pod-Level Governance (`pod_mutation_hook`)**:
   * **Autonomous Resource Clamping**: Intercepts the raw Kubernetes pod specification (`k8s.V1Pod`) in memory and clamps excessive CPU requests (e.g., `8000m` -> `4000m`) and RAM (e.g., `16000Mi` -> `8192Mi`) before GKE API dispatch.
   * **Namespace Governance**: Automatically reroutes unauthorized or unmanaged namespace declarations into the dedicated `composer-user-workloads` pool.
   * **Corporate FinOps Tagging**: Auto-injects enterprise tracking labels (`managed-by: composer-cluster-policy`, `policy-enforced: true`) to ensure 100% billing attribution.
   * **Platform Protection**: Non-destructive safety checks guarantee internal Composer executor worker pods and monitoring agents are never altered.

---

## Architectural Insights & Pitfalls Encountered

When deploying custom cluster policies to modern Cloud Composer (Composer 2.9+ and Composer 3 / Airflow 3), central platform teams encounter several critical platform realities:

### 1. Why `airflow_local_settings.py` in GCS Fails on Cloud Composer
* In Composer 1 and early Composer 2, users placed `airflow_local_settings.py` in `dags/` or `plugins/`.
* **The Pitfall**: Google Cloud Composer relies on internal `airflow_local_settings` hooks for GKE worker telemetry, environment variable management, and Kubernetes executor initialization. Overwriting `airflow_local_settings.py` directly in Cloud Storage is unsupported and can break internal platform services.
* **The Fix**: Policies must be packaged as an isolated Python package with entry points registered under `[airflow.policy]`.

### 2. Airflow 3 Task SDK Process Isolation
* In Airflow 3, worker execution runs in a decoupled Task SDK process (`RuntimeTaskInstance`).
* **The Pitfall**: On the worker, `task.dag` does not exist in memory. Therefore, `dag_policy` **cannot** be evaluated inside worker hooks (`task_policy` or task execution listeners).
* **The Fix**: `dag_policy` is strictly evaluated during DAG parsing inside the **`dag-processor`** container. The `dag-processor` does not read GCS `plugins/`, making PyPI package entry points the only viable mechanism to enforce DAG-level policies across all cluster components.

### 3. Cloud Build Container Isolation (Why GCS Wheels Fail)
* When updating dependencies via `gcloud composer environments update --update-pypi-packages`, `pip install` runs inside an ephemeral **Google Cloud Build** container, not on the live GKE cluster.
* **The Pitfall (GCS Paths)**: Cloud Build does not have Cloud Storage FUSE mounted. Specifying paths like `/home/airflow/gcs/data/package.whl` in `requirements.txt` fails with `FileNotFoundError`.
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
     def dag_policy(dag: Any) -> None: ...

     @hookimpl
     def task_policy(task: Any) -> None: ...

     @hookimpl
     def pod_mutation_hook(pod: Any) -> None: ...
     ```
  2. Point the entry point in `pyproject.toml` or `setup.py` to the **module**, not individual function names:
     ```toml
     [project.entry-points."airflow.policy"]
     composer_cluster_policy = "composer_cluster_policy.policies"
     ```

### 5. Platform Exemption Guards
* Cloud Composer continuously monitors cluster health via an internal DAG named `airflow_monitoring.py`.
* **The Pitfall**: Because Google does not declare an `owner` attribute on `airflow_monitoring`, a naive `dag_policy` will raise an `AirflowClusterPolicyViolation`, crashing Composer's internal health checks.
* **The Fix**: Policies must explicitly exempt internal workloads:
  ```python
  if dag_id == "airflow_monitoring" or str(dag_id).startswith(("airflow_monitoring", "composer_sample")):
      return
  ```

---

## Repository Structure

```
composer_cluster_policy/
├── README.md                      # Comprehensive architecture and deployment guide
├── deploy_policy.sh               # Turn-key 1-command deployment script
├── pyproject.toml                 # Package configuration with [airflow.policy] entry point
├── setup.py                       # Distribution build script
├── airflow_local_settings.py      # Standalone / local development shim
├── src/
│   └── composer_cluster_policy/
│       ├── __init__.py            # Package exports (v1.0.2)
│       └── policies.py            # Core Airflow cluster policies with @hookimpl
├── dags/                          # Symmetrical 3-Tier Demonstration Suite
│   ├── sample_dag_policy_violations_dag.py    # Tier 1 Before: Catchup flood & invalid owner (Red banner)
│   ├── sample_dag_policy_remediation_dag.py   # Tier 1 After: Concurrency clamped & FinOps tags injected
│   ├── sample_task_policy_violations_dag.py   # Tier 2 Before: Unshielded baseline (30s hang, 50 retries)
│   ├── sample_task_policy_remediation_dag.py  # Tier 2 After: Watchdog kill @ 10s & retries clamped to 3
│   ├── sample_pod_policy_violations_dag.py    # Tier 3 Before: Unshielded KPO (8 CPUs, 16GB RAM, wrong namespace)
│   └── sample_pod_policy_remediation_dag.py   # Tier 3 After: Clamped to 4 CPUs/8GB, namespace overridden
└── tests/
    ├── __init__.py
    └── test_cluster_policy.py     # Complete unit test suite (17 tests)
```

---

## Deployment Guide: Enterprise Artifact Registry Method

This repository supports three flexible ways to deploy the policy package:

---

### Option A: Automated GitOps CI/CD Deployment (`cicd/cloudbuild.yaml`)
> **Recommended for Production Environments and Enterprise Platform Teams**

This repository includes a unified Google Cloud Build CI/CD pipeline (`cicd/cloudbuild.yaml`) that combines policy building, dependency management, and DAG synchronization into a single automated execution.

#### What Cloud Build Automates:
1. **Static Validation**: Runs `ruff check` on policy and DAG code.
2. **Container Parity Testing**: Resolves the exact target Cloud Composer base Docker image (via `cicd/get_composer_tagged_image.py`) and executes unit and integration tests inside that container.
3. **Artifact Registry Publishing**: Compiles the `composer-cluster-policy` wheel and uploads it directly to Google Cloud Artifact Registry.
4. **Environment Package Rollout**: Dynamically writes `gs://${BUCKET}/config/pip/pip.conf` pointing to Artifact Registry, then updates Cloud Composer dependencies via `requirements.txt`.
5. **DAG Synchronization**: Synchronizes all DAGs (`cicd/dags/`) directly to the Cloud Storage `dags/` bucket via `gcloud storage rsync`.

#### Triggering the Automated Build:
```bash
gcloud builds submit --config=cicd/cloudbuild.yaml --substitutions=LOCATION="us-central1"
```
*Result: Once the build finishes, your Cloud Composer environment is 100% ready—policies are active across all pods, and all demonstration DAGs are live in the UI!*

---

### Option B: Turn-Key CLI Script (`deploy_policy.sh`)
> **Recommended for Sandboxes, Dev Environments, or Fast Direct Setup**

For users who want to deploy without configuring a CI/CD trigger, run the included turn-key bash script:

```bash
chmod +x deploy_policy.sh

# Usage: ./deploy_policy.sh <ENV_NAME> <LOCATION> <PROJECT_ID>
./deploy_policy.sh composer-3-airflow-3 us-central1 composer-utils
```

---

### Option C: Manual Step-by-Step Deployment

For teams with customized deployment orchestrators, follow the manual steps:

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
# 1. Build wheel distribution
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
    --format="value(storageConfig.bucket)")
BUCKET="${BUCKET#gs://}"

cat << EOF > pip.conf
[global]
extra-index-url = https://us-central1-python.pkg.dev/${PROJECT_ID}/composer-packages/simple/
EOF

gcloud storage cp pip.conf gs://${BUCKET}/config/pip/pip.conf
rm pip.conf
```

#### Step 5: Update Cloud Composer Environment
```bash
echo "composer-cluster-policy==1.0.2" > requirements.txt

gcloud composer environments update composer-3-airflow-3 \
    --location=us-central1 \
    --update-pypi-packages-from-file=requirements.txt \
    --async
```

---

## Hands-On Verification: Testing Governance Across All 3 Tiers

### 1. Run Unit Tests Locally (Shift-Left Validation)
Before deploying any pipeline, verify policies using the offline test harness:
```bash
python3 -m unittest discover -s tests
# Ran 17 tests in 0.002s - OK
```

### 2. Live Cluster Verification Across the 3 Tiers

#### Step 1: Clone Repository & Deploy Demonstration DAGs

##### If cloning for the first time:
```bash
git clone https://github.com/GoogleCloudPlatform/composer-utilities.git
cd composer-utilities/composer_cluster_policy
```

##### If repository is already cloned:
```bash
cd composer-utilities/composer_cluster_policy
# Or if already in the repo root:
# cd composer_cluster_policy
```

##### Sync Demonstration DAGs to Cloud Storage:
```bash
BUCKET="$(gcloud composer environments describe large-central1-airflow3 \
    --location=us-central1 \
    --format="value(storageConfig.bucket)")"
BUCKET="${BUCKET#gs://}"

gcloud storage cp dags/*.py "gs://${BUCKET}/dags/"
```

---

#### Tier 1: DAG-Level Governance (`dag_policy`)
* **Before (`sample_dag_policy_violations_dag.py`)**:
  * **Anti-Patterns**: `catchup=True`, `owner="root"`, `max_active_runs=16`, `tags=[]`.
  * **Observed Result**: The DAG Processor flags the DAG. `AirflowClusterPolicyViolation` blocks the catchup stampede at the front door with a bright red banner in the Airflow UI, scheduling 0 runs.
* **After (`sample_dag_policy_remediation_dag.py`)**:
  * **Remediation**: `catchup=False`, `owner="data-engineering-team"`.
  * **Observed Result**: `dag_policy` auto-remediates the pipeline: clamps `max_active_runs` from **16 to 2**, injects a **4-hour dagrun timeout ceiling**, and attaches FinOps catalog tags.

#### Tier 2: Task-Level Governance (`task_policy`)
* **Before (`sample_task_policy_violations_dag.py`)**:
  * **Anti-Patterns**: 30-second hanging query without timeout, `retries=50` with 0s delay. Uses the `composer_sample_` exemption prefix.
  * **Observed Result**: Runs unshielded. The query hogs the worker slot for the full 30 seconds without duration limits.
* **After (`sample_task_policy_remediation_dag.py`)**:
  * **Remediations**:
    * `runaway_retries_clamped`: Intercepted on worker and clamped from **50 down to 3 retries**.
    * `resilient_standard_task`: Injected with a **4-hour timeout ceiling**.
    * `hanging_query_timeout_watchdog`: Intercepted by the **10s watchdog** and actively terminated at **10.3s** via `SIGTERM` (`AirflowTaskTimeout`), immediately freeing the worker slot!

#### Tier 3: Pod-Level Governance (`pod_mutation_hook`)
* **Before (`sample_pod_policy_violations_dag.py`)**:
  * **Anti-Patterns**: Requests **8 cores (`8000m`)**, **16 GiB RAM (`16000Mi`)**, targets an unapproved namespace with zero tracking labels.
  * **Observed Result**: Runs unshielded, exposing the cluster to GKE node quota exhaustion and untracked compute costs.
* **After (`sample_pod_policy_remediation_dag.py`)**:
  * **Remediations**: `pod_mutation_hook` intercepts the `k8s.V1Pod` spec in memory pre-GKE submission:
    * **CPU Clamped**: 8.0 cores clamped down to **4.0 cores (`4000m`)**.
    * **RAM Clamped**: 16.0 GiB clamped down to **8.0 GiB (`8192Mi`)**.
    * **Namespace Enforced**: Overridden from `unauthorized-tenant-namespace` to **`composer-user-workloads`**.
    * **FinOps Labels Injected**: `managed-by: composer-cluster-policy`, `policy-enforced: true`.
