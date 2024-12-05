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

import json
from typing import List, TypeVar

from google.cloud.orchestration.airflow import service_v1
from rich.console import Console
from rich.table import Table

from cloudcomposerdiff.lib.difference import EnvironmentAttributeDiff
from cloudcomposerdiff.lib.strategies.strategy import EnvironmentAttributeDiffer

# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="EnvironmentComparator")


class EnvironmentComparator:
    def __init__(
        self: T, env1: service_v1.types.Environment, env2: service_v1.types.Environment
    ) -> None:
        self.differences: List[EnvironmentAttributeDiff] = []
        self.env1: service_v1.types.Environment = env1
        self.env2: service_v1.types.Environment = env2

    def compare_environments(self: T, strategy: EnvironmentAttributeDiffer) -> None:
        diffs: List[EnvironmentAttributeDiff] = strategy.detect_difference(
            self.env1, self.env2
        )
        self.differences.extend(diffs)

    def output_diffs_to_console(self: T) -> None:
        console = Console()
        table = Table()
        table.add_column("category")
        table.add_column("attribute")
        table.add_column("env_1_value")
        table.add_column("env_2_value")
        table.add_column("matching_value")
        for diff in self.differences:
            table.add_row(
                diff.category_of_diff,
                diff.diff_anchor,
                None if diff.values_match else diff.env_1_anchor_value,
                None if diff.values_match else diff.env_2_anchor_value,
                diff.env_1_anchor_value if diff.values_match else None,
            )
        console.print(table)

    def output_diffs_as_json(self: T) -> None:
        with open("cloudcomposerdiff.json", "w") as write_file:
            json_data = {"differences_detected": []}
            for diff in self.differences:
                json_data["differences_detected"].append(
                    {
                        "category": diff.category_of_diff,
                        "attribute": diff.diff_anchor,
                        "env_1_value": (
                            None if diff.values_match else diff.env_1_anchor_value
                        ),
                        "env_2_value": (
                            None if diff.values_match else diff.env_2_anchor_value
                        ),
                        "matching_value": (
                            diff.env_1_anchor_value if diff.values_match else None
                        ),
                    }
                )
            json.dump(json_data, write_file, indent=4)
