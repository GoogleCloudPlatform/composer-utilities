# Cloud Composer Workshop IAM Automation

This directory contains Terraform scripts to automate sequential IAM onboarding for participants across the **40 pre-created workshop projects** (`afsummit2026-workshop-1` to `afsummit2026-workshop-40`).

---

## Least-Privilege IAM Roles Granted

Participants receive **strictly** the permissions needed for workshop exercises (Control Panel, Cluster Policies, CI/CD Cloud Build, DAG Linter & Profiler, Cloud Shell Editor), with **no access** to unrelated GCP services:

| Component | Role | Purpose |
| :--- | :--- | :--- |
| **Cloud Composer** | `roles/composer.user` | Airflow Web UI & REST API (trigger/pause/inspect DAGs) |
| **Cloud Composer** | `roles/composer.viewer` | Environment metadata & status viewing in GCP Console |
| **Cloud Storage** | `roles/storage.objectUser` | Upload/manage DAGs, plugins (`airflow_local_settings.py`), and test data |
| **Cloud Build** | `roles/cloudbuild.builds.editor` | Submit & monitor CI/CD builds |
| **Artifact Registry** | `roles/artifactregistry.writer` | Push & pull container images |
| **Cloud Run** | `roles/run.developer` + `roles/run.invoker` | Deploy & access the Control Panel dashboard |
| **Cloud Shell / Console** | `roles/browser` | Navigate & select the assigned project in GCP Console |
| **Cloud Logging** | `roles/logging.viewer` | View task, scheduler, build, and container logs |
| **Cloud Monitoring** | `roles/monitoring.viewer` | View environment health and resource charts |
| **Service Account** | `roles/iam.serviceAccountUser` | Deploy Cloud Run / trigger Cloud Build acting as the workshop SA |

---

## Quickstart Guide

### 1. Add Participant Emails
Open `terraform.tfvars` and append emails in order:

```hcl
participant_emails = [
  "rachana@example.com",     # -> Automatically assigned to afsummit2026-workshop-1
  "attendee2@company.com", # -> Automatically assigned to afsummit2026-workshop-2
]
```

### 2. Apply Terraform
```bash
cd workshop_iam
terraform init
terraform apply
```

### 3. Check Assignments & Remaining Available Projects
```bash
# View who was assigned to which project
terraform output assigned_pairings

# View remaining projects ready for new attendees
terraform output unassigned_available_projects
```
