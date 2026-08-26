from setuptools import find_packages, setup

setup(
    name="composer_cluster_policy",
    version="1.0.0",
    description="Airflow Cluster Policies and Governance for Google Cloud Composer",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "airflow.policy": [
            "task_policy = composer_cluster_policy.policies:task_policy",
            "dag_policy = composer_cluster_policy.policies:dag_policy",
            "pod_mutation_hook = composer_cluster_policy.policies:pod_mutation_hook",
        ],
    },
)
