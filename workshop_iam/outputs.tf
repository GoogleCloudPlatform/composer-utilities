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

output "assigned_pairings" {
  description = "Sequential mapping of participants to their assigned GCP project"
  value = {
    for email, project in local.participant_project_map :
    email => project
  }
}

output "unassigned_available_projects" {
  description = "Projects still available for upcoming participants"
  value       = slice(var.project_ids, local.assigned_count, length(var.project_ids))
}

output "unassigned_emails_overflow" {
  description = "Emails that could not be assigned due to lack of projects (if any)"
  value = length(var.participant_emails) > length(var.project_ids) ? slice(
    var.participant_emails,
    length(var.project_ids),
    length(var.participant_emails)
  ) : []
}
