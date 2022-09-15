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

from typing import List

from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.difference import EnvironmentAttributeDiff
from cloudcomposerdiff.lib.strategies.strategy import EnvironmentAttributeDiffer


class DiffEnvImage(EnvironmentAttributeDiffer):
    def detect_difference(
        self, env1: service_v1.types.Environment, env2: service_v1.types.Environment
    ) -> List[EnvironmentAttributeDiff]:
        image1: str = env1.config.software_config.image_version
        image2: str = env2.config.software_config.image_version

        diff: EnvironmentAttributeDiff = EnvironmentAttributeDiff(
            category_of_diff="composer_image_version",
            diff_anchor="image_version",
            env_1_anchor_value=image1,
            env_2_anchor_value=image2,
        )
        return [diff]
