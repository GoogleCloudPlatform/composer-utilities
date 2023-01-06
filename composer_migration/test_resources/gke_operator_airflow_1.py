# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# [START composer_gkeoperator_airflow_1]


from airflow import models
from airflow.operators.bash_operator import BashOperator
from airflow.providers.google.cloud.operators.kubernetes_engine import (
    GKECreateClusterOperator,
    GKEDeleteClusterOperator,
    GKEStartPodOperator,
)
from airflow.utils.dates import days_ago


with models.DAG(
    "example_gcp_gke",
    schedule_interval=None,  # Override to match your needs
    start_date=days_ago(1),
    tags=["example"],
) as dag:

    # [START composer_gke_create_cluster_airflow_1]
    # [START composer_gkeoperator_minconfig_airflow_1]
    # [START composer_gkeoperator_templateconfig_airflow_1]
    # [START composer_gkeoperator_affinity_airflow_1]
    # [START composer_gkeoperator_fullconfig_airflow_1]
    # TODO(developer): update with your values
    PROJECT_ID = "leah-playground"
    CLUSTER_ZONE = "us-west1-a"
    CLUSTER_NAME = "example-cluster"
    # [END composer_gkeoperator_minconfig_airflow_1]
    # [END composer_gkeoperator_templateconfig_airflow_1]
    # [END composer_gkeoperator_affinity_airflow_1]
    # [END composer_gkeoperator_fullconfig_airflow_1]
    CLUSTER = {"name": CLUSTER_NAME, "initial_node_count": 1}
    # [END composer_gke_create_cluster_airflow_1]
    # [START composer_gke_create_cluster_airflow_1]
    create_cluster = GKECreateClusterOperator(
        task_id="create_cluster",
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
        body=CLUSTER,
    )
    # Using the BashOperator to create node pools is a workaround
    # In Airflow 2, because of https://github.com/apache/airflow/pull/17820
    # Node pool creation can be done using the GKECreateClusterOperator

    create_node_pools = BashOperator(
        task_id="create_node_pools",
        bash_command=f"gcloud container node-pools create pool-0 \
                        --cluster {CLUSTER_NAME} \
                        --num-nodes 1 \
                        --zone {CLUSTER_ZONE} \
                        && gcloud container node-pools create pool-1 \
                        --cluster {CLUSTER_NAME} \
                        --num-nodes 1 \
                        --zone {CLUSTER_ZONE}",
    )
    # [END composer_gke_create_cluster_airflow_1]

    # [START composer_gkeoperator_minconfig_airflow_1]
    kubernetes_min_pod = GKEStartPodOperator(
        # The ID specified for the task.
        task_id="pod-ex-minimum",
        # Name of task you want to run, used to generate Pod ID.
        name="pod-ex-minimum",
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
        cluster_name=CLUSTER_NAME,
        # Entrypoint of the container, if not specified the Docker container's
        # entrypoint is used. The cmds parameter is templated.
        cmds=["echo"],
        # The namespace to run within Kubernetes, default namespace is
        # `default`.
        namespace="default",
        # Docker image specified. Defaults to hub.docker.com, but any fully
        # qualified URLs will point to a custom repository. Supports private
        # gcr.io images if the Composer Environment is under the same
        # project-id as the gcr.io images and the service account that Composer
        # uses has permission to access the Google Container Registry
        # (the default service account has permission)
        image="gcr.io/gcp-runtimes/ubuntu_18_0_4",
    )
    # [END composer_gkeoperator_minconfig_airflow_1]

    # [START composer_gkeoperator_templateconfig_airflow_1]
    kubenetes_template_ex = GKEStartPodOperator(
        task_id="ex-kube-templates",
        name="ex-kube-templates",
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
        cluster_name=CLUSTER_NAME,
        namespace="default",
        image="bash",
        # All parameters below are able to be templated with jinja -- cmds,
        # arguments, env_vars, and config_file. For more information visit:
        # https://airflow.apache.org/docs/apache-airflow/stable/macros-ref.html
        # Entrypoint of the container, if not specified the Docker container's
        # entrypoint is used. The cmds parameter is templated.
        cmds=["echo"],
        # DS in jinja is the execution date as YYYY-MM-DD, this docker image
        # will echo the execution date. Arguments to the entrypoint. The docker
        # image's CMD is used if this is not provided. The arguments parameter
        # is templated.
        arguments=["{{ ds }}"],
        # The var template variable allows you to access variables defined in
        # Airflow UI. In this case we are getting the value of my_value and
        # setting the environment variable `MY_VALUE`. The pod will fail if
        # `my_value` is not set in the Airflow UI.
        env_vars={"MY_VALUE": "{{ var.value.my_value }}"},
    )
    # [END composer_gkeoperator_templateconfig_airflow_1]

    # [START composer_gkeoperator_affinity_airflow_1]
    kubernetes_affinity_ex = GKEStartPodOperator(
        task_id="ex-pod-affinity",
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
        cluster_name=CLUSTER_NAME,
        name="ex-pod-affinity",
        namespace="default",
        image="perl",
        cmds=["perl"],
        arguments=["-Mbignum=bpi", "-wle", "print bpi(2000)"],
        # affinity allows you to constrain which nodes your pod is eligible to
        # be scheduled on, based on labels on the node. In this case, if the
        # label 'cloud.google.com/gke-nodepool' with value
        # 'nodepool-label-value' or 'nodepool-label-value2' is not found on any
        # nodes, it will fail to schedule.
        affinity={
            "nodeAffinity": {
                # requiredDuringSchedulingIgnoredDuringExecution means in order
                # for a pod to be scheduled on a node, the node must have the
                # specified labels. However, if labels on a node change at
                # runtime such that the affinity rules on a pod are no longer
                # met, the pod will still continue to run on the node.
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": [
                        {
                            "matchExpressions": [
                                {
                                    # When nodepools are created in Google Kubernetes
                                    # Engine, the nodes inside of that nodepool are
                                    # automatically assigned the label
                                    # 'cloud.google.com/gke-nodepool' with the value of
                                    # the nodepool's name.
                                    "key": "cloud.google.com/gke-nodepool",
                                    "operator": "In",
                                    # The label key's value that pods can be scheduled
                                    # on.
                                    "values": [
                                        "pool-1",
                                    ],
                                }
                            ]
                        }
                    ]
                }
            }
        },
    )
    # [END composer_gkeoperator_affinity_airflow_1]
    # [START composer_gkeoperator_fullconfig_airflow_1]
    kubernetes_full_pod = GKEStartPodOperator(
        task_id="ex-all-configs",
        name="full",
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
        cluster_name=CLUSTER_NAME,
        namespace="default",
        image="perl",
        # Entrypoint of the container, if not specified the Docker container's
        # entrypoint is used. The cmds parameter is templated.
        cmds=["perl"],
        # Arguments to the entrypoint. The docker image's CMD is used if this
        # is not provided. The arguments parameter is templated.
        arguments=["-Mbignum=bpi", "-wle", "print bpi(2000)"],
        # The secrets to pass to Pod, the Pod will fail to create if the
        # secrets you specify in a Secret object do not exist in Kubernetes.
        secrets=[],
        # Labels to apply to the Pod.
        labels={"pod-label": "label-name"},
        # Timeout to start up the Pod, default is 120.
        startup_timeout_seconds=120,
        # The environment variables to be initialized in the container
        # env_vars are templated.
        env_vars={"EXAMPLE_VAR": "/example/value"},
        # If true, logs stdout output of container. Defaults to True.
        get_logs=True,
        # Determines when to pull a fresh image, if 'IfNotPresent' will cause
        # the Kubelet to skip pulling an image if it already exists. If you
        # want to always pull a new image, set it to 'Always'.
        image_pull_policy="Always",
        # Annotations are non-identifying metadata you can attach to the Pod.
        # Can be a large range of data, and can include characters that are not
        # permitted by labels.
        annotations={"key1": "value1"},
        # Resource specifications for Pod, this will allow you to set both cpu
        # and memory limits and requirements.
        # Prior to Airflow 1.10.4, resource specifications were
        # passed as a Pod Resources Class object,
        # If using this example on a version of Airflow prior to 1.10.4,
        # import the "pod" package from airflow.contrib.kubernetes and use
        # resources = pod.Resources() instead passing a dict
        # For more info see:
        # https://github.com/apache/airflow/pull/4551
        resources={"limit_memory": "250M", "limit_cpu": "100m"},
        # If true, the content of /airflow/xcom/return.json from container will
        # also be pushed to an XCom when the container ends.
        do_xcom_push=False,
        # List of Volume objects to pass to the Pod.
        volumes=[],
        # List of VolumeMount objects to pass to the Pod.
        volume_mounts=[],
        # Affinity determines which nodes the Pod can run on based on the
        # config. For more information see:
        # https://kubernetes.io/docs/concepts/configuration/assign-pod-node/
        affinity={},
    )
    # [END composer_gkeoperator_fullconfig_airflow_1]
    # [START composer_gkeoperator_delete_cluster_airflow_1]
    delete_cluster = GKEDeleteClusterOperator(
        task_id="delete_cluster",
        name=CLUSTER_NAME,
        project_id=PROJECT_ID,
        location=CLUSTER_ZONE,
    )
    # [END composer_gkeoperator_delete_cluster_airflow_1]

    create_cluster >> create_node_pools >> kubernetes_min_pod >> delete_cluster
    create_cluster >> create_node_pools >> kubernetes_full_pod >> delete_cluster
    create_cluster >> create_node_pools >> kubernetes_affinity_ex >> delete_cluster
    create_cluster >> create_node_pools >> kubenetes_template_ex >> delete_cluster

# [END composer_gkeoperator_airflow_1]
