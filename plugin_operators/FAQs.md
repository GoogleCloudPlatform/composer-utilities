# Frequently Asked Questions (FAQs): Enterprise Plugin Operators & Architecture

This document answers common architectural, CI/CD, and local testing questions for enterprise teams implementing custom Airflow Plugin Operators on **Managed Service for Apache Airflow (formerly Cloud Composer)**.

---

## Table of Contents
1. [Should the Plugin Operators Code Reside in Its Own Git Repository?](#1-should-the-plugin-operators-code-reside-in-its-own-git-repository)
2. [How Does Automated Testing Happen in the CI/CD Process on Pull Requests?](#2-how-does-automated-testing-happen-in-the-cicd-process-on-pull-requests)
3. [How Does Unit Testing Happen Locally and in CI When Plugin Operators Are in a Separate Git Repo?](#3-how-does-unit-testing-happen-locally-and-in-ci-when-plugin-operators-are-in-a-separate-git-repo)

---

### 1. Should the Plugin Operators Code Reside in Its Own Git Repository?

**Yes, strongly recommended.** In enterprise organizations, platform plugin operators should reside in a dedicated central repository (e.g., `airflow-platform-plugins` or `composer-governance-plugins`, mirrored as [`platform_team_repo`](file:///Users/palakpatel/Documents/playground/composer-utilities/plugin_operators/platform_team_repo)) separate from domain data team DAG repositories for three primary reasons:

1. **Strict Access Control & CODEOWNERS Security:**
   * Platform governance rules (e.g., maximum worker limits, mandatory CMEK keys, private IP enforcement, allowed VPC subnets) must **not** be editable by business DAG authors.
   * A separate repository allows strict branch protection and GitHub `CODEOWNERS` rules restricted exclusively to the Platform Engineering / Cloud Infrastructure team.
2. **Independent Release Lifecycle & Semantic Versioning:**
   * Platform operators evolve at a different cadence than daily business data pipelines.
   * Versioning platform plugins (e.g., `company-airflow-plugins==1.2.0`) allows backward-compatible improvements and structured release notes without requiring simultaneous DAG redeployments.
3. **Multi-Tenant / Multi-Environment Distribution:**
   * A single, centralized platform operator plugin can be deployed across **dozens of independent Managed Service for Apache Airflow (formerly Cloud Composer) environments** (Dev, Staging, Production) and consumed by dozens of distributed domain DAG repositories (Marketing, Finance, Supply Chain, ML Platform).

---

### 2. How Does Automated Testing Happen in the CI/CD Process on Pull Requests?

#### A. When a PR is Created in the Platform Plugin Repo (`platform_team_repo`):
The Platform CI pipeline (Cloud Build, GitHub Actions, or GitLab CI) executes:
1. **Linting & Code Quality:** Runs `ruff`, `flake8`, and `black` to enforce enterprise code standards.
2. **Type Checking:** Runs `mypy` to verify typing across operator arguments and configuration dictionaries.
3. **Comprehensive Guardrail Unit Tests:** Runs `python3 -m unittest` matrix tests verifying that:
   * Sizing tiers (`DEV_SINGLE_NODE`, `STANDARD_ANALYTICS`, etc.) generate valid Dataproc v1 structures.
   * Security violations (`RULE_SEC_001` - `RULE_SEC_004`) fail fast and reject insecure configurations.
   * Quota violations (`RULE_QUOTA_001` - `RULE_QUOTA_004`) reject oversized clusters.
   * FinOps metadata labels (`RULE_FIN_001` - `RULE_FIN_004`) enforce required cost attribution tags.
   * Lifecycle TTLs (`RULE_LIFE_001` - `RULE_LIFE_002`) enforce idle termination.
4. **Airflow Plugin Registration Test:** Confirms the `DataprocGovernancePlugin` registers cleanly with Airflow's `PluginManager` without import errors.
5. **Deployment / Packaging:**
   * **GCS Sync (Standard Managed Service for Apache Airflow):** On merge to `main`, automatically syncs `plugins/` to `gs://$COMPOSER_BUCKET/plugins/`.
   * **Artifact Packaging (Optional):** Builds a Python wheel (`.whl`) and pushes it to **Google Cloud Artifact Registry**.

#### B. When a PR is Created in a Domain DAG Repo (`data_team_repo`):
The DAG CI pipeline executes:
1. **Dependency Resolution:**
   * Fetches the platform plugins via GCS (`gcloud storage cp -r gs://$COMPOSER_DEV_BUCKET/plugins/ /tmp/composer_plugins/`) and sets `PYTHONPATH`, OR installs the platform plugin wheel (`company-airflow-plugins`) from Artifact Registry.
2. **Airflow DagBag Integrity & Parsing Test:**
   * Loads all repository DAGs using `airflow.models.DagBag(dag_folder='dags/', include_examples=False)`.
   * Asserts `len(dagbag.import_errors) == 0`.
3. **Governance & Guardrail Compliance Check:**
   * Ensures that any DAG instantiating `SecureDataprocCreateClusterOperator` passes mandatory parameters (`team`, `cost_center`, `environment`) and satisfies platform quotas.
4. **Pipeline Simulation / Mock Execution:** Runs unit tests on custom Python callables and transformations.
5. **Deployment:** On merge to `main`, the pipeline syncs `dags/` to the target Composer GCS bucket (`gs://$COMPOSER_BUCKET/dags/`).

---

### 3. How Does Unit Testing Happen Locally and in CI When Plugin Operators Are in a Separate Git Repo?

When the custom plugin operator code lives in **Repo A (`platform_team_repo`)** and the data engineer is writing and testing DAGs in **Repo B (`data_team_repo`)**, teams use the following local developer workflows and automated CI pipelines:

---

#### Local Developer Workflows

##### Workflow 1 (Recommended for Workshops & Fast Local Dev): Zero-Install `PYTHONPATH` Linking
For data engineers who want instant, frictionless feedback on their DAGs without needing to configure complex virtual environments, build wheels, or install packages:

1. **Folder Layout:**
   ```text
   workspace/
   ├── platform_team_repo/   # Repo A: Platform Operator & Rule Definitions
   └── data_team_repo/       # Repo B: Domain Airflow DAGs
   ```
2. **Execute Local DAG Tests Instantly (< 0.01s):**
   ```bash
   # From inside data_team_repo:
   export PYTHONPATH="../platform_team_repo/plugins:$PYTHONPATH"

   # Run DAG integrity and policy compliance tests
   python3 -m unittest discover -s tests -v
   ```
   * The DAG dynamically imports `from operators.secure_dataproc_operator import SecureDataprocCreateClusterOperator, ClusterTier`.
   * Unit tests run 100% in memory with zero cloud latency and zero GCP credentials required.

---

##### Workflow 2: Active Co-Development / Platform Engineer (`pip install -e` Editable Mode)
When developing or testing a *new platform guardrail or sizing tier* in **Repo A** and verifying it against DAGs in **Repo B** on a local laptop:

1. **Install Repo A in Editable Mode inside Repo B's Virtualenv:**
   ```bash
   cd data_team_repo
   source .venv/bin/activate

   # Install local platform repo as an editable live link
   pip install -e ../platform_team_repo
   ```
2. **Instant Feedback:** Any edit saved in `platform_team_repo/plugins/operators/secure_dataproc_operator.py` is **instantly live** inside `data_team_repo` local test runs without building wheels or reinstalling!

---

##### Workflow 3: Mirroring Plugins from Managed Service for Apache Airflow (formerly Cloud Composer) Dev Bucket
If data engineers want to test against the exact plugins currently deployed in the Managed Service for Apache Airflow development environment without cloning the platform repo:

```bash
# In data_team_repo:
mkdir -p .composer_plugins
gcloud storage cp -r gs://$COMPOSER_DEV_BUCKET/plugins/* .composer_plugins/
export PYTHONPATH="$(pwd)/.composer_plugins:$PYTHONPATH"

# Run DAG tests locally
python3 -m unittest discover -s tests -v
```

---

##### Workflow 4: Enterprise Private PyPI Package in Artifact Registry
For large enterprises requiring strict semantic version pinning across 50+ distributed domain repositories:

1. **Platform Repo CI:** Builds a versioned wheel (`company_airflow_plugins-1.2.0.whl`) and pushes it to Google Cloud Artifact Registry.
2. **DAG Repo `requirements-dev.txt`:**
   ```text
   apache-airflow>=2.8.0
   apache-airflow-providers-google>=10.15.0
   company-airflow-plugins>=1.2.0 --extra-index-url https://us-central1-python.pkg.dev/my-gcp-project/airflow-plugins-pypi/simple/
   ```
3. **Local Test Execution:** `pip install -r requirements-dev.txt && python3 -m unittest discover -s tests -v`.

---

#### IDE Integration (VS Code / PyCharm Local Setup)
To enable real-time linting, autocomplete, and in-editor test execution in VS Code, add `.vscode/settings.json` to `data_team_repo`:

```json
{
  "python.analysis.extraPaths": [
    "../platform_team_repo/plugins",
    "./plugins"
  ],
  "python.testing.unittestArgs": [
    "-v",
    "-s",
    "./tests",
    "-p",
    "test_*.py"
  ],
  "python.testing.unittestEnabled": true,
  "python.testing.pytestEnabled": false
}
```
* **Benefits:** Data engineers get instant IntelliSense autocomplete for `SecureDataprocCreateClusterOperator` and `ClusterTier`, real-time red underlines if mandatory parameters (`team`, `cost_center`) are missing, and green "Run Test" buttons directly in the editor.

---

#### Automated CI/CD Pipeline on Pull Requests

When a PR is opened in `data_team_repo`, the CI runner (Cloud Build / GitHub Actions) performs automated testing via either of the following strategies:

* **GCS Plugin Sync in CI (Managed Service for Apache Airflow Approach):**
  ```yaml
  # Cloud Build / GitHub Actions Step:
  - name: 'Fetch Governed Platform Plugins'
    run: |
      gcloud storage cp -r gs://$COMPOSER_DEV_BUCKET/plugins/ /tmp/composer_plugins/
      export PYTHONPATH="/tmp/composer_plugins:$PYTHONPATH"
      python3 -m unittest discover -s tests -v
  ```
* **Artifact Registry Wheel Install (Enterprise Package Approach):**
  ```yaml
  - name: 'Install Governed Platform Plugins & Run Tests'
    run: |
      pip install -r requirements-dev.txt
      python3 -m unittest discover -s tests -v
  ```
