from unittest.mock import MagicMock

from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.service import GCPComposerService


def test_gcp_composer_service_construction():
    service: GCPComposerService = GCPComposerService("projectid", "location", "name")
    assert service.name == f"projects/projectid/locations/location/environments/name"


def test_gcp_composer_service_fetch_env():
    service: GCPComposerService = GCPComposerService("projectid", "location", "name")
    service.fetch_env = MagicMock(
        return_value=service_v1.types.Environment(
            {"name": "projects/projectid/locations/location/environments/name"}
        )
    )
    env: service_v1.types.Environment = service.fetch_env()
    assert env.name == f"projects/projectid/locations/location/environments/name"
