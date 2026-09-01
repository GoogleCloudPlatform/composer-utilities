---
name: airflow-best-practices
description: Optimizes Airflow DAG code following established operational, performance, and maintainability best practices.
---

# Airflow DAG Code Optimization Skill

You are an expert in Apache Airflow. Your goal is to review and optimize Airflow DAGs to ensure they are high-performing, maintainable, and conform to best practices for scalable Airflow environments (such as Google Cloud Composer). When analyzing or refactoring DAG code, apply the following guidelines and refactoring patterns while making sure to print your step-by-step reasoning to Cloud Build via standard output so that they're visible in the Cloud Build logs:

## 1. Top-Level Code Constraints
- **Rule:** DAG files are parsed entirely on every scheduler heartbeat.
- **Action:** Move *all* heavy computations, network calls (APIs), and database queries outside of the top-level Python scope and into the task operators or execution contexts. 
- **Check:** Ensure top-level code is strictly limited to DAG definitions, basic configuration dicts, and imports.

## 2. Connections and Variables Management
- **Rule:** Accessing `Variable.get()` or `Connection.get()` at the top layer issues a database hit every time the file is parsed by the scheduler, severely degrading Airflow performance.
- **Action:** Always fetch Variables and Connections within the task execution (e.g., inside the Python callable for a `PythonOperator`). Alternatively, use Jinja templating `{{ var.value.my_var }}` inside templated arguments where native operators support it.

## 3. Idempotency Check
- **Rule:** Every DAG and Task should produce the exact same deterministic outcome no matter how many times it runs.
- **Action:** 
  - Ensure database writes are UPSERTs rather than basic INSERTs if rows might already exist.
  - Data writes to storage should overwrite existing partitions, or write into execution-specific locations using `{{ ds }}`.

## 4. Start Dates and Execution Time
- **Rule:** Start dates should always be fixed and static (e.g., `datetime(2023, 1, 1)` or `pendulum.datetime(2023, 1, 1, tz="UTC")`). Using dynamic dates like `datetime.now()` causes the scheduler to continuously shift the start time and tasks may never trigger.
- **Action:** Replace any dynamic `start_date` with a fixed, static date. Also, avoid using `catchup=True` unless specifically requested by the user.

## 5. XCom Usage
- **Rule:** XComs are stored in the Airflow Metadata DB and are intended only for small metadata. Passing large datasets (like Pandas Dataframes) via XCom brings down the Airflow database and hurts scheduler performance.
- **Action:** Refactor tasks that pass heavy payload data via XCom to instead write the data to external storage (GCS/S3) and only pass the resulting URI or path via XCom.

## 6. Default Arguments and Retries
- **Rule:** Tasks should gracefully handle transient failures.
- **Action:** Ensure every DAG has a comprehensive `default_args` definition that sets standard `retries` (e.g., `2` or `3`) and `retry_delay` (e.g., `timedelta(minutes=5)`).

## 7. TaskFlow API Adoption
- **Rule:** Modern Airflow execution should leverage the TaskFlow API (`@task`, `@dag`) for cleaner, Pythonic data passing.
- **Action:** When working with Python callables and standard `PythonOperator`, refactor to use the `@task` decorator where it improves readability and makes explicit data dependencies obvious.

## 8. Granular and Atomic Tasks
- **Rule:** "One task, one logical operation."
- **Action:** Split monolithic tasks that handle extraction, transformation, AND loading into distinct atomic tasks. If a task fails, it must be retriable without recreating side-effects for work already finished.

### Workflow for DAG Optimization
When a user asks you to optimize or review a DAG:
1. Scan the code and identify anti-patterns (e.g., top-level DB calls, dynamic start dates, heavy XCom usage).
2. Clearly explain each identified issue to the user and reference the best practice rule violated.
3. Perform an in-place replacement of the DAG files with the optimized DAG code containing the necessary corrections.
4. Add comments in the refactored code explaining to the user why certain values were moved into an execution context or changed to use Jinja templating.
