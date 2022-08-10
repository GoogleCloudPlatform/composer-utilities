"""
 Copyright 2022 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

from unittest.mock import MagicMock

from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.service import GCPComposerService


def test_gcp_composer_service_construction():
    service: GCPComposerService = GCPComposerService("projectid", "location", "name")
    assert service.name == f"projects/projectid/locations/location/environments/name"


def test_gcp_composer_service_fetch_env():
    service: GCPComposerService = GCPComposerService("projectid", "location", "name")
    service.fetch_env = MagicMock(
        return_value=service_v1.types.Environment(
            {"name": "projects/projectid/locations/location/environments/name"}
        )
    )
    env: service_v1.types.Environment = service.fetch_env()
    assert env.name == f"projects/projectid/locations/location/environments/name"
