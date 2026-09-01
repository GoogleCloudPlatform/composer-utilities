#! /bin/python
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
import os
import re
import sys

DOCKER_REGISTRY_IMAGE_TAG = (
    "us-docker.pkg.dev/cloud-airflow-releaser/"
    "airflow-worker-scheduler-{dashed_airflow_v}/"
    "airflow-worker-scheduler-{dashed_airflow_v}:"
    "{image_tag}"
)
IMAGE_VERSION_PATTERN = r"composer-([1-9]+(?:\.[0-9]+\.[0-9]+)?)-airflow-([1-9]+\.[0-9]+\.[0-9]+(?:-build\.[0-9]+)?)"


# https://github.com/GoogleCloudPlatform/composer-local-dev/blob/2f18605627a2b92de145bfc8a7e44e19ab08a97b/composer_local_dev/utils.py#L185
def get_airflow_composer_versions(image_version: str) -> tuple[str, str]:
    """
    Get airflow and composer versions from image_version.

    Args:
        image_version: Image version in format of 'composer-(2.b.c|3)-airflow-x.y.z[-build.w]'

    Returns:
        airflow_v: Airflow version (in x.y.z[-build.w] format).
        composer_v: Composer version (in (2.b.c|3) format).
    """
    version_match = re.match(IMAGE_VERSION_PATTERN, image_version)
    if not version_match:
        raise ValueError("No image version found")
    composer_v, airflow_v = version_match.group(1), version_match.group(2)
    return airflow_v, composer_v


# https://github.com/GoogleCloudPlatform/composer-local-dev/blob/2f18605627a2b92de145bfc8a7e44e19ab08a97b/composer_local_dev/utils.py#L208
def get_image_version_tag(airflow_v: str, composer_v: str) -> str:
    """
    Returns Composer image version tag created from
    Airflow and Composer versions.
    """
    # In Composer 2, image tags have Airflow version dashified
    if composer_v != "3":
        airflow_v = airflow_v.replace(".", "-")
    return f"composer-{composer_v}-airflow-{airflow_v}"


# https://github.com/GoogleCloudPlatform/composer-local-dev/blob/2f18605627a2b92de145bfc8a7e44e19ab08a97b/composer_local_dev/environment.py#L284
def get_docker_image_tag_from_image_version(image_version: str) -> str:
    """
    Parse image version to Airflow and Composer versions and return image tag
    with those versions if it exists.

    Args:
        image_version: Image version in format of 'composer-x.y.z-airflow-a.b.c'

    Returns:
        Composer image tag in Artifact Registry
    """
    airflow_v, composer_v = get_airflow_composer_versions(image_version)
    dashed_airflow_v = airflow_v.replace(".", "-").split("-build")[0]
    image_tag = get_image_version_tag(airflow_v, composer_v)
    return DOCKER_REGISTRY_IMAGE_TAG.format(
        dashed_airflow_v=dashed_airflow_v,
        composer_v=composer_v,
        image_tag=image_tag,
    )


if __name__ == "__main__":
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Check if running in Google Cloud Build environment (/workspace)
        # or locally (the repository root, two levels above the script directory)
        workspace_path = (
            "/workspace"
            if os.path.exists("/workspace")
            else os.path.dirname(script_dir)
        )
        with open(
            os.path.join(workspace_path, "cicd/composer_version.txt"),
        ) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    image_version = line.strip()
                    break
        tag = get_docker_image_tag_from_image_version(image_version)
        print(tag)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
