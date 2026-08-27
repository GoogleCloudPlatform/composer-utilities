#!/usr/bin/env python3
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

"""
Interactive, zero-dependency colored test dashboard for Airflow Plugin Operators.

Runs and formats unit test suites across platform and data engineering repositories.
"""

import argparse
import os
import sys
import time
import unittest

# Prevent bytecode generation when running test suite
sys.dont_write_bytecode = True

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"


def colorize(text: str, color_code: str, enable: bool = True) -> str:
    """Applies ANSI color formatting if enabled."""
    if not enable or not sys.stdout.isatty():
        return text
    return f"{color_code}{text}{RESET}"


class DashboardTestResult(unittest.TestResult):
    """Custom test result collector capturing test run metrics for the dashboard."""

    def __init__(self, suite_name: str, use_color: bool = True):
        super().__init__()
        self.suite_name = suite_name
        self.use_color = use_color
        self.test_records = []
        self.start_time = None
        self.end_time = None
        self._current_test_start = None

    def startTest(self, test):
        super().startTest(test)
        self._current_test_start = time.perf_counter()

    def addSuccess(self, test):
        super().addSuccess(test)
        elapsed = time.perf_counter() - self._current_test_start
        test_id = test.id().split(".")[-1]
        doc = test.shortDescription() or test_id
        self.test_records.append((test_id, doc, "PASS", elapsed, None))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        elapsed = time.perf_counter() - self._current_test_start
        test_id = test.id().split(".")[-1]
        doc = test.shortDescription() or test_id
        self.test_records.append(
            (test_id, doc, "FAIL", elapsed, self._exc_info_to_string(err, test))
        )

    def addError(self, test, err):
        super().addError(test, err)
        elapsed = time.perf_counter() - self._current_test_start
        test_id = test.id().split(".")[-1]
        doc = test.shortDescription() or test_id
        self.test_records.append(
            (test_id, doc, "ERROR", elapsed, self._exc_info_to_string(err, test))
        )


