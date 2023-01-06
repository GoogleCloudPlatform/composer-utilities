from typing import List
import logging
import os

from composer_migration.lib.strategies.strategy import DAGChecker

from rich.console import Console
from rich.table import Table
from rich.console import Group
from rich.text import Text
from rich.panel import Panel


class DAGComparator:
    def __init__(self, dags_directory: str) -> None:
        self.problem_operators: List[str] = []
        self.dags_directory = dags_directory

    def check_dag_files(self, strategy: DAGChecker) -> None:
        dags_dir = os.listdir(self.dags_directory)
        console = Console()
        problems: List[str] = []
        output = None
        if len(dags_dir) == 0:
            logging.error(
                "No dags to check, which means no problem operators were found."
            )

        else:
            for dag_file in dags_dir:
                # make a tuple with filename and operator for output
                output = strategy.check_for_problem(f"{self.dags_directory}/{dag_file}")
                problem_operators = output["nodes"]
                if len(problem_operators) > 0:
                    for operator in problem_operators:
                        problems.append((dag_file, operator))
            self.problem_operators += problems

            # make the output pretty
            if output:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("DAG")
                table.add_column("Operator")
                show_table = (
                    False  # if there are no problems at all, don't show the table
                )
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

            else:
                logging.error("No output from strategy, double check strategy name")

            # reset problem operators before doing next check
        self.problem_operators = []
