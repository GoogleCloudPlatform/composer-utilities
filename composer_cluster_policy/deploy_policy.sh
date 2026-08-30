#!/usr/bin/env bash
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

set -euo pipefail

# ==============================================================================
# Cloud Composer Cluster Policy Turn-Key Deployment Script
#
# Automates the official enterprise workflow for deploying Airflow Cluster
# Policies to Cloud Composer 2 and Composer 3 via Google Artifact Registry.
# ==============================================================================

ENV_NAME="${1:-composer-3-airflow-3}"
LOCATION="${2:-us-central1}"
AR_REPO="${3:-composer-packages}"
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================================"
echo " Cloud Composer Cluster Policy Deployment Engine"
echo " Environment: ${ENV_NAME} (${LOCATION})"
echo " Artifact Registry Repository: ${AR_REPO}"
echo "======================================================================"

# 1. Verify Prerequisites
command -v gcloud >/dev/null 2>&1 || { echo "ERROR: gcloud CLI is required."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required."; exit 1; }

PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"
if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: No active GCP project configured in gcloud."
  exit 1
fi
echo "[+] Active GCP Project: ${PROJECT_ID}"

# 2. Ensure Twine and Keyring are installed
if ! python3 -c "import twine" >/dev/null 2>&1; then
  echo "[+] Installing twine and google-artifactregistry keyring for upload..."
  pip3 install --quiet twine keyrings.google-artifactregistry-auth
fi

# 3. Ensure Artifact Registry Repository Exists
echo "[+] Verifying Artifact Registry Python repository [${AR_REPO}]..."
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${LOCATION}" >/dev/null 2>&1; then
  echo "[+] Creating Artifact Registry Python repository [${AR_REPO}] in ${LOCATION}..."
  gcloud artifacts repositories create "${AR_REPO}" \
      --repository-format=python \
      --location="${LOCATION}" \
      --description="Private repository for Cloud Composer cluster policies"
fi

# 4. Resolve Composer Service Accounts and Grant Permissions
echo "[+] Resolving Composer environment and Cloud Build service accounts..."
COMPOSER_SA="$(gcloud composer environments describe "${ENV_NAME}" \
    --location="${LOCATION}" \
    --format="value(config.nodeConfig.serviceAccount)")"
PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
CLOUDBUILD_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"

echo "[+] Granting Artifact Registry reader access to: ${COMPOSER_SA}"
gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
    --location="${LOCATION}" \
    --member="serviceAccount:${COMPOSER_SA}" \
    --role="roles/artifactregistry.reader" --quiet >/dev/null 2>&1 || true

echo "[+] Granting Artifact Registry reader access to: ${CLOUDBUILD_SA}"
gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
    --location="${LOCATION}" \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/artifactregistry.reader" --quiet >/dev/null 2>&1 || true

# 5. Build Distribution Wheel
echo "[+] Building cluster policy distribution wheel..."
cd "${PACKAGE_DIR}"
rm -rf dist/ build/ *.egg-info
pip3 wheel --no-deps -w dist/ .

WHEEL_FILE="$(ls dist/*.whl | head -n 1)"
VERSION="$(basename "${WHEEL_FILE}" | sed -E 's/.*-([0-9]+\.[0-9]+\.[0-9]+)-.*/\1/')"
echo "[+] Built wheel: ${WHEEL_FILE} (Version: ${VERSION})"

# 6. Upload Wheel to Artifact Registry
echo "[+] Uploading ${WHEEL_FILE} to Artifact Registry..."
python3 -m twine upload \
    --username oauth2accesstoken \
    --password "$(gcloud auth print-access-token)" \
    --repository-url "https://${LOCATION}-python.pkg.dev/${PROJECT_ID}/${AR_REPO}/" \
    "${WHEEL_FILE}" --skip-existing

# 7. Configure Environment pip.conf
BUCKET="$(gcloud composer environments describe "${ENV_NAME}" \
    --location="${LOCATION}" \
    --format="value(config.storageConfig.bucket)")"

echo "[+] Generating and uploading pip.conf to gs://${BUCKET}/config/pip/pip.conf..."
cat << EOF > "${PACKAGE_DIR}/pip.conf"
[global]
extra-index-url = https://${LOCATION}-python.pkg.dev/${PROJECT_ID}/${AR_REPO}/simple/
EOF

gcloud storage cp "${PACKAGE_DIR}/pip.conf" "gs://${BUCKET}/config/pip/pip.conf"
rm -f "${PACKAGE_DIR}/pip.conf"

# 8. Trigger Composer Environment Update
echo "[+] Triggering Composer environment update with composer-cluster-policy==${VERSION}..."
echo "composer-cluster-policy==${VERSION}" > "${PACKAGE_DIR}/requirements.txt"

gcloud composer environments update "${ENV_NAME}" \
    --location="${LOCATION}" \
    --update-pypi-packages-from-file="${PACKAGE_DIR}/requirements.txt" \
    --async

echo "======================================================================"
echo " [SUCCESS] Deployment triggered successfully!"
echo " Composer is now installing composer-cluster-policy==${VERSION}."
echo " Check operation status with:"
echo "   gcloud composer environments describe ${ENV_NAME} --location=${LOCATION}"
echo "======================================================================"
