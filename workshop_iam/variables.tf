# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_ids" {
  description = "Sequential list of 40 pre-created GCP Project IDs for the workshop"
  type        = list(string)
  default = [
    "afsummit2026-workshop-1",
    "afsummit2026-workshop-2",
    "afsummit2026-workshop-3",
    "afsummit2026-workshop-4",
    "afsummit2026-workshop-5",
    "afsummit2026-workshop-6",
    "afsummit2026-workshop-7",
    "afsummit2026-workshop-8",
    "afsummit2026-workshop-9",
    "afsummit2026-workshop-10",
    "afsummit2026-workshop-11",
    "afsummit2026-workshop-12",
    "afsummit2026-workshop-13",
    "afsummit2026-workshop-14",
    "afsummit2026-workshop-15",
    "afsummit2026-workshop-16",
    "afsummit2026-workshop-17",
    "afsummit2026-workshop-18",
    "afsummit2026-workshop-19",
    "afsummit2026-workshop-20",
    "afsummit2026-workshop-21",
    "afsummit2026-workshop-22",
    "afsummit2026-workshop-23",
    "afsummit2026-workshop-24",
    "afsummit2026-workshop-25",
    "afsummit2026-workshop-26",
    "afsummit2026-workshop-27",
    "afsummit2026-workshop-28",
    "afsummit2026-workshop-29",
    "afsummit2026-workshop-30",
    "afsummit2026-workshop-31",
    "afsummit2026-workshop-32",
    "afsummit2026-workshop-33",
    "afsummit2026-workshop-34",
    "afsummit2026-workshop-35",
    "afsummit2026-workshop-36",
    "afsummit2026-workshop-37",
    "afsummit2026-workshop-38",
    "afsummit2026-workshop-39",
    "afsummit2026-workshop-40"
  ]
}

variable "participant_emails" {
  description = "Sequential list of participant email addresses. Add emails as participants arrive."
  type        = list(string)
  default     = []
}

variable "workshop_iam_roles" {
  description = "Least-privilege IAM roles granted to each participant in their assigned project"
  type        = list(string)
  default = [
    # Cloud Composer (Airflow UI, Airflow REST API, Environment Metadata)
    "roles/composer.user",
    "roles/composer.viewer",

    # Cloud Storage (DAGs, Plugins, Cluster Policies)
    "roles/storage.objectUser",

    # Cloud Build (Building containers & CI/CD)
    "roles/cloudbuild.builds.editor",

    # Artifact Registry (Image repository)
    "roles/artifactregistry.writer",

    # Cloud Run (Deploying & accessing Control Panel)
    "roles/run.developer",
    "roles/run.invoker",

    # Cloud Shell & GCP Console Navigation
    "roles/browser",

    # Troubleshooting Logs & Health Monitoring
    "roles/logging.viewer",
    "roles/monitoring.viewer"
  ]
}

variable "workshop_service_account_id" {
  description = "Service account prefix in each project (e.g. 'composer' -> composer@PROJECT_ID.iam.gserviceaccount.com)"
  type        = string
  default     = "composer"
}

variable "grant_service_account_user" {
  description = "Whether to grant roles/iam.serviceAccountUser on the workshop service account"
  type        = bool
  default     = true
}
