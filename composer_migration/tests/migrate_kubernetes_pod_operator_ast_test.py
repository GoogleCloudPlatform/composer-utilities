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


# import migrate_kubernetes_pod_operator_ast
from composer_migration.lib.strategies.migrate_kubernetes_pod_operator_ast import (
    CheckKubernetesPodOperator,
)


def test_find_problem_kubernetes_pod_operator() -> None:
    output = CheckKubernetesPodOperator.check_for_problem(
        "composer_migration/test_resources/kubernetes_pod_operator_airflow_1.py"
    )
    problem_operators = output["nodes"]
    assert "kubernetes_affinity_ex" in problem_operators
    assert "kubernetes_affinity_ex_2" in problem_operators
    assert "kubernetes_affinity_ex_gke" not in problem_operators


def test_find_problem_kubernetes_pod_operator_no_problem() -> None:
    problem_operators_airflow_1_no_affinity = CheckKubernetesPodOperator.check_for_problem(
        "composer_migration/test_resources/kubernetes_pod_operator_airflow_1_no_affinity.py"
    )[
        "nodes"
    ]
    problem_operators_airflow_1_gke = CheckKubernetesPodOperator.check_for_problem(
        "composer_migration/test_resources/gke_operator_airflow_1.py"
    )[
        "nodes"
    ]  # has affinity but is ok to have it
    problem_operators_hadoop = CheckKubernetesPodOperator.check_for_problem(
        "composer_migration/test_resources/hadoop_tutorial.py"
    )[
        "nodes"
    ]  # has nothing to do with k8s
    problem_operators_airflow_db = CheckKubernetesPodOperator.check_for_problem(
        "composer_migration/test_resources/airflow_db_cleanup.py"
    )[
        "nodes"
    ]  # has nothing to do with k8s but has multiple targets in an assign

    assert len(problem_operators_airflow_1_no_affinity) == 0
    assert len(problem_operators_airflow_1_gke) == 0
    assert len(problem_operators_hadoop) == 0
    assert len(problem_operators_airflow_db) == 0
