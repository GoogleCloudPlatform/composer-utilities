# Copyright 2022 Google LLC
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

import synthtool as s
import synthtool.gcp as gcp
from synthtool.languages import python

# ----------------------------------------------------------------------------
# Copy the generated client from the owl-bot staging directory
# ----------------------------------------------------------------------------

default_version = "v1"

for library in s.get_staging_dirs(default_version):
    s.move(library)
s.remove_staging_dirs()

# ----------------------------------------------------------------------------
# Add templated files
# ----------------------------------------------------------------------------

templated_files = gcp.CommonTemplates().py_library(
    microgenerator=True,
    versions=gcp.common.detect_versions(path="./google", default_first=True),
)
# skip setup.py and setup.cfg - those are in each utility's directory
# skip kokoro testing configs as of now we are not using kokoro for tests
# skip readme generation - our readmes are manual
# skip testing directory
# skip codeowners - ours is nonstandard
# skip noxfiles for subdirectories
s.move(
    templated_files,
    excludes=[
        "noxfile.py",
        "CONTRIBUTING.rst",
        "setup.py",
        "README.rst",
        "noxfile.py.j2",
        "setup.cfg",
        ".kokoro/samples/*",
        ".kokoro/presubmit/*",
        ".kokoro/docs/*",
        ".kokoro/continuous/*",
        ".kokoro/docker/docs/*",
        ".kokoro/test-samples*",
        "docs/*",
        "testing/*",
        "scripts/readme-gen/*",
        ".github/CODEOWNERS"
    ],
)
s.replace(
    "renovate.json",
    '"fileMatch": ["requirements-test.txt", "samples/[\\S/]*constraints.txt", "samples/[\\S/]*constraints-test.txt"]',
    '"fileMatch": ["requirements-test.txt"]',
)
python.py_samples(skip_readmes=True)

# ----------------------------------------------------------------------------
# Run blacken session
# ----------------------------------------------------------------------------

# s.shell.run(["nox", "-s", "blacken"], hide_output=False)
