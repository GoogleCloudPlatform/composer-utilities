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

from typing import TypeVar

# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="EnvironmentAttributeDiff")


class EnvironmentAttributeDiff:
    def __init__(
        self: T,
        category_of_diff: str,
        diff_anchor: str,
        env_1_anchor_value: str,
        env_2_anchor_value: str,
    ) -> None:
        self.category_of_diff: str = category_of_diff
        self.diff_anchor = diff_anchor
        self.env_1_anchor_value = env_1_anchor_value
        self.env_2_anchor_value = env_2_anchor_value
        self.values_match = self.env_1_anchor_value == self.env_2_anchor_value
