from google.cloud.orchestration.airflow import service_v1

from cloudcomposerdiff.lib.difference import EnvironmentAttributeDiff
from cloudcomposerdiff.lib.service import GCPComposerService
from cloudcomposerdiff.lib.strategies.diffenvimage import DiffEnvImage


def test_diff_env_image_strategy():
    env1: service_v1.types.Environment = service_v1.types.Environment(
        {
            "config": service_v1.types.EnvironmentConfig(
                {
                    "software_config": service_v1.types.SoftwareConfig(
                        {"image_version": "123"}
                    )
                }
            )
        }
    )
    env2: service_v1.types.Environment = service_v1.types.Environment(
        {
            "config": service_v1.types.EnvironmentConfig(
                {
                    "software_config": service_v1.types.SoftwareConfig(
                        {"image_version": "456"}
                    )
                }
            )
        }
    )
    detector: DiffEnvImage = DiffEnvImage()
    diff: EnvironmentAttributeDiff = detector.detect_difference(env1, env2)
    assert diff[0].category_of_diff == "composer_image_version"
