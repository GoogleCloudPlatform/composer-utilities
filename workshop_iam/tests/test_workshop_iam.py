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

import re
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class TestWorkshopIAM(unittest.TestCase):
    def test_variables_file_exists(self):
        var_file = BASE_DIR / "variables.tf"
        self.assertTrue(var_file.exists(), "variables.tf must exist")

    def test_main_file_exists(self):
        main_file = BASE_DIR / "main.tf"
        self.assertTrue(main_file.exists(), "main.tf must exist")

    def test_outputs_file_exists(self):
        out_file = BASE_DIR / "outputs.tf"
        self.assertTrue(out_file.exists(), "outputs.tf must exist")

    def test_project_ids_count_and_uniqueness(self):
        var_file = BASE_DIR / "variables.tf"
        content = var_file.read_text()
        project_matches = re.findall(r'"(afsummit2026-workshop-\d+)"', content)

        self.assertEqual(
            len(project_matches),
            40,
            f"Expected 40 project IDs, found {len(project_matches)}",
        )
        self.assertEqual(
            len(set(project_matches)), 40, "All 40 project IDs must be unique"
        )

        for i in range(1, 41):
            expected_project = f"afsummit2026-workshop-{i}"
            self.assertIn(
                expected_project,
                project_matches,
                f"Missing {expected_project}",
            )

    def test_least_privilege_roles(self):
        var_file = BASE_DIR / "variables.tf"
        content = var_file.read_text()
        role_matches = re.findall(r'"(roles/[a-zA-Z0-9\._]+)"', content)

        disallowed_roles = [
            "roles/owner",
            "roles/editor",
            "roles/resourcemanager.organizationAdmin",
        ]
        for disallowed in disallowed_roles:
            self.assertNotIn(
                disallowed,
                role_matches,
                f"Overly permissive role {disallowed} found",
            )

        required_roles = [
            "roles/composer.user",
            "roles/composer.viewer",
            "roles/storage.objectUser",
            "roles/cloudbuild.builds.editor",
            "roles/artifactregistry.writer",
            "roles/run.developer",
            "roles/run.invoker",
            "roles/browser",
            "roles/logging.viewer",
            "roles/monitoring.viewer",
        ]
        for req in required_roles:
            self.assertIn(
                req,
                role_matches,
                f"Missing expected least privilege role {req}",
            )

    def test_sequential_mapping_logic(self):
        projects = [f"afsummit2026-workshop-{i}" for i in range(1, 41)]
        emails = [
            "ddeleo@google.com",
            "jjaladi@google.com",
            "palakpatel@google.com",
            "rachanams@google.com",
        ]

        assigned_count = min(len(emails), len(projects))
        mapping = {emails[i]: projects[i] for i in range(assigned_count)}

        self.assertEqual(mapping["ddeleo@google.com"], "afsummit2026-workshop-1")
        self.assertEqual(mapping["jjaladi@google.com"], "afsummit2026-workshop-2")
        self.assertEqual(mapping["palakpatel@google.com"], "afsummit2026-workshop-3")
        self.assertEqual(mapping["rachanams@google.com"], "afsummit2026-workshop-4")
        self.assertEqual(len(mapping), 4)


if __name__ == "__main__":
    unittest.main()
