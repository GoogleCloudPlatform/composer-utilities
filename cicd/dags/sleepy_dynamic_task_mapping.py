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
"""Example of a Composer DAG that runs a long-running (5min) KubernetesPodOperator with retries."""

import datetime

import pendulum
from airflow.decorators import dag, task, task_group
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s


@dag(
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_tasks=100,
    default_args={
        "retries": 10,
        "retry_delay": datetime.timedelta(seconds=10),
    },
)
def sleepy_dynamic_task_mapping():
    @task
    def get_sleepy_minutes():
        return [1, 1, 1, 1, 1]

    @task_group
    def sleep_for(minutes):
        @task(multiple_outputs=True)
        def create_kpo_args(minutes):
            arguments = [
                "-c",
                rf"""
                set -e && \
                echo "Try number: $AIRFLOW_RETRY_NUMBER" && \
                echo "Sleeping for {minutes} minutes" && \
                sleep {minutes}m
                """,
            ]
            return {"arguments": arguments}

        kpo_args = create_kpo_args(minutes)
        KubernetesPodOperator(
            task_id="sleepy_pod",
            name="sleepy",
            cmds=["bash"],
            arguments=kpo_args["arguments"],
            env_vars={"AIRFLOW_RETRY_NUMBER": "{{ task_instance.try_number }}"},
            namespace="composer-user-workloads",
            image="gcr.io/google.com/cloudsdktool/google-cloud-cli:latest",
            config_file="/home/airflow/composer_kube_config",
            kubernetes_conn_id="kubernetes_default",
            container_resources=k8s.V1ResourceRequirements(
                requests={
                    "cpu": "100m",
                    "memory": "64Mi",
                }
            ),
        )

    sleep_for.expand(minutes=get_sleepy_minutes())


# Instantiate the DAG
sleepy_dynamic_task_mapping()
