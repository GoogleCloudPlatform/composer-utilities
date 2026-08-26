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

"""Airflow Plugin to load and activate Cloud Composer cluster policies in Airflow 3."""

from __future__ import annotations

import importlib.util
import logging
import os
import sys

logger = logging.getLogger("airflow.cluster_policy")

_plugins_dir = os.path.dirname(os.path.abspath(__file__))
if _plugins_dir not in sys.path:
    sys.path.insert(0, _plugins_dir)

# Ensure our airflow_local_settings.py in plugins/ is loaded (overriding any default Google stub in /etc/airflow/config)
_policy_file = os.path.join(_plugins_dir, "airflow_local_settings.py")
if os.path.isfile(_policy_file):
    try:
        _spec = importlib.util.spec_from_file_location("airflow_local_settings", _policy_file)
        if _spec and _spec.loader:
            _real_als = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_real_als)
            sys.modules["airflow_local_settings"] = _real_als
            
            import airflow.policies
            import airflow.settings
            
            airflow.policies.dag_policy = getattr(_real_als, "dag_policy", None)
            airflow.policies.task_policy = getattr(_real_als, "task_policy", None)
            airflow.settings.task_policy = getattr(_real_als, "task_policy", None)
            if hasattr(_real_als, "pod_mutation_hook"):
                airflow.policies.pod_mutation_hook = _real_als.pod_mutation_hook
                airflow.settings.pod_mutation_hook = _real_als.pod_mutation_hook
            logger.info("Composer Cluster Policy plugin successfully bound real policies to airflow.policies and airflow.settings.")
    except Exception as e:
        logger.error("Failed to load real airflow_local_settings via spec: %s", e)

try:
    from airflow.listeners import hookimpl

    class ClusterPolicyListener:
        """Enforces cluster policies at runtime on Airflow workers."""

        @hookimpl
        def on_task_instance_running(self, previous_state, task_instance, session=None):
            task = getattr(task_instance, "task", None)
            als = sys.modules.get("airflow_local_settings")
            if als and hasattr(als, "task_policy") and task:
                try:
                    als.task_policy(task)
                except Exception as e:
                    logger.error("Failed to apply task_policy in listener: %s", e)

    _listener = ClusterPolicyListener()
except Exception as e:
    _listener = None

try:
    from airflow.plugins_manager import AirflowPlugin

    class ComposerClusterPolicyPlugin(AirflowPlugin):
        """Airflow Plugin registering Cloud Composer cluster governance policies."""
        name = "composer_cluster_policy"
        listeners = [_listener] if _listener else []
except Exception:
    pass
