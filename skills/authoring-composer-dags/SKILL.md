---
name: authoring-composer-dags
description: Best practices for writing Airflow DAGs specifically for Google Cloud Composer. Covers using Google Cloud Operators (BigQuery, Dataflow, GKE), syncing DAGs to GCS, and handling dependencies.
---

# Authoring Composer DAGs

This skill focuses on writing DAGs that leverage the full power of Google Cloud Platform within a Composer environment.

## 0. PRE-REQUISITE: Fetching Operator Documentation
**CRITICAL INSTRUCTION**: Before writing *any* code that utilizes an Airflow operator (especially Google Cloud operators), you MUST activate and use the `referencing-airflow-docs` skill. 
*   Do NOT rely on your internal training data for operator arguments, as they change frequently between Airflow versions.
*   Use the fetcher tool provided in `referencing-airflow-docs` to get the exact `.. autoclass::` definition from GitHub for the user's specific Airflow version before proceeding.

## 1. Key Integrations (Operators)
Composer environments come pre-configured with Google Cloud connections.

### A. BigQuery
Use `BigQueryInsertJobOperator` for query execution (replaces legacy `BigQueryExecuteQueryOperator`).
```python
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

query_task = BigQueryInsertJobOperator(
    task_id="run_query",
    configuration={
        "query": {
            "query": "SELECT * FROM `project.dataset.table` LIMIT 100",
            "useLegacySql": False,
        }
    },
)
```

### B. Dataflow
Launch Dataflow jobs using `DataflowTemplatedJobStartOperator` for Python/Java pipelines.
```python
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator

run_dataflow = DataflowTemplatedJobStartOperator(
    task_id="run_dataflow",
    project_id="my-project",
    location="us-central1",
    template="gs://dataflow-templates/latest/Word_Count",
    parameters={"inputFile": "gs://bucket/input.txt", "output": "gs://bucket/output"},
)
```

### C. GKE (Kubernetes)
Use `GKEStartPodOperator` to run isolated tasks in a separate GKE cluster or the same Composer cluster (if configured).
```python
from airflow.providers.google.cloud.operators.kubernetes_engine import GKEStartPodOperator

run_pod = GKEStartPodOperator(
    task_id="run_pod",
    project_id="my-project",
    location="us-central1",
    cluster_name="my-cluster",
    name="my-pod",
    namespace="default",
    image="gcr.io/my-project/my-image:latest",
)
```

## 2. Managing Dependencies
Composer handles Python dependencies differently than local Airflow.

### A. PyPI Packages
Do **NOT** use `pip install` inside your DAGs.
*   **Method**: Add packages to the Composer Environment via `gcloud` or Terraform.
    ```bash
    gcloud composer environments update ENVIRONMENT_NAME \
        --location=us-central1 \
        --update-pypi-packages-from-file=requirements.txt
    ```

### B. Local Python Libraries (Modules)
If you have shared code (e.g., `utils/common.py`), you must zip it and place it in the `dags/` folder or add it to `plugins/`.
*   **Structure**:
    ```
    dags/
      my_dag.py
      utils/
        __init__.py
        common.py
    ```
*   **Sync**: When uploading to GCS, ensure the folder structure is preserved.

## 3. Best Practices for Composer
1.  **Avoid Local File Storage**: Workers are ephemeral. Do not store files locally (`/tmp` is okay for small transient data, but use GCS for passing data between tasks).
2.  **Use XCom Backend**: Composer 2/3 can use GCS for custom XCom backends to handle large data.
3.  **Heavy Tasks**: Offload heavy processing (Pandas, huge requires) to `GKEStartPodOperator` or Dataflow to avoid overloading the Airflow Worker.

## 4. Testing
See the **testing-composer-dags** skill for how to validate these DAGs using `composer-dev`.

## 5. Managing DAG Metadata
Good metadata allows teams to filter, monitor, and diagnose issues across hundreds of DAGs efficiently.

1.  **Apply Tags for Discoverability**: Use `tags` to filter the UI (e.g., `tags=['domain:finance', 'team:sales-eng']`).
2.  **Clarify Ownership**: Define the `owner` field in `default_args` using a team alias or mailing list, not an individual.
3.  **Leverage Markdown Documentation (`doc_md`)**: Include a block string documenting the DAG's purpose, data sources/destinations, and run-books. The UI renders this markdown.
4.  **Use Descriptive Task IDs**: Never use generic names like `python_task`. Task IDs are the primary identifier in alerts. Use a `verb_noun_system` convention (e.g., `extract_redis_sessions`).

## 6. Resource Optimization (CPU, Memory, API Limits)
1.  **Avoid High Memory**: Do not load massive files into memory at once in Python (e.g., use `chunksize` in pandas).
2.  **Reduce High CPU**: Use vectorized operations (NumPy, pandas) instead of slow row-by-row Python `for` loops.
3.  **Avoid I/O Bottlenecks**: Never execute database queries or API calls in a Python loop. Use bulk insert methods provided by Hooks (e.g., `PostgresHook.insert_rows`).
4.  **Limit External API Concurrency**: Use Airflow Pools (`pool='api_rate_limit'`) to prevent tasks from overwhelming external APIs.
5.  **Control DAG Concurrency**: Always set `max_active_tasks` on the DAG object to prevent highly-parallel branches from consuming all worker slots.

## 7. Parameterizing DAGs
1.  **Use Airflow Variables**: Never hardcode environment-specific strings (like GCS bucket names). Use Jinja templating (e.g., `gs://{{ var.value.bucket_name }}`).
2.  **Secure Secrets via Connections**: Never hardcode API keys or passwords. Use Airflow Connections and Hooks (e.g., `HttpHook(http_conn_id='my_api')`).
3.  **Use DAG `params` for Business Logic**: Expose runtime configuration (like "region" or "customer_id") using `params={}` in the DAG definition to allow interactive triggering in the UI.

## 8. Securing DAG Operations
Because DAGs execute Python code directly on worker nodes, insecure file operations or unhandled external API calls can destabilize a Cloud Composer environment.

### A. Eliminate Destructive Shell Commands
Do not use `os.system()` or `subprocess` to execute raw shell commands like `rm -rf`.
*   **Best Practice**: Use native Python libraries like `shutil` and `os.remove`, and explicitly validate the path before execution (e.g. check if path starts with `/tmp/`).

### B. Isolate File I/O
Do not write custom files or logs to arbitrary directories on the worker (e.g., `/opt/airflow/`).
*   **Best Practice**:
    *   For ephemeral transit data that will be deleted within the task, use `/tmp`.
    *   For persistent data, write exclusively to the `/home/airflow/gcs/data` directory (which syncs to GCS).

### C. Enforce API Timeouts
When communicating with external APIs or databases, always define a strict timeout.
*   **Best Practice**: Set both an operator-level `timeout` (network) and an `execution_timeout` (absolute task max time). 

### D. Design for Idempotent Retries
Transient network failures are common. Tasks should be retried, but only if the operation is **idempotent**.
*   **Best Practice**: Ensure retries use exponential backoff, and use logic (like SQL Upserts/Merges) that can be safely repeated rather than raw `INSERT`s that will duplicate data on retry.