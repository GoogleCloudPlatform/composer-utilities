#!/usr/bin/env bash
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

# Enable exit-on-error mode
set -eo pipefail

# Determine base directory whether mounted at repo root or inside cicd directory
if [ -d "/workspace/cicd" ]; then
    BASE_DIR="/workspace/cicd"
elif [ -d "/workspace/dags" ]; then
    BASE_DIR="/workspace"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    BASE_DIR="$SCRIPT_DIR"
fi

DAGS_DIR="$BASE_DIR/dags"
TESTS_DIR="$BASE_DIR/tests"
REQUIREMENTS_FILE="$DAGS_DIR/requirements.txt"

# Set up the Python user base directory where local packages will be installed
export PYTHONUSERBASE=/home/airflow/.local

# Add the local user bin directory to the PATH so installed executables can be found
export PATH=$PYTHONUSERBASE/bin:$PATH

# Set up the Airflow home directory
export AIRFLOW_HOME=/home/airflow/airflow
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export PYTHONDONTWRITEBYTECODE=1

# Capture currently installed packages as constraints for the upcoming install
pip list --format=freeze > /tmp/constraints.txt

# Remove the apache-airflow-providers-google constraint because requirements.txt
# may specify a higher version when testing the DAGs (e.g. "==19.1.0").
sed -i '/apache-airflow-providers-google/d' /tmp/constraints.txt

# Install requested testing requirements using the captured constraints to avoid dependency conflicts
if [ -f "$REQUIREMENTS_FILE" ]; then
    pip install --no-cache-dir --user pytest \
        --requirement "$REQUIREMENTS_FILE" \
        --constraint /tmp/constraints.txt
else
    pip install --no-cache-dir --user pytest \
        --constraint /tmp/constraints.txt
fi

# In Airflow 3, some internal components (like the Simple Auth Manager) may attempt to initialize 
# or "build" UI assets on the fly if they aren't present. Since Airflow is installed in a system-level
# directory, ensure the directory exists and is owned by the airflow user.
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/opt/python3.11/lib/python3.11/site-packages")
if [ -d "$SITE_PACKAGES/airflow" ]; then
    sudo mkdir -p "$SITE_PACKAGES/airflow/api_fastapi/auth/managers/simple/ui/dist" || true
    sudo chown -R airflow: "$SITE_PACKAGES/airflow/api_fastapi/auth/managers/simple/ui/dist" || true
fi

# Set basic auth if testing Airflow 2 
export AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
export AIRFLOW__CORE__DAGS_FOLDER="$DAGS_DIR"

# Start Airflow standalone in the background
airflow standalone > /dev/null &

# Wait to ensure the Airflow database is fully initialized
echo "Waiting for Airflow database to be ready..."
airflow db check
echo "Database is up!"

# Wait for the Airflow Webserver to be ready to accept REST API connections
echo "Waiting for Airflow Webserver to be ready..."
RETRIES=60
until curl -sf http://localhost:8080 > /dev/null || [ $RETRIES -eq 0 ]; do
    sleep 2
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo "Error: Airflow Webserver failed to start within 120 seconds."
    exit 1
fi
echo "Webserver is up!"

# List the DAGs to verify they are parsed without errors
airflow dags list

# Run pytest to execute the tests in the workspace
python3 -m pytest -o cache_dir=/tmp/.pytest_cache -vv -s "$TESTS_DIR"
