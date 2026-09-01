# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import os
import time

import airflow
import requests

""" Integration testing using Airflow REST API

These tests assume Airflow is running in standalone mode (e.g., via the "airflow standalone" command).
They trigger DAG runs via the Airflow REST API and poll for their completion to verify logic and dependencies.
"""

# Detect Airflow version
AIRFLOW_VERSION = airflow.__version__
print(f"Detected Airflow version: {AIRFLOW_VERSION}")

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/home/airflow/airflow")
admin_password = "admin"  # default fallback

# Default headers and auth
HEADERS = {}
AUTH = None

if AIRFLOW_VERSION.startswith("3"):
    AF_URL = "http://localhost:8080/api/v2"
    PASSWORD_FILE = os.path.join(
        AIRFLOW_HOME, "simple_auth_manager_passwords.json.generated"
    )
    try:
        if os.path.exists(PASSWORD_FILE):
            with open(PASSWORD_FILE) as f:
                passwords = json.load(f)
                admin_password = passwords.get("admin", admin_password)
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Could not read password file {PASSWORD_FILE}: {e}")

    # Get JWT Token for Airflow 3
    token_url = "http://localhost:8080/auth/token"
    try:
        token_res = requests.post(
            token_url, json={"username": "admin", "password": admin_password}
        )
        try:
            res_json = token_res.json()
        except Exception:  # noqa: BLE001
            res_json = {}

        if token_res.status_code in [200, 201] or "access_token" in res_json:
            token = res_json.get("access_token")
            HEADERS = {"Authorization": f"Bearer {token}"}
            print(
                f"Successfully obtained JWT token for Airflow 3 (Status: {token_res.status_code})"
            )
        else:
            print(
                f"Warning: Failed to get token (Status: {token_res.status_code}): {token_res.text}. Falling back to no auth headers."
            )
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Error getting token: {e}")

else:
    # Airflow 2 or others
    AF_URL = "http://localhost:8080/api/v1"
    PASSWORD_FILE = os.path.join(AIRFLOW_HOME, "standalone_admin_password.txt")
    try:
        if os.path.exists(PASSWORD_FILE):
            with open(PASSWORD_FILE) as f:
                admin_password = f.read().strip()
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Could not read password file {PASSWORD_FILE}: {e}")

    AUTH = ("admin", admin_password)


def unpause_all_dags():
    """Unpauses all DAGs using wildcard."""
    url = f"{AF_URL}/dags?dag_id_pattern=%"
    kwargs = {}
    if HEADERS:
        kwargs["headers"] = HEADERS
    if AUTH:
        kwargs["auth"] = AUTH

    try:
        print("Attempting to unpause all DAGs with pattern '%'...")
        res = requests.patch(url, json={"is_paused": False}, **kwargs)
        if res.status_code not in (200, 201):
            print(
                f"Warning: Failed to unpause all DAGs with wildcard (Status: {res.status_code}): {res.text}"
            )
        else:
            print("Successfully unpaused all DAGs.")
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Error unpausing all DAGs: {e}")


# Call unpause all DAGs
unpause_all_dags()


def trigger_and_wait_for_dag(dag_id: str, conf: dict | None = None):
    # Wait for DAG to be available in REST API
    status_url = f"{AF_URL}/dags/{dag_id}"
    max_retries = 60  # 120 seconds total with 2s sleep
    status_kwargs = {}
    if HEADERS:
        status_kwargs["headers"] = HEADERS
    if AUTH:
        status_kwargs["auth"] = AUTH

    print(f"Waiting for DAG {dag_id} to be available in REST API...")
    while max_retries > 0:
        try:
            res = requests.get(status_url, **status_kwargs)
            if res.status_code == 200:
                print(f"DAG {dag_id} is available.")
                break
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Error checking DAG availability: {e}")

        time.sleep(2)
        max_retries -= 1

    if max_retries <= 0:
        print(
            f"Warning: DAG {dag_id} not found in REST API after timeout. Attempting to trigger anyway."
        )

    # 1. Trigger the DAG
    trigger_url = f"{AF_URL}/dags/{dag_id}/dagRuns"

    trigger_kwargs = {"json": {}}
    if conf:
        trigger_kwargs["json"]["conf"] = conf

    if AIRFLOW_VERSION.startswith("3"):
        from datetime import datetime, timezone

        trigger_kwargs["json"]["logical_date"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    if HEADERS:
        trigger_kwargs["headers"] = HEADERS
    if AUTH:
        trigger_kwargs["auth"] = AUTH

    response = requests.post(trigger_url, **trigger_kwargs)

    if response.status_code not in (200, 201):
        # Check for import errors before failing
        import_errors_url = f"{AF_URL}/importErrors"
        try:
            status_kwargs = {}
            if HEADERS:
                status_kwargs["headers"] = HEADERS
            if AUTH:
                status_kwargs["auth"] = AUTH
            errors_res = requests.get(import_errors_url, **status_kwargs)

            if errors_res.status_code == 200:
                print(f"\nImport Errors found in system: {errors_res.text}")
            else:
                print(
                    f"\nFailed to fetch import errors (Status: {errors_res.status_code})"
                )
        except Exception as e:  # noqa: BLE001
            print(f"\nError fetching import errors: {e}")

    assert response.status_code in (200, 201), (
        f"Failed to trigger {dag_id}: {response.text}"
    )

    dag_run_id = response.json()["dag_run_id"]

    # 2. Poll for completion
    status_url = f"{AF_URL}/dags/{dag_id}/dagRuns/{dag_run_id}"
    state = "queued"
    max_retries = 450  # Poll up to 15 minutes

    while state in ["queued", "running"] and max_retries > 0:
        time.sleep(2)

        status_kwargs = {}
        if HEADERS:
            status_kwargs["headers"] = HEADERS
        if AUTH:
            status_kwargs["auth"] = AUTH

        status_res = requests.get(status_url, **status_kwargs).json()
        state = status_res.get("state", "unknown")
        max_retries -= 1

    # 3. Assert outcome
    assert state == "success", f"DAG {dag_id} failed with state: {state}"


def test_sleepy_task_group_execution():
    """Triggers the sleepy_task_group DAG and verifies it completes successfully."""
    trigger_and_wait_for_dag(
        "sleepy_task_group",
        conf={"seconds_to_sleep": 1, "number_of_sleepy_tasks": 1},
    )
