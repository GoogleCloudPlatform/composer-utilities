# Platform Engineering Repository: `airflow-platform-plugins`

## Overview
This repository is owned and maintained exclusively by the **Central Data Platform Engineering Team**. It contains the custom Managed Service for Apache Airflow (formerly Cloud Composer) plugin operators, configuration sizing tiers, and enterprise guardrail policies for Google Cloud Dataproc.

---

## Directory Structure
```
platform_team_repo/
├── README.md
├── plugins/
│   ├── __init__.py
│   ├── dataproc_governance_plugin.py          # AirflowPlugin class
│   ├── config/
│   │   ├── __init__.py
│   │   ├── cluster_tiers.py                   # T-Shirt sizing tiers (DEV, SMALL, STANDARD, HIGH_MEM)
│   │   └── governance_rules.py                # Platform limits, allowed subnets, mandatory labels
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── policy_violations.py               # Actionable fail-fast exception hierarchy
│   └── operators/
│       ├── __init__.py
│       ├── secure_dataproc_operator.py        # SecureDataprocCreateClusterOperator & Delete operator
│       └── dataproc_job_operator.py           # SecureDataprocSubmitJobOperator with provenance tags
└── tests/
    ├── __init__.py
    ├── test_cluster_tiers.py                  # Sizing template & config builder tests
    ├── test_guardrail_enforcement.py          # Security, Quotas, FinOps & Lifecycle tests
    ├── test_secure_dataproc_operator.py       # Operator lifecycle & execution tests
    └── test_dag_compliance.py                 # Platform CI static compliance & raw operator linter tests
```

---

## Local Unit Testing & Verification
Platform engineers run tests in milliseconds to verify that all platform guardrails enforce strictly:

```bash
# Run all platform tests (< 0.01s)
python3 -B -m unittest discover -s tests -v

# (OR run via unified workshop test dashboard)
python3 -B ../run_tests.py --scope platform

# Run guardrail tests showing live actionable error output
python3 -B -m unittest tests/test_guardrail_enforcement.py -v
```

---

## Deployment to Managed Service for Apache Airflow (formerly Cloud Composer)
```bash
export BUCKET=$(gcloud composer environments describe $COMPOSER_ENVIRONMENT \
    --location=$LOCATION \
    --format="value(storageConfig.bucket)")

# Sync platform plugins to GCS
gcloud storage cp -r plugins/* gs://$BUCKET/plugins/
```
