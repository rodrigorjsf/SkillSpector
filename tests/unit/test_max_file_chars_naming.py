# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The per-file analysis cap is named ``MAX_FILE_CHARS``, everywhere it is named.

The constant was renamed from ``MAX_FILE_BYTES`` when its meaning changed from
bytes to characters. The rename came with a guard -- ``test_skip_log_reports_char_metric``
in ``tests/nodes/analyzers/test_static_runner_filtering.py`` -- but that guard
reads one log message, so prose was free to keep the retired name. It did, in
``README.md`` and in ``input_handler.py``, for as long as it took someone to
audit the two against the source (issue #42).

The unit is the reason this is worth a test rather than a proofreading pass. A
character count and a byte count are the same number only for ASCII: 1 000 000
CJK characters occupy roughly 3 MB, so a reader told the cap is "1 MB" has been
told the wrong thing about which files a Scan reads, not merely the wrong name.

**Scope.** Tracked ``.md`` and ``.py`` files, which is where a Python constant
is named. A mention in a build file, a workflow or a notebook is not caught.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

_RETIRED_NAME = "MAX_FILE_BYTES"
_CURRENT_NAME = "MAX_FILE_CHARS"

_SEARCHED_SUFFIXES = (".md", ".py")

# The two files that may write the retired name, and why.
#
# ``test_static_runner_filtering.py`` holds the assertion that the skip log does
# *not* say it -- the guard the rename shipped with. This module names it to say
# it is retired. Every other occurrence is drift.
#
# ``TestScope`` asserts each of these still contains the name, so an exemption
# that has outlived its file fails the build rather than silently widening what
# the guard permits.
_EXEMPT: tuple[str, ...] = (
    "tests/nodes/analyzers/test_static_runner_filtering.py",
    "tests/unit/test_max_file_chars_naming.py",
)


def _tracked_files() -> list[str]:
    """Every tracked ``.md`` and ``.py`` path, relative to the repository root.

    Read from ``git ls-files`` rather than a filesystem walk so a generated
    report, a virtualenv or a local scratch file cannot fail an unrelated
    change. Paths come back with forward slashes on every platform, which is
    what ``_EXEMPT`` is written in.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        path
        for path in result.stdout.split("\0")
        if path.endswith(_SEARCHED_SUFFIXES) and path not in _EXEMPT
    ]


def naming_drift(paths: Iterable[str], root: Path = _REPO_ROOT) -> list[str]:
    """Every ``path:line`` under *root* that writes the retired constant name."""
    reported: list[str] = []
    for path in paths:
        try:
            content = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(content.splitlines(), start=1):
            if _RETIRED_NAME in line:
                reported.append(
                    f"{path}:{number} writes {_RETIRED_NAME}, a name that no longer exists. "
                    f"The per-file analysis cap is {_CURRENT_NAME} in "
                    "src/skillspector/nodes/analyzers/static_runner.py, and it counts "
                    "characters of decoded text rather than bytes on disk."
                )
    return reported


class TestScope:
    """The guard covers what it claims to, so a pass is not vacuous."""

    def test_the_searched_corpus_is_not_empty(self) -> None:
        # A `git ls-files` that returned nothing -- wrong cwd, no repository --
        # would make the assertion below pass while reading no file at all.
        assert len(_tracked_files()) > 100

    def test_the_current_name_is_present_in_the_corpus(self) -> None:
        # The positive control for the search itself: the same read that finds
        # no retired name does find the one that replaced it.
        found = [
            path
            for path in _tracked_files()
            if _CURRENT_NAME in (_REPO_ROOT / path).read_text(encoding="utf-8")
        ]
        assert len(found) >= 5, f"expected the live constant to be named widely, found {found}"

    @pytest.mark.parametrize("path", _EXEMPT)
    def test_every_exemption_still_writes_the_retired_name(self, path: str) -> None:
        content = (_REPO_ROOT / path).read_text(encoding="utf-8")
        assert _RETIRED_NAME in content, (
            f"{path} no longer writes {_RETIRED_NAME}, so its exemption permits drift it was "
            "never meant to cover -- drop the entry from _EXEMPT."
        )

    def test_a_file_writing_the_retired_name_is_reported(self, tmp_path: Path) -> None:
        drifted = tmp_path / "README.md"
        drifted.write_text(
            f"The per-file 1 MB analysis cap (`{_RETIRED_NAME}`) is downstream.\n",
            encoding="utf-8",
        )
        reported = naming_drift(["README.md"], root=tmp_path)
        assert len(reported) == 1
        assert "README.md:1" in reported[0]
        assert _CURRENT_NAME in reported[0]

    def test_a_file_writing_the_current_name_is_not_reported(self, tmp_path: Path) -> None:
        # The control for the control: the search matches the retired spelling,
        # not any mention of the cap.
        clean = tmp_path / "README.md"
        clean.write_text(f"The per-file analysis cap is `{_CURRENT_NAME}`.\n", encoding="utf-8")
        assert naming_drift(["README.md"], root=tmp_path) == []


class TestSingleName:
    """No tracked prose or source outside the two exemptions names the retired constant."""

    def test_the_retired_name_appears_nowhere(self) -> None:
        assert naming_drift(_tracked_files()) == []
