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

"""Unit tests for dag_parsing_profiler.linter_core."""

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def _build_optional_dep_stubs():
    """Creates lightweight module stubs if optional dependencies are absent."""
    stubs = {}
    if "airflow" not in sys.modules:
        airflow_mod = types.ModuleType("airflow")
        airflow_models = types.ModuleType("airflow.models")
        airflow_dag = types.ModuleType("airflow.models.dag")

        class _StubDAG:
            pass

        airflow_dag.DAG = _StubDAG
        airflow_models.dag = airflow_dag
        airflow_mod.models = airflow_models
        stubs.update(
            {
                "airflow": airflow_mod,
                "airflow.models": airflow_models,
                "airflow.models.dag": airflow_dag,
            }
        )

    if "google.cloud.storage" not in sys.modules:
        google_mod = sys.modules.get("google") or types.ModuleType("google")
        cloud_mod = sys.modules.get("google.cloud") or types.ModuleType("google.cloud")
        storage_mod = types.ModuleType("google.cloud.storage")

        class _StubBucket:
            pass

        class _StubClient:
            pass

        storage_mod.Bucket = _StubBucket
        storage_mod.Client = _StubClient
        cloud_mod.storage = storage_mod
        google_mod.cloud = cloud_mod
        stubs.update(
            {
                "google": google_mod,
                "google.cloud": cloud_mod,
                "google.cloud.storage": storage_mod,
            }
        )
    return stubs


_OPTIONAL_DEP_STUBS = _build_optional_dep_stubs()


def _load_linter_core():
    """Loads linter_core.py with lightweight stubs if optional deps are absent."""
    module_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "linter_core.py")
    )
    spec = importlib.util.spec_from_file_location("linter_core", module_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, _OPTIONAL_DEP_STUBS):
        spec.loader.exec_module(module)
    return module


linter_core = _load_linter_core()


class FakeBlob:
    """Minimal GCS blob stand-in that writes content to the target filename."""

    def __init__(self, name: str, content: bytes = b"# test\n"):
        self.name = name
        self.content = content
        self.downloaded_to: list[str] = []

    def download_to_filename(self, filename: str) -> None:
        self.downloaded_to.append(filename)
        with open(filename, "wb") as f:
            f.write(self.content)


class FakeBucket:
    """Minimal GCS bucket stand-in returning blobs matching a prefix."""

    def __init__(self, blobs: list[FakeBlob]):
        self._blobs = blobs

    def list_blobs(self, prefix: str = ""):
        return [b for b in self._blobs if b.name.startswith(prefix)]


