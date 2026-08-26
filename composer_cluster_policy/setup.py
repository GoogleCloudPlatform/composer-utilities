from setuptools import find_packages, setup

setup(
    name="composer_cluster_policy",
    version="1.0.2",
    description="Airflow Cluster Policies and Governance for Google Cloud Composer",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "airflow.policy": [
            "composer_cluster_policy = composer_cluster_policy.policies",
        ],
    },
)
