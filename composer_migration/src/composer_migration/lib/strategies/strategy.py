# Copyright 2023 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from abc import ABC, abstractmethod
from typing import TypeVar


# Anthony's examle
# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="DAGChecker")


# Takes in the name of a DAG file in our temporary directory
# The concrete implementation the abstract method will check
# for operators in the DAG file with that concrete problem
# Outputs a dict with the name of any operators with the problem
# and info to make it more human readable
class DAGChecker(ABC):
    @abstractmethod
    def check_for_problem(self: T, dag: str) -> dict:
        pass
