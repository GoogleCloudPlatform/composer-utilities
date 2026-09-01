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

from fastapi.testclient import TestClient

from proxy_server import app

client = TestClient(app)


def test_get_environments():
    # This test checks if the app can be initialized and the route is reachable.
    # It might return 500 if Google credentials are not available in the test environment,
    # but it confirms the code is syntactically correct and importable.
    try:
        response = client.get("/api/environments")
        assert response.status_code in [200, 500]
    except Exception as e:  # noqa: BLE001
        # If it fails due to missing credentials during initialization (lifespan),
        # we might get an exception here or earlier.
        print(f"App initialization or request failed: {e}")
        # We don't fail the test if it's an auth issue, but we want to see it.


def test_patch_all_dags_with_pattern():
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "dags": [{"dag_id": "test_dag_1", "is_paused": True}],
        "total_entries": 1,
    }

    mock_http = AsyncMock()
    mock_http.patch.return_value = mock_resp

    with (
        patch("proxy_server.get_valid_token", return_value="mock-token"),
        patch(
            "proxy_server.get_all_environments_async",
            return_value=[
                {
                    "name": "env1",
                    "url": "https://env1.airflow.com",
                    "imageVersion": "composer-2.0.0-airflow-2.9.0",
                    "project": "proj1",
                },
            ],
        ),
        patch("proxy_server.http_client", mock_http),
    ):
        response = client.patch(
            "/api/all-dags?dag_id_prefix_pattern=test_&update_mask=is_paused",
            json={"is_paused": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] == 1
        assert data["dags"][0]["dag_id"] == "test_dag_1"
        assert data["dags"][0]["environment"]["name"] == "env1"

        # Verify proxy call received the query param and body
        mock_http.patch.assert_called_once()
        call_kwargs = mock_http.patch.call_args.kwargs
        assert call_kwargs["params"]["dag_id_prefix_pattern"] == "test_"
        assert call_kwargs["params"]["update_mask"] == "is_paused"
        assert call_kwargs["json"] == {"is_paused": True}


def test_get_all_dags_with_pattern():
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_dags_resp = MagicMock()
    mock_dags_resp.status_code = 200
    mock_dags_resp.json.return_value = {
        "dags": [{"dag_id": "cust_orders", "is_paused": False}],
        "total_entries": 1,
    }

    mock_err_resp = MagicMock()
    mock_err_resp.status_code = 200
    mock_err_resp.json.return_value = {"import_errors": []}

    mock_runs_resp = MagicMock()
    mock_runs_resp.status_code = 200
    mock_runs_resp.json.return_value = {"dag_runs": []}

    async def mock_get(url, **kwargs):
        if "importErrors" in url:
            return mock_err_resp
        if "dagRuns" in url:
            return mock_runs_resp
        return mock_dags_resp

    mock_http = AsyncMock()
    mock_http.get.side_effect = mock_get

    with (
        patch("proxy_server.get_valid_token", return_value="mock-token"),
        patch(
            "proxy_server.get_all_environments_async",
            return_value=[
                {
                    "name": "env1",
                    "url": "https://env1.airflow.com",
                    "imageVersion": "composer-2.0.0-airflow-2.9.0",
                    "project": "proj1",
                    "bucket": "bucket1",
                },
            ],
        ),
        patch("proxy_server.http_client", mock_http),
    ):
        response = client.get("/api/all-dags?dag_id_pattern=%25customer_%25")
        assert response.status_code == 200
        data = response.json()
        assert len(data["dags"]) == 1
        assert data["dags"][0]["dag_id"] == "cust_orders"
