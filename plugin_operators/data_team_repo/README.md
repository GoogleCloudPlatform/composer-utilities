# Domain Data Team Repository: `analytics-dags`

## Overview
This repository is owned by the **Marketing & Analytics Data Engineering Team**. It contains domain DAG pipelines that leverage the platform-governed operators (`SecureDataprocCreateClusterOperator`, `SecureDataprocSubmitJobOperator`, `SecureDataprocDeleteClusterOperator`).

---

## Directory Structure
```
data_team_repo/
├── README.md
├── dags/
│   ├── sample_secure_dataproc_dag.py          # Production ETL pipeline demo
│   └── sample_guardrail_violation_dag.py      # Guardrail fail-fast demonstration
└── tests/
    ├── __init__.py
    └── test_dag_integrity.py                  # DAG parsing & compliance tests
```

---

## Local Unit Testing: Zero-Install `PYTHONPATH` Workflow
Data engineers test their DAGs locally with **zero installation overhead** by pointing `PYTHONPATH` to the platform repository's `plugins/` directory:

```bash
# 1. From inside data_team_repo:
export PYTHONPATH="../platform_team_repo/plugins:$PYTHONPATH"

# 2. Run local DAG integrity & policy compliance tests (< 0.05s)
python3 -B -m unittest discover -s tests -v

# (OR run via unified workshop test dashboard)
python3 -B ../run_tests.py --scope data
```

---

## Deployment to Managed Service for Apache Airflow (formerly Cloud Composer)
```bash
export BUCKET=$(gcloud composer environments describe $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --format="value(storageConfig.bucket)")

# Sync business DAGs to GCS
gcloud storage cp -r dags/* gs://$BUCKET/dags/
```
