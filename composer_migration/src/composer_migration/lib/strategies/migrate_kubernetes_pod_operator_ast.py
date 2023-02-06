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

from typing import TypeVar
import ast
import logging

from composer_migration.lib.strategies.strategy import DAGChecker

# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="CheckKubernetesPodOperator")
A = TypeVar("A", bound="ast.AST")


# just visit needed nodes per
# https://greentreesnakes.readthedocs.io/en/latest/manipulating.html#working-on-the-tree
# subclass visitor for what we need
# also derived from IBIS https://github.com/ibis-project/ibis-bigquery/blob/main/ibis_bigquery/udf/core.py
# Style note: visit methods sometimes have snake case with capital letters which is
# not very Pythonic - this is because they are overriding visit methods for
# particular nodes - see https://greentreesnakes.readthedocs.io/en/latest/manipulating.html#modifying-the-tree
# for more info


# KubernetesPodOperator objects will only ever be under an "Assign"
# This traverses the tree and adds all "Assign" nodes to a list
class AssignFinder(ast.NodeVisitor):
    def __init__(self: ast.NodeVisitor) -> None:
        self.possible_kpo_nodes = []

    def visit_Assign(self: ast.NodeVisitor, node: ast.Assign) -> None:
        self.possible_kpo_nodes.append(node)
        self.generic_visit(node)


# This should only be used on subtrees of nodes of type "ast.Assign"
class KPOFinder(ast.NodeVisitor):
    def __init__(self: ast.NodeVisitor) -> None:
        self.has_problem = False
        self.kpo_attribute = False

    # Binding to ast.AST means we can accept any node type
    def visit_value(self: ast.NodeVisitor, node: A) -> None:
        print(type(node))
        self.generic_visit(node)

    def visit_Call(self: ast.NodeVisitor, node: ast.Call) -> None:
        self.generic_visit(node)

    # Airflow 2 nodes will determine this way
    def visit_Name(self: ast.NodeVisitor, node: ast.Name) -> None:
        if node.id == "KubernetesPodOperator":
            self.kpo_attribute = True
            self.generic_visit(node)

    # Airflow 1 nodes will determine this way
    def visit_Attribute(self: ast.NodeVisitor, node: ast.Attribute) -> None:
        if node.attr == "KubernetesPodOperator":
            self.kpo_attribute = True
            self.generic_visit(node)

    def visit_keyword(self: ast.NodeVisitor, node: ast.keyword) -> None:
        if node.arg == "affinity":
            self.generic_visit(node)

    def visit_Dict(self: ast.NodeVisitor, node: ast.Dict) -> None:
        if len(node.keys) != 0 and self.kpo_attribute:  # This means pod affinity is set
            self.has_problem = True
            self.kpo_attribute = False


class CheckKubernetesPodOperator(DAGChecker):
    def table_title_text() -> dict:
        return {
            "title": "KubernetesPodOperator Affinity Check",
            "text": "Node pools are not supported with the KubernetesPodOperator in Composer 2. Refactor the following DAGs to use the GKE Operators to launch your pod in a new cluster, or remove the 'affinity' field from your operator. See https://cloud.google.com/composer/docs/composer-2/use-gke-operator for more information on using the GKE operators in Cloud Composer.",
        }

    def check_for_problem(file: str) -> dict:
        # read dag in as a string
        with open(file, "r") as f:
            dag = f.read()
        # parse string into abstract syntax tree
        tree = ast.parse(dag)

        # create a traverser that looks for "ast.Assign" nodes
        a = AssignFinder()

        # visit the ast and add all assign nodes to a list
        # we need the "assign" nodes to be able to name the problem variables
        a.visit(tree)

        # go through possible problem notes and check for "affinity" parameter
        problem_nodes = []
        for assign in a.possible_kpo_nodes:
            k = KPOFinder()
            k.visit(assign)
            # assumes only one target ever
            # if target node doesn't have an ID, log a debug statement
            try:
                i = assign.targets[0].id
                if k.has_problem:
                    problem_nodes.append(i)
            except AttributeError:
                logging.debug("Node is not of type with a target")

        output = {"nodes": problem_nodes}
        return output


if __name__ == "__main__":
    print(
        CheckKubernetesPodOperator.check_for_problem(
            "./composer_migration/test_resources/kubernetes_pod_operator_airflow_1.py"
        )
    )
