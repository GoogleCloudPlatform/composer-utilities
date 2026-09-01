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
from copy import deepcopy

import pendulum
from airflow.decorators import dag, task, task_group
from airflow.models.param import Param
from airflow.utils.task_group import TaskGroup


class CustomSleepyTaskGroup(TaskGroup):
    def __init__(self, group_id, seconds=0, **kwargs):
        super().__init__(group_id=group_id, **kwargs)

        @task(task_group=self)
        def sleep_for(seconds):
            from time import sleep

            sleep(seconds)
            return seconds

        @task(task_group=self)
        def more_sleep_for(seconds):
            from time import sleep

            sleep(seconds)
            return seconds

        @task(task_group=self)
        def even_more_sleep_for(seconds):
            from time import sleep

            sleep(seconds)
            return seconds

        self.output = even_more_sleep_for(more_sleep_for(sleep_for(seconds)))


@dag(
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["taskgroup", "test", "dynamic_task_mapping"],
    params={
        "seconds_to_sleep": Param(
            1,
            type="integer",
            title="Seconds to Sleep",
            description="The number of seconds each task will sleep.",
        ),
        "number_of_sleepy_tasks": Param(
            10,
            type="integer",
            title="Number of Tasks to Sleep",
            description="The number of tasks that will sleep.",
        ),
    },
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=5),
    },
    # max_active_tasks=500,
)
def sleepy_task_group():
    @task
    def get_sleepy_seconds(params=None):
        """Gets the seconds_to_sleep value from the DAG run parameters."""
        seconds_to_sleep = deepcopy(params["seconds_to_sleep"])
        num_sleepy_tasks = deepcopy(params["number_of_sleepy_tasks"])
        return [seconds_to_sleep] * num_sleepy_tasks

    @task_group()
    def sleepy_task_group(seconds):
        sleep1 = CustomSleepyTaskGroup(
            group_id="my_custom_sleepy_task_group_1", seconds=seconds
        )
        sleep2 = CustomSleepyTaskGroup(
            group_id="my_custom_sleepy_task_group_2", seconds=sleep1.output
        )
        sleep3 = CustomSleepyTaskGroup(
            group_id="my_custom_sleepy_task_group_3", seconds=sleep2.output
        )
        return sleep3.output

    @task
    def done_sleeping(seconds):
        # The seconds variable is not a normal list, but a “lazy sequence” that
        # retrieves each individual value only when asked since this
        # task is mapped via dynamic task mapping. Therefore we "ask"
        # for the values by forcing the lazy sequence into a list using
        # the list constructor.
        try:
            seconds = list(seconds)
        except TypeError:
            seconds = [seconds]
        print(f"Done sleeping for {seconds=}")

    out = sleepy_task_group.expand(seconds=get_sleepy_seconds())
    done_sleeping(out)


sleepy_task_group()
