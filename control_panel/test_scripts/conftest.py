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

from unittest.mock import MagicMock
import google.auth
import googleapiclient.discovery  # type: ignore


# Mock google.auth.default to return mock credentials and project ID
mock_credentials = MagicMock()
mock_credentials.token = "mock-token"
mock_credentials.valid = True
mock_credentials.refresh = MagicMock()

google.auth.default = MagicMock(return_value=(mock_credentials, "mock-project-id"))

# Mock googleapiclient.discovery.build to return a mock client
mock_client = MagicMock()
googleapiclient.discovery.build = MagicMock(return_value=mock_client)
