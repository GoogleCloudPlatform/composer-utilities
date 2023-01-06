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

from typing import List
import ast
import logging

# TODO: adjust this import as needed
from composer_migration.lib.strategies.strategy import DAGChecker


# just visit needed nodes per
# https://greentreesnakes.readthedocs.io/en/latest/manipulating.html#working-on-the-tree
# subclass visitor for what we need
# also derived from IBIS https://github.com/ibis-project/ibis-bigquery/blob/main/ibis_bigquery/udf/core.py

# KubernetesPodOperator objects will only ever be under an "Assign"
# This traverses the tree and adds all "Assign" nodes to a list
class AssignFinder(ast.NodeVisitor):
    def __init__(self):
        self.possible_kpo_nodes = []

    def visit_Assign(self, node):
        self.possible_kpo_nodes.append(node)
        self.generic_visit(node)


# This should only be used on nodes of type "ast.Assign"
class KPOFinder(ast.NodeVisitor):
    def __init__(self):
        self.has_problem = False
        self.kpo_attribute = False

    def visit_value(self, node):
        self.generic_visit(node)

    def visit_Call(self, node):
        self.generic_visit(node)

    # Airflow 2 nodes will determine this way
    def visit_Name(self, node):
        if node.id == "KubernetesPodOperator":
            self.kpo_attribute = True
            self.generic_visit(node)

    # Airflow 1 nodes will determine this way
    def visit_Attribute(self, node):
        if node.attr == "KubernetesPodOperator":
            self.kpo_attribute = True
            self.generic_visit(node)

    def visit_keyword(self, node):
        if node.arg == "affinity":
            self.generic_visit(node)

    def visit_Dict(self, node):
        if len(node.keys) != 0 and self.kpo_attribute:  # This means pod affinity is set
            self.has_problem = True
            self.kpo_attribute = False


class CheckKubernetesPodOperator(DAGChecker):
    def check_for_problem(file: str) -> List[str]:
        TABLE_TITLE = "KubernetesPodOperator Affinity Check"
        TABLE_TEXT = "Node pools are not supported with the KubernetesPodOperator in Composer 2. Refactor the following DAGs to use the GKE Operators to launch your pod in a new cluster, or remove the 'affinity' field from your operator. See https://cloud.google.com/composer/docs/composer-2/use-gke-operator for more information on using the GKE operators in Cloud Composer."
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

        output = {"nodes": problem_nodes, "title": TABLE_TITLE, "text": TABLE_TEXT}
        return output


if __name__ == "__main__":
    print(
        CheckKubernetesPodOperator.check_for_problem(
            "test_resources/kubernetes_pod_operator_airflow_1.py"
        )
    )
