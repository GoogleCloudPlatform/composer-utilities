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

from typing import List, Tuple, TypeVar
import logging
import os

from composer_migration.lib.strategies.strategy import DAGChecker

from rich.console import Console
from rich.table import Table
from rich.console import Group
from rich.text import Text
from rich.panel import Panel

# https://peps.python.org/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="DAGsComparator")


class DAGsComparator:
    def __init__(self: T, dags_directory: str) -> None:
        self.problem_operators: List[Tuple(str, str)] = []
        self.dags_directory = dags_directory
        self.dags_list = os.listdir(dags_directory)

    def check_dag_files(self: T, strategy: DAGChecker) -> None:
        console = Console()
        problems: List[str] = []
        output = None
        if len(self.dags_list) == 0:
            logging.error(
                "No dags to check, which means no problem operators were found."
            )
            return

        for dag_file in self.dags_list:
            # make a tuple with filename and operator for output
            output = strategy.check_for_problem(f"{self.dags_directory}/{dag_file}")
            this_dag_problem_operators = output["nodes"]
            if len(this_dag_problem_operators) > 0:
                for operator in this_dag_problem_operators:
                    problems.append((dag_file, operator))
        self.problem_operators += problems
        logging.debug(self.problem_operators)


    
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("DAG")
        table.add_column("Operator")
        show_table = False  # if there are no problems at all, don't show the table
        if len(self.problem_operators) > 0:
            show_table = True
        for operator in self.problem_operators:
            table.add_row(operator[0], operator[1])
        if show_table:
            table_text = Text(output["text"])
            panel_group = Group(table_text, table)
            console.print(Panel(panel_group, title=output["title"]))
        else:
            table_text = Text("No problem operators found")
            console.print(Panel(table_text, title=output["title"]))
        # reset problem operators before doing next check
        self.problem_operators = []
