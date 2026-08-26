# Copyright 2026 Google LLC
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

"""Unit tests for Composer Cluster Policy (airflow_local_settings)."""

from datetime import timedelta
import os
import sys
import unittest
from unittest.mock import patch

# Ensure the module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from composer_cluster_policy import policies as policy
except ImportError:
    import airflow_local_settings as policy


class MockObject:
    """Helper class for creating mock objects with dynamic attributes."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestResourceParsers(unittest.TestCase):
    """Tests for CPU and Memory string parsing utilities."""

    def test_parse_cpu_to_cores(self):
        self.assertEqual(policy.parse_cpu_to_cores("8000m"), 8.0)
        self.assertEqual(policy.parse_cpu_to_cores("500m"), 0.5)
        self.assertEqual(policy.parse_cpu_to_cores("4"), 4.0)
        self.assertEqual(policy.parse_cpu_to_cores(2), 2.0)
        self.assertIsNone(policy.parse_cpu_to_cores(None))
        self.assertIsNone(policy.parse_cpu_to_cores("invalid"))

    def test_parse_memory_to_mib(self):
        self.assertEqual(policy.parse_memory_to_mib("16000Mi"), 16000.0)
        self.assertEqual(policy.parse_memory_to_mib("16Gi"), 16384.0)
        self.assertAlmostEqual(policy.parse_memory_to_mib("1024Ki"), 1.0, places=2)
        self.assertIsNone(policy.parse_memory_to_mib(None))
        self.assertIsNone(policy.parse_memory_to_mib("invalid"))


class TestPodMutationHook(unittest.TestCase):
    """Tests for pod_mutation_hook in airflow_local_settings."""

    def setUp(self):
        self.container = MockObject(
            name="base",
            resources={
                "requests": {"cpu": "8000m", "memory": "16000Mi"},
                "limits": {"cpu": "8000m", "memory": "16000Mi"},
            },
        )
        self.pod = MockObject(
            metadata=MockObject(namespace="composer-user-workloads", labels={}),
            spec=MockObject(containers=[self.container]),
        )

    def test_clamps_excessive_cpu_and_memory(self):
        """Verify that requests exceeding 4 cores and 8192Mi are clamped."""
        policy.pod_mutation_hook(self.pod)

        requests = self.container.resources["requests"]
        limits = self.container.resources["limits"]

        self.assertEqual(requests["cpu"], "4000m")
        self.assertEqual(requests["memory"], "8192Mi")
        self.assertEqual(limits["cpu"], "4000m")
        self.assertEqual(limits["memory"], "8192Mi")

    def test_injects_default_resources_when_missing(self):
        """Verify fallback requests and limits are set when none are provided."""
        container_no_resources = MockObject(name="base", resources=None)
        pod = MockObject(
            metadata=MockObject(namespace="composer-user-workloads", labels={}),
            spec=MockObject(containers=[container_no_resources]),
        )

        policy.pod_mutation_hook(pod)

        self.assertIsNotNone(container_no_resources.resources)
        resources = container_no_resources.resources
        requests = resources["requests"] if isinstance(resources, dict) else resources.requests
        self.assertEqual(requests["cpu"], "500m")
        self.assertEqual(requests["memory"], "1024Mi")

    def test_injects_default_limits_when_only_requests_specified(self):
        """Verify fallback limits are injected when only requests are provided."""
        container_only_req = MockObject(
            name="worker",
            resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
        )
        pod = MockObject(
            metadata=MockObject(namespace="composer-user-workloads", labels={}),
            spec=MockObject(containers=[container_only_req]),
        )

        policy.pod_mutation_hook(pod)

        limits = container_only_req.resources["limits"]
        self.assertEqual(limits["cpu"], "2000m")
        self.assertEqual(limits["memory"], "4096Mi")
        self.assertEqual(container_only_req.resources["requests"]["cpu"], "250m")
        self.assertEqual(container_only_req.resources["requests"]["memory"], "512Mi")

    def test_handles_k8s_model_objects_without_type_error(self):
        """Verify object-based resource definitions are clamped and updated safely without TypeError."""
        class ResourceSpec:
            def __init__(self, cpu, memory):
                self.cpu = cpu
                self.memory = memory

        class K8sResources:
            def __init__(self, requests, limits):
                self.requests = requests
                self.limits = limits

        container_obj = MockObject(
            name="k8s_worker",
            resources=K8sResources(
                requests=ResourceSpec(cpu="8000m", memory="16000Mi"),
                limits=ResourceSpec(cpu="9000m", memory="18000Mi"),
            ),
        )
        pod = MockObject(
            metadata=MockObject(namespace="composer-user-workloads", labels={}),
            spec=MockObject(containers=[container_obj]),
        )

        policy.pod_mutation_hook(pod)

        self.assertEqual(container_obj.resources.requests.cpu, "4000m")
        self.assertEqual(container_obj.resources.requests.memory, "8192Mi")
        self.assertEqual(container_obj.resources.limits.cpu, "4000m")
        self.assertEqual(container_obj.resources.limits.memory, "8192Mi")

    def test_injects_metadata_delay_init_container(self):
        """Verify Solution 1: custom-init-setup init container is injected to delay for GKE metadata server."""
        with patch.object(policy, "ENABLE_INIT_CONTAINER_DELAY", True):
            policy.pod_mutation_hook(self.pod)
            self.assertIsNotNone(self.pod.spec.init_containers)
            names = [getattr(c, 'name', '') for c in self.pod.spec.init_containers]
            self.assertIn('custom-init-setup', names)

    def test_injects_governance_labels(self):
        """Verify standard corporate/governance labels are attached."""
        policy.pod_mutation_hook(self.pod)
        labels = self.pod.metadata.labels
        self.assertEqual(labels.get("managed-by"), "composer-cluster-policy")
        self.assertEqual(labels.get("policy-enforced"), "true")

    def test_overrides_disallowed_namespace(self):
        """Verify unauthorized namespaces are overridden to composer-user-workloads."""
        self.pod.metadata.namespace = "kube-system"
        policy.pod_mutation_hook(self.pod)
        self.assertEqual(self.pod.metadata.namespace, "composer-user-workloads")

    def test_sets_default_namespace_if_empty(self):
        """Verify unset namespace gets set to composer-user-workloads."""
        self.pod.metadata.namespace = None
        policy.pod_mutation_hook(self.pod)
        self.assertEqual(self.pod.metadata.namespace, "composer-user-workloads")


class TestTaskPolicy(unittest.TestCase):
    """Tests for task_policy in airflow_local_settings."""

    def test_enforces_execution_timeout(self):
        task = MockObject(task_id="test_task", execution_timeout=None, retries=1)
        policy.task_policy(task)
        self.assertEqual(task.execution_timeout, timedelta(hours=4))

    def test_enforces_kpo_retries_and_backoff(self):
        """Verify Solution 2: KPO tasks receive minimum retries and backoff for metadata server resilience."""
        kpo_task = MockObject(task_id='gcloud_ls', execution_timeout=timedelta(hours=1), retries=0, retry_delay=timedelta(seconds=0))
        kpo_task.__class__.__name__ = 'KubernetesPodOperator'
        policy.task_policy(kpo_task)
        self.assertEqual(kpo_task.retries, 2)
        self.assertEqual(kpo_task.retry_delay, timedelta(seconds=10))
        self.assertTrue(getattr(kpo_task, 'retry_exponential_backoff', False))

    def test_clamps_excessive_retries(self):
        task = MockObject(task_id="test_task", execution_timeout=timedelta(minutes=30), retries=10)
        policy.task_policy(task)
        self.assertEqual(task.retries, 3)


class TestDagPolicy(unittest.TestCase):
    """Tests for dag_policy in airflow_local_settings."""

    def test_dag_policy_runs_cleanly(self):
        dag = MockObject(
            dag_id="test_dag",
            catchup=False,
            tags=["domain:data"],
            default_args={"owner": "data-team"},
        )
        policy.dag_policy(dag)

    def test_dag_policy_rejects_catchup(self):
        """Verify dag_policy raises AirflowClusterPolicyViolation when catchup=True."""
        dag = MockObject(
            dag_id="bad_dag",
            catchup=True,
            tags=["domain:data"],
            default_args={"owner": "data-team"},
        )
        with self.assertRaises(policy.AirflowClusterPolicyViolation):
            policy.dag_policy(dag)

    def test_dag_policy_clamps_concurrency_and_timeout(self):
        """Verify dag_policy clamps max_active_runs and injects dagrun_timeout."""
        dag = MockObject(
            dag_id="unconstrained_dag",
            catchup=False,
            max_active_runs=16,
            dagrun_timeout=None,
            tags=[],
            default_args={"owner": "data-team"},
        )
        policy.dag_policy(dag)
        self.assertEqual(dag.max_active_runs, 2)
        self.assertEqual(dag.dagrun_timeout, timedelta(hours=4))
        self.assertIn("policy:remediated", dag.tags)

    def test_dag_policy_exempts_airflow_monitoring(self):
        """Verify dag_policy safely ignores internal Cloud Composer monitoring DAGs."""
        dag = MockObject(
            dag_id="airflow_monitoring",
            catchup=True,
            default_args={"owner": "None"},
            tags=[],
        )
        # Should not raise any AirflowClusterPolicyViolation
        policy.dag_policy(dag)


if __name__ == "__main__":
    unittest.main()
