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

import logging
from typing import Dict, List, TypeVar

from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.difference import EnvironmentAttributeDiff
from cloudcomposerdiff.lib.strategies.strategy import EnvironmentAttributeDiffer

# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar('T', bound='DiffPyPiPackages')


class DiffPyPiPackages(EnvironmentAttributeDiffer):
    def detect_difference(
        self: T, env1: service_v1.types.Environment, env2: service_v1.types.Environment
    ) -> List[EnvironmentAttributeDiff]:
        config1: Dict = env1.config.software_config.pypi_packages
        config2: Dict = env2.config.software_config.pypi_packages
        category: str = "pypi_packages"
        diffs = []
        if config1 == {} and config2 == {}:
            # both environments do not have any custom pypi packages
            logging.warning("Both environments have no custom pypi packages.")
        elif not config1 == {} and config2 == {}:
            # only environment 1 has config overrides
            while len(config1) > 0:
                k1, v1 = config1.popitem()
                diffs.append(
                    EnvironmentAttributeDiff(
                        category_of_diff=category,
                        diff_anchor=k1,
                        env_1_anchor_value=v1,
                        env_2_anchor_value=None,
                    )
                )
        elif config1 == {} and not config2 == {}:
            # only environment 1 has config overrides
            while len(config2) > 0:
                k2, v2 = config2.popitem()
                diffs.append(
                    EnvironmentAttributeDiff(
                        category_of_diff=category,
                        diff_anchor=k2,
                        env_1_anchor_value=None,
                        env_2_anchor_value=v2,
                    )
                )

        else:
            # both environments have custom pypi packages to compare
            # compare both config parameter & value across both environments
            while len(config1) > 0:
                # remove an item from config1
                k1, v1 = config1.popitem()
                if k1 in config2:
                    # this config parameter exists in both environments
                    v2 = config2.get(k1)
                    diffs.append(
                        EnvironmentAttributeDiff(
                            category_of_diff=category,
                            diff_anchor=k1,
                            env_1_anchor_value=v1,
                            env_2_anchor_value=v2,
                        )
                    )
                    config2.pop(k1)
                else:
                    # this config parameter only exists in environment 1
                    diffs.append(
                        EnvironmentAttributeDiff(
                            category_of_diff=category,
                            diff_anchor=k1,
                            env_1_anchor_value=v1,
                            env_2_anchor_value=None,
                        )
                    )
            # whatever is left in config2 now is unique to environment 2
            while len(config2) > 0:
                k2, v2 = config2.popitem()
                diffs.append(
                    EnvironmentAttributeDiff(
                        category_of_diff=category,
                        diff_anchor=k2,
                        env_1_anchor_value=None,
                        env_2_anchor_value=v2,
                    )
                )
        return diffs