class TestDownloadFolder(unittest.TestCase):
    """Tests for download_folder() path containment and normal downloads."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_work_dir = self.temp_dir.name
        self.config = {"BASE_WORK_DIR": self.base_work_dir}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_downloads_benign_flat_and_nested_files(self):
        blobs = [
            FakeBlob("dags/"),
            FakeBlob("dags/good.py", b"x = 1\n"),
            FakeBlob("dags/subdir/"),
            FakeBlob("dags/subdir/nested.py", b"y = 2\n"),
            FakeBlob("dags/report..v2.py", b"z = 3\n"),
            FakeBlob("dags/.hidden.py", b"h = 4\n"),
        ]
        bucket = FakeBucket(blobs)
        report_lines: list[str] = []

        count = linter_core.download_folder(
            bucket, "dags/", "dags", self.config, report_lines
        )

        self.assertEqual(count, 4)
        self.assertTrue(os.path.isfile(os.path.join(self.base_work_dir, "dags", "good.py")))
        self.assertTrue(
            os.path.isfile(os.path.join(self.base_work_dir, "dags", "subdir", "nested.py"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(self.base_work_dir, "dags", "report..v2.py"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(self.base_work_dir, "dags", ".hidden.py"))
        )
        self.assertFalse(any("SKIPPED" in line for line in report_lines))

    def test_blocks_data_traversal_into_dags(self):
        evil_blob = FakeBlob("data/../dags/evil.py", b"raise RuntimeError('pwned')\n")
        bucket = FakeBucket([evil_blob])
        report_lines: list[str] = []

        count = linter_core.download_folder(
            bucket, "data/", "data", self.config, report_lines
        )

        self.assertEqual(count, 0)
        self.assertEqual(evil_blob.downloaded_to, [])
        self.assertFalse(
            os.path.exists(os.path.join(self.base_work_dir, "dags", "evil.py"))
        )
        self.assertIn("SKIPPED (path escape): data/../dags/evil.py", report_lines)

    def test_blocks_multiple_traversal_variants(self):
        malicious_names = [
            "data/../dags/evil.py",
            "data/a/../../dags/evil.py",
            "data/../../outside.py",
            "data/../data_evil/evil.py",
            "data/sub/../other.py",
            "data/..",
            "data/.",
            "data/sub/.",
        ]
        blobs = [FakeBlob(name, b"evil") for name in malicious_names]
        bucket = FakeBucket(blobs)
        report_lines: list[str] = []

        count = linter_core.download_folder(
            bucket, "data/", "data", self.config, report_lines
        )

        self.assertEqual(count, 0)
        for blob in blobs:
            self.assertEqual(
                blob.downloaded_to, [], f"Expected {blob.name} to be skipped"
            )
            self.assertIn(f"SKIPPED (path escape): {blob.name}", report_lines)

    def test_blocks_prefix_without_trailing_slash_sibling_escape(self):
        good_blob = FakeBlob("data/ok.txt", b"ok")
        sibling_blob = FakeBlob("data_other/evil.py", b"evil")
        exact_blob = FakeBlob("data", b"exact")
        bucket = FakeBucket([good_blob, sibling_blob, exact_blob])
        report_lines: list[str] = []

        count = linter_core.download_folder(
            bucket, "data", "data", self.config, report_lines
        )

        self.assertEqual(count, 1)
        self.assertEqual(len(good_blob.downloaded_to), 1)
        self.assertEqual(sibling_blob.downloaded_to, [])
        self.assertEqual(exact_blob.downloaded_to, [])
        self.assertIn("SKIPPED (path escape): data_other/evil.py", report_lines)
        self.assertIn("SKIPPED (path escape): data", report_lines)

    def test_blocks_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            data_dir = os.path.join(self.base_work_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            os.symlink(outside_dir, os.path.join(data_dir, "link"))

            evil_blob = FakeBlob("data/link/escaped.py", b"evil")
            bucket = FakeBucket([evil_blob])
            report_lines: list[str] = []

            count = linter_core.download_folder(
                bucket, "data/", "data", self.config, report_lines
            )

            self.assertEqual(count, 0)
            self.assertEqual(evil_blob.downloaded_to, [])
            self.assertFalse(os.path.exists(os.path.join(outside_dir, "escaped.py")))
            self.assertIn("SKIPPED (path escape): data/link/escaped.py", report_lines)

    def test_data_traversal_payload_not_executed_by_main(self):
        marker_file = os.path.join(self.base_work_dir, "pwned_marker")
        evil_payload = (
            f"with open({marker_file!r}, 'w') as f:\n    f.write('executed')\n"
        ).encode()
        good_dag = b"from airflow.models.dag import DAG\nd = DAG()\n"

        bucket = FakeBucket(
            [
                FakeBlob("dags/good_dag.py", good_dag),
                FakeBlob("data/../dags/evil.py", evil_payload),
                FakeBlob("plugins/../dags/evil_plugin.py", evil_payload),
            ]
        )

        config = {
            "GCS_BUCKET": "test-bucket",
            "BASE_WORK_DIR": self.base_work_dir,
            "FETCH_EXTRAS": True,
            "PROFILE_SLOW": False,
            "PROFILE_SORT_KEY": "tottime",
            "PARSE_TIME_THRESHOLD_SECONDS": 5.0,
            "GCS_DAGS_SOURCE_FOLDER": "dags/",
            "GCS_PLUGINS_SOURCE_FOLDER": "plugins/",
            "GCS_DATA_SOURCE_FOLDER": "data/",
        }

        class _SerialPool:
            def __init__(self, processes=None):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def starmap(self, func, iterable):
                return [func(*args) for args in iterable]

        class _FakeClient:
            def bucket(self, name):
                return bucket

        printed: list[str] = []
        original_sys_path = list(sys.path)
        try:
            with (
                patch.dict(sys.modules, _OPTIONAL_DEP_STUBS),
                patch.object(linter_core.storage, "Client", return_value=_FakeClient()),
                patch.object(linter_core, "Pool", _SerialPool),
                patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(map(str, a)))),
            ):
                linter_core.main(json.dumps(config))
        finally:
            sys.path[:] = original_sys_path

        report = "\n".join(printed)
        self.assertFalse(os.path.exists(marker_file))
        self.assertFalse(
            os.path.exists(os.path.join(self.base_work_dir, "dags", "evil.py"))
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.base_work_dir, "dags", "evil_plugin.py"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.base_work_dir, "dags", "good_dag.py"))
        )
        self.assertIn("SKIPPED (path escape): data/../dags/evil.py", report)
        self.assertIn("SKIPPED (path escape): plugins/../dags/evil_plugin.py", report)
        self.assertIn("Status: SUCCESS", report)


if __name__ == "__main__":
    unittest.main()
