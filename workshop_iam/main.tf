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

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  # Determine how many participants can be mapped based on available projects
  assigned_count = min(length(var.participant_emails), length(var.project_ids))

  # Sequentially map index i of emails to index i of project_ids
  participant_project_map = {
    for idx in range(local.assigned_count) :
    var.participant_emails[idx] => var.project_ids[idx]
  }

  # Flatten map to [participant, project, role] for non-destructive for_each assignment
  participant_project_roles = flatten([
    for email, project_id in local.participant_project_map : [
      for role in var.workshop_iam_roles : {
        key        = "${email}-${project_id}-${role}"
        email      = email
        project_id = project_id
        role       = role
      }
    ]
  ])

  # Service Account User bindings
  participant_sa_bindings = var.grant_service_account_user ? [
    for email, project_id in local.participant_project_map : {
      key        = "${email}-${project_id}-sa-user"
      email      = email
      project_id = project_id
    }
  ] : []
}

# 1. Project-level least-privilege IAM bindings
# Uses google_project_iam_member to be additive and avoid purging GCP service agents
resource "google_project_iam_member" "participant_roles" {
  for_each = { for item in local.participant_project_roles : item.key => item }

  project = each.value.project_id
  role    = each.value.role
  member  = "user:${each.value.email}"
}

# 2. Grant SA User on composer@${PROJECT_ID}.iam.gserviceaccount.com
# Enables Cloud Run deployments & Cloud Build runs acting as the runtime SA
resource "google_service_account_iam_member" "sa_user" {
  for_each = { for item in local.participant_sa_bindings : item.key => item }

  service_account_id = "projects/${each.value.project_id}/serviceAccounts/${var.workshop_service_account_id}@${each.value.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "user:${each.value.email}"

  depends_on = [google_project_iam_member.participant_roles]
}
