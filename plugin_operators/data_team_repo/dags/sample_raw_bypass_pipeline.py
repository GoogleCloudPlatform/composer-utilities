from datetime import datetime
from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import DataprocCreateClusterOperator

with DAG(dag_id="sample_raw_bypass_pipeline", schedule=None, start_date=datetime(2026, 1, 1)) as dag:
    # ❌ SHADOW IT ATTEMPT: Direct use of raw native operator without governance
    create_cluster = DataprocCreateClusterOperator(
        task_id="create_unhardened_cluster",
        project_id="my-enterprise-project",
        region="us-central1",
        cluster_name="rogue-cluster",
        cluster_config={
            "master_config": {"num_instances": 1, "machine_type_uri": "n1-standard-4"},
        },
    )
