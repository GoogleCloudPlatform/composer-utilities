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

from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.difference import EnvironmentAttributeDiff
from cloudcomposerdiff.lib.service import GCPComposerService
from cloudcomposerdiff.lib.strategies.diffenvimage import DiffEnvImage


def test_diff_env_image_strategy():
    env1: service_v1.types.Environment = service_v1.types.Environment(
        {
            "config": service_v1.types.EnvironmentConfig(
                {
                    "software_config": service_v1.types.SoftwareConfig(
                        {"image_version": "123"}
                    )
                }
            )
        }
    )
    env2: service_v1.types.Environment = service_v1.types.Environment(
        {
            "config": service_v1.types.EnvironmentConfig(
                {
                    "software_config": service_v1.types.SoftwareConfig(
                        {"image_version": "456"}
                    )
                }
            )
        }
    )
    detector: DiffEnvImage = DiffEnvImage()
    diff: EnvironmentAttributeDiff = detector.detect_difference(env1, env2)
    assert diff[0].category_of_diff == "composer_image_version"
