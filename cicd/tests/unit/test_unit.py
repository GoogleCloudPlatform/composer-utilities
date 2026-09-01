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
import sys
from pathlib import Path

import pytest
from airflow.models import DagBag

PARSING_DURATION_THRESHOLD = 2.5


@pytest.fixture(scope="session")
def dagbag():
    dags_path = str((Path(__file__).parent.parent.parent / "dags").resolve())
    sys.path.insert(0, dags_path)
    import airflow  # Used only to check version for backward compatibility

    kwargs = {"include_examples": False} if airflow.__version__.startswith("2.") else {}
    yield DagBag(dag_folder=dags_path, **kwargs)


def test_dagbag_not_empty(dagbag):
    assert dagbag.size() > 0, "Dagbag should not be empty."


def test_dagbag_no_import_errors(dagbag):
    assert dagbag.import_errors == {}, "No import errors should be found."


""" Uncomment below if you want to fail on warnings
def test_dagbag_no_import_warnings(dagbag):
    assert len(dagbag.captured_warnings) == 0, "No warnings should be found."
"""


def test_filename_matches_dag_id(dagbag):
    """Tests that filename matches dag_id"""
    for dag in dagbag.dags.values():
        assert dag.dag_id == Path(dag.relative_fileloc).stem, (
            "Filename does not match DAG ID."
        )


def test_all_dags_have_start_date(dagbag):
    """Tests that all DAGs have a start_date."""
    for dag_id, dag in dagbag.dags.items():
        assert dag.start_date is not None, f"DAG {dag_id} does not have a start_date."


def test_sleepy_dynamic_task_mapping_structure(dagbag):
    dag = dagbag.get_dag("sleepy_dynamic_task_mapping")
    assert dag is not None, "DAG sleepy_dynamic_task_mapping not found."
    # get_sleepy_minutes and the expanded task group
    # Note: in TaskFlow, the number of tasks might be different depending on how they are counted
    assert len(dag.tasks) >= 2
    assert "sleep_for.sleepy_pod" in [task.task_id for task in dag.tasks]


def test_sleepy_task_group_structure(dagbag):
    dag = dagbag.get_dag("sleepy_task_group")
    assert dag is not None
    assert len(dag.tasks) >= 3


def test_dagbag_parse_times(dagbag):
    """Test that each DAG file takes less than the threshold to parse."""
    failing_dags = []
    for stat in dagbag.dagbag_stats:
        duration = (
            stat.duration.total_seconds()
            if hasattr(stat.duration, "total_seconds")
            else stat.duration
        )
        file_path = stat.file if hasattr(stat, "file") else stat.fileloc
        if duration >= PARSING_DURATION_THRESHOLD:
            failing_dags.append(
                f"DAG parsing for {file_path} took too long: {duration} seconds (threshold: {PARSING_DURATION_THRESHOLD}s)"
            )

    assert not failing_dags, "\n".join(failing_dags)


def test_dag_tags_example(dagbag):
    """Example of testing that a specific DAG has the expected tags."""
    dag = dagbag.get_dag("sleepy_task_group")
    assert dag is not None, "DAG sleepy_task_group not found."
    assert "taskgroup" in dag.tags
    assert "test" in dag.tags
    assert "dynamic_task_mapping" in dag.tags


def test_dag_default_args_example(dagbag):
    """Example of testing that a DAG has specific default_args configured."""
    dag = dagbag.get_dag("sleepy_dynamic_task_mapping")
    assert dag is not None, "DAG sleepy_dynamic_task_mapping not found."
    assert "retries" in dag.default_args
    assert dag.default_args["retries"] >= 3


def test_task_properties_example(dagbag):
    """Example of testing specific properties of a task."""
    dag = dagbag.get_dag("sleepy_dynamic_task_mapping")
    assert dag is not None, "DAG sleepy_dynamic_task_mapping not found."

    # Retrieve the specific task
    task = dag.get_task("sleep_for.sleepy_pod")

    # Check properties
    assert task.image == "gcr.io/google.com/cloudsdktool/google-cloud-cli:latest"
    assert task.namespace == "composer-user-workloads"


def test_kubernetes_pod_operator_namespace(dagbag):
    """Tests that any KubernetesPodOperator uses the 'composer-user-workloads' namespace."""
    from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

    invalid_tasks = []
    for dag_id, dag in dagbag.dags.items():
        for task in dag.tasks:
            if (
                isinstance(task, KubernetesPodOperator)
                and getattr(task, "namespace", None) != "composer-user-workloads"
            ):
                invalid_tasks.append(
                    f"DAG: {dag_id}, Task: {task.task_id}, Namespace: {getattr(task, 'namespace', None)}"
                )

    assert not invalid_tasks, (
        "The following KubernetesPodOperator tasks do not use the 'composer-user-workloads' namespace:\n"
        + "\n".join(invalid_tasks)
    )
