# Cloud Composer Cluster Policy Manager

## Overview
This utility provides production-grade **Airflow Cluster Policies** for Google Cloud Composer (Composer 2 and Composer 3) to enforce resource governance, cluster stability, and operational standards.

When running containerized workloads with `KubernetesPodOperator` (KPO) or `GKEStartPodOperator`, tasks may request excessive compute resources (e.g., 8 vCPUs and 16 GiB RAM), omit resource limits, or deploy into unauthorized namespaces. This can lead to **GKE node exhaustion**, **pending pod deadlocks**, **runaway billing**, or **noisy neighbor problems** across shared Airflow workers.

Using Airflow Cluster Policies (`airflow_local_settings.py`), this tool intercepts task and pod definitions before submission, dynamically enforcing safe resource caps, namespace boundaries, and governance metadata.

---

## Key Features

1. **Pod Resource Governance (`pod_mutation_hook`):**
   * **Automatic Clamping:** Intercepts pod definitions and clamps excessive CPU requests/limits (e.g., capping `8000m` -> `4000m`) and Memory (e.g., `16000Mi` -> `8192Mi`).
   * **Default Fallback Injection:** Injects safe default requests (`500m` CPU, `1024Mi` RAM) and limits (`2000m` CPU, `4096Mi` RAM) if omitted by DAG authors.
   * **Namespace Enforcement:** Restricts execution to approved namespaces (defaults to `composer-user-workloads`).
   * **Standardized Metadata:** Automatically attaches tracking and cost-allocation labels (e.g., `managed-by: composer-cluster-policy`, `policy-enforced: true`).

2. **Task Execution Governance (`task_policy`):**
   * **Default Execution Timeouts:** Enforces maximum task run durations (default 4 hours) to eliminate hanging tasks.
   * **Retry Limits:** Caps excessive retry attempts (default max 3 retries) with exponential backoff encouragement.

3. **DAG Metadata Standards (`dag_policy`):**
   * **Tags & Ownership:** Audits DAG definitions to ensure valid ownership and categorization tags.

---

## Repository Structure

```
composer_cluster_policy/
├── README.md                      # Comprehensive user and deployment guide
├── airflow_local_settings.py      # Core Airflow cluster policy hooks
├── dags/
│   └── sample_kpo_resource_enforcement_dag.py  # Standardized demonstration DAG
└── tests/
    ├── __init__.py
    └── test_cluster_policy.py     # Unit test suite
```

---

## Quick Setup

### 1. Deploy the Cluster Policy to Cloud Composer
Copy `airflow_local_settings.py` into your Cloud Composer environment's `plugins/` directory:

```bash
# Set your environment variables
export COMPOSER_ENVIRONMENT="your-composer-env"
export LOCATION="us-east1"

# Get the DAGs/Plugins GCS bucket
export BUCKET=$(gcloud composer environments describe $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --format="value(config.storageConfig.bucket)")

# Upload the policy file to the plugins/ folder
gcloud storage cp composer_cluster_policy/airflow_local_settings.py gs://$BUCKET/plugins/
```

### 2. Deploy the Sample Verification DAG
Deploy the sample DAG to verify policy enforcement:

```bash
gcloud storage cp composer_cluster_policy/dags/sample_kpo_resource_enforcement_dag.py gs://$BUCKET/dags/
```

### 3. Verify Execution
1. Open your Cloud Composer Airflow Web UI.
2. Trigger the DAG **`sample_kpo_resource_enforcement`**.
3. Check the task logs for **`extract_gcs_storage_metadata`** or inspect the created Kubernetes Pod in the GKE Workloads console.
4. You will see log messages indicating that the 8000m CPU and 16000Mi RAM requests were intercepted and clamped to 4000m and 8192Mi:
   ```text
   Cluster Policy [kpo-extract-storage-metadata]: CPU request '8000m' (8.0 cores) exceeded max allowed (4.0 cores). Clamping to '4000m'.
   Cluster Policy [kpo-extract-storage-metadata]: Memory request '16000Mi' (16000.0 MiB) exceeded max allowed (8192.0 MiB). Clamping to '8192Mi'.
   ```

---

## Configuration Options

The policy behavior can be customized via Airflow Environment Variables or directly in `airflow_local_settings.py`:

| Variable / Parameter | Default | Description |
| :--- | :--- | :--- |
| `COMPOSER_POLICY_MAX_CPU_CORES` | `4.0` | Maximum allowed CPU per container in cores (4000m). |
| `COMPOSER_POLICY_MAX_MEMORY_MIB` | `8192.0` | Maximum allowed Memory per container in MiB (8 GiB). |
| `COMPOSER_POLICY_DEFAULT_CPU_REQUEST` | `500m` | Default CPU request if omitted by task. |
| `COMPOSER_POLICY_DEFAULT_MEMORY_REQUEST` | `1024Mi` | Default Memory request if omitted by task. |
| `COMPOSER_POLICY_DEFAULT_CPU_LIMIT` | `2000m` | Default CPU limit if omitted by task. |
| `COMPOSER_POLICY_DEFAULT_MEMORY_LIMIT` | `4096Mi` | Default Memory limit if omitted by task. |
| `COMPOSER_POLICY_ALLOWED_NAMESPACES` | `composer-user-workloads,default` | Comma-separated list of permitted Kubernetes namespaces. |
| `COMPOSER_POLICY_TASK_TIMEOUT_HOURS` | `4` | Default execution timeout applied to tasks without explicit timeouts. |
| `COMPOSER_POLICY_MAX_RETRIES` | `3` | Maximum allowed retries per task. |

To set these environment variables on your Composer environment:
```bash
gcloud composer environments update $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --update-env-variables=COMPOSER_POLICY_MAX_CPU_CORES=4.0,COMPOSER_POLICY_MAX_MEMORY_MIB=8192.0
```

---

## Running Unit Tests

Run the test suite locally:

```bash
python3 -m unittest discover -s composer_cluster_policy/tests -p "test_*.py" -v
```