def run_suite_category(
    name: str,
    icon: str,
    loader: unittest.TestLoader,
    start_dir: str,
    pattern: str = "test_*.py",
    top_level_dir: str | None = None,
    use_color: bool = True,
):
    """Discovers and executes a specific test suite category."""
    suite = loader.discover(
        start_dir=start_dir, pattern=pattern, top_level_dir=top_level_dir or start_dir
    )
    result = DashboardTestResult(name, use_color=use_color)
    result.start_time = time.perf_counter()
    suite.run(result)
    result.end_time = time.perf_counter()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Airflow Governance Workshop Test Dashboard"
    )
    parser.add_argument(
        "--scope",
        choices=["all", "platform", "data"],
        default="all",
        help="Scope of tests to execute",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display individual test method names",
    )
    parser.add_argument(
        "-b",
        "--show-banners",
        action="store_true",
        help="Display actionable error box banners during tests",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    args = parser.parse_args()

    use_color = not args.no_color and sys.stdout.isatty()

    if args.show_banners:
        os.environ["SHOW_BANNER"] = "1"

    base_dir = os.path.dirname(os.path.abspath(__file__))
    platform_dir = os.path.join(base_dir, "platform_team_repo")
    data_dir = os.path.join(base_dir, "data_team_repo")
    plugins_dir = os.path.join(platform_dir, "plugins")

    # Set up PYTHONPATH for zero-install linking
    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)
    if platform_dir not in sys.path:
        sys.path.insert(0, platform_dir)
    if data_dir not in sys.path:
        sys.path.insert(0, data_dir)

    print()
    print(colorize("=" * 82, CYAN + BOLD, use_color))
    print(
        colorize(
            "🧪  APACHE AIRFLOW ENTERPRISE GOVERNANCE TEST DASHBOARD",
            WHITE + BOLD,
            use_color,
        )
    )
    print(colorize("=" * 82, CYAN + BOLD, use_color))
    print(
        colorize(
            f"📍 Execution Mode: Scope={args.scope.upper()} | Zero Cloud Latency Mode (< 0.01s)",
            DIM,
            use_color,
        )
    )
    print()

    total_start = time.perf_counter()
    suites_results = []
    loader = unittest.TestLoader()

    # 1. Platform Suite
    if args.scope in ("all", "platform"):
        print(
            colorize(
                "🏛️  PLATFORM ENGINEERING DOMAIN (platform_team_repo):",
                BLUE + BOLD,
                use_color,
            )
        )
        categories = [
            (
                "Cluster Sizing Tiers",
                "📐",
                os.path.join(platform_dir, "tests"),
                "test_cluster_tiers.py",
            ),
            (
                "Guardrails & Policies",
                "🛡️",
                os.path.join(platform_dir, "tests"),
                "test_guardrail_enforcement.py",
            ),
            (
                "Operator Lifecycle",
                "⚡",
                os.path.join(platform_dir, "tests"),
                "test_secure_dataproc_operator.py",
            ),
        ]
        if args.scope == "platform":
            categories.append(
                (
                    "DAG Compliance & Interception",
                    "🔒",
                    os.path.join(platform_dir, "tests"),
                    "test_dag_compliance.py",
                )
            )

        for title, icon, path, pattern in categories:
            res = run_suite_category(
                title, icon, loader, path, pattern, use_color=use_color
            )
            suites_results.append(res)
            duration = res.end_time - res.start_time
            passed = len(res.test_records) - len(res.failures) - len(res.errors)
            total = len(res.test_records)
            status_text = (
                colorize("PASS", GREEN + BOLD, use_color)
                if not (res.failures or res.errors)
                else colorize("FAIL", RED + BOLD, use_color)
            )
            icon_status = (
                colorize("✔", GREEN, use_color)
                if not (res.failures or res.errors)
                else colorize("✖", RED, use_color)
            )
            print(
                f"   {icon_status}  {title:<28} ({passed}/{total} tests)    [{duration:.4f}s]  --> {status_text}"
            )

            if args.verbose:
                for tid, doc, st, el, _ in res.test_records:
                    st_col = (
                        colorize("✔", GREEN, use_color)
                        if st == "PASS"
                        else colorize("✖", RED, use_color)
                    )
                    print(f"      {st_col} {tid:<52} [{el:.4f}s]")
        print()

    # 2. Data Team Suite
    if args.scope in ("all", "data"):
        print(
            colorize(
                "💼  DATA ENGINEERING PIPELINES (data_team_repo):",
                MAGENTA + BOLD,
                use_color,
            )
        )
        data_categories = [
            (
                "DAG Parsing & Integrity",
                "📄",
                os.path.join(data_dir, "tests"),
                "test_dag_integrity.py",
            ),
            (
                "Platform Policy Compliance",
                "🔒",
                os.path.join(platform_dir, "tests"),
                "test_dag_compliance.py",
            ),
        ]
        for title, icon, path, pattern in data_categories:
            res = run_suite_category(
                title, icon, loader, path, pattern, use_color=use_color
            )
            suites_results.append(res)
            duration = res.end_time - res.start_time
            passed = len(res.test_records) - len(res.failures) - len(res.errors)
            total = len(res.test_records)
            status_text = (
                colorize("PASS", GREEN + BOLD, use_color)
                if not (res.failures or res.errors)
                else colorize("FAIL", RED + BOLD, use_color)
            )
            icon_status = (
                colorize("✔", GREEN, use_color)
                if not (res.failures or res.errors)
                else colorize("✖", RED, use_color)
            )
            print(
                f"   {icon_status}  {title:<28} ({passed}/{total} tests)    [{duration:.4f}s]  --> {status_text}"
            )

            if args.verbose:
                for tid, doc, st, el, _ in res.test_records:
                    st_col = (
                        colorize("✔", GREEN, use_color)
                        if st == "PASS"
                        else colorize("✖", RED, use_color)
                    )
                    print(f"      {st_col} {tid:<52} [{el:.4f}s]")
        print()

    total_time = time.perf_counter() - total_start
    all_tests = sum(len(r.test_records) for r in suites_results)
    all_fails = sum(len(r.failures) for r in suites_results)
    all_errors = sum(len(r.errors) for r in suites_results)

    print(colorize("-" * 82, DIM, use_color))
    if all_fails == 0 and all_errors == 0:
        msg = f"🎉  ALL {all_tests} GOVERNANCE & INTEGRITY TESTS PASSED (100% Success in {total_time:.4f}s)"
        print(colorize(msg, GREEN + BOLD, use_color))
    else:
        msg = f"⚠️  {all_fails + all_errors} OUT OF {all_tests} TESTS FAILED (Elapsed: {total_time:.4f}s)"
        print(colorize(msg, RED + BOLD, use_color))

        # Print failures in detail
        for r in suites_results:
            for t, err in r.failures + r.errors:
                print(
                    colorize(f"\n[FAILURE DETAILS - {t.id()}]:", RED + BOLD, use_color)
                )
                print(err)

    print(colorize("=" * 82, CYAN + BOLD, use_color))
    print()

    return 0 if (all_fails == 0 and all_errors == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
