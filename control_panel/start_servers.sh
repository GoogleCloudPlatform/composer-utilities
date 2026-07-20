#!/bin/bash

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
#

set -m # Enable job control so background processes get their own process group
if [ -z "${COMPOSER_PROJECTS}" ]; then
    export COMPOSER_PROJECTS="YOUR_PROJECT_ID_A,YOUR_PROJECT_ID_B,YOUR_PROJECT_ID_C"
fi

if [ -z "${COMPOSER_LOCATIONS}" ]; then
    export COMPOSER_LOCATIONS="us-central1,us-east4"
fi

echo "Starting Proxy Python server..."
uv run proxy_server.py &
PROXY_PID=$!

echo "Starting NPM server..."
npm start &
NPM_PID=$!

# Trap for cleanup: kill the entire process groups to prevent ghost processes
trap "echo 'Stopping servers...'; kill -TERM -$NPM_PID -$PROXY_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM EXIT

echo "Both servers are running. Press Ctrl+C to stop."
wait
