import tempfile

from composer_migration.lib.comparator import DAGComparator
from composer_migration.lib.strategies.migrate_kubernetes_pod_operator_ast import (
    CheckKubernetesPodOperator,
)

import pytest


def test_check_dag_files_no_dags(caplog):
    temp_dag_dir = tempfile.mkdtemp()
    comparator = DAGComparator(temp_dag_dir)
    assert comparator.problem_operators == []

    comparator.check_dag_files(strategy=CheckKubernetesPodOperator)
    out = caplog.messages
    assert "No dags to check, which means no problem operators were found." in out
    assert comparator.problem_operators == []


def test_check_dag_files_empty_filepath():
    with pytest.raises(FileNotFoundError):
        comparator = DAGComparator("")
        assert comparator.problem_operators == []

        comparator.check_dag_files(strategy=CheckKubernetesPodOperator)
