"""
 Copyright 2022 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """


from google.cloud.orchestration.airflow import service_v1


class GCPComposerService:
    def __init__(self, project_id: str, location: str, name: str) -> None:
        self.client: service_v1.EnvironmentsClient = service_v1.EnvironmentsClient()
        self.name = f"projects/{project_id}/locations/{location}/environments/{name}"

    def fetch_env(self) -> service_v1.types.Environment:
        request: service_v1.GetEnvironmentRequest = service_v1.GetEnvironmentRequest(
            name=self.name
        )
        response: service_v1.types.Environment = self.client.get_environment(
            request=request
        )
        return response
