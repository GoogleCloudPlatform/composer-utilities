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

import tempfile

from composer_migration.lib.comparator import DAGComparator
from composer_migration.lib.strategies.migrate_kubernetes_pod_operator_ast import (
    CheckKubernetesPodOperator,
)

import pytest


def test_check_dag_files_no_dags(caplog: pytest.LogCaptureFixture) -> None:
    temp_dag_dir = tempfile.mkdtemp()
    comparator = DAGComparator(temp_dag_dir)
    assert comparator.problem_operators == []

    comparator.check_dag_files(strategy=CheckKubernetesPodOperator)
    out = caplog.messages
    assert "No dags to check, which means no problem operators were found." in out
    assert comparator.problem_operators == []


def test_check_dag_files_empty_filepath() -> None:
    with pytest.raises(FileNotFoundError):
        comparator = DAGComparator("")
        assert comparator.problem_operators == []

        comparator.check_dag_files(strategy=CheckKubernetesPodOperator)
