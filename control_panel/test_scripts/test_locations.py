# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from googleapiclient.discovery import build


def test():
    composer_client = build("composer", "v1")
    project = "YOUR_PROJECT_ID"

    try:
        response = (
            composer_client.projects()
            .locations()
            .list(name=f"projects/{project}")
            .execute()
        )
        print(json.dumps(response, indent=2))

        # Now list environments in those locations
        for loc in response.get("locations", []):
            loc_id = loc["locationId"]
            # Only loop a few to test
            envs = (
                composer_client.projects()
                .locations()
                .environments()
                .list(parent=f"projects/{project}/locations/{loc_id}")
                .execute()
            )
            if "environments" in envs:
                print(f"Found environments in {loc_id}:")
                for e in envs["environments"]:
                    print(e["name"])
    except Exception as e:
        print(f"Error: {e}")


test()
