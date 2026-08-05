# SPDX-FileCopyrightText: Copyright (c) 2026 SkillSpector-Polyglot contributors
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

"""Every runtime dependency the distribution declares is named in the notices.

``THIRD_PARTY_NOTICES.md`` is hand-maintained and read by nothing else, so a
dependency added to ``pyproject.toml`` without its entry used to be caught by
nobody -- see issue #102, which is the second time the file drifted.

The comparison is by **set membership** on normalised names, not by substring:
``tree-sitter`` is a substring of ``tree-sitter-java``, so a containment check
still passes after the ``tree-sitter`` entry is deleted.

Scope is ``project.dependencies`` only. ``project.optional-dependencies`` --
``mcp`` is redistributed, ``dev`` is not -- has never been audited and is
tracked as issue #109; covering it here would fail on day one and silently
widen this check's subject.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_NOTICES = _REPO_ROOT / "THIRD_PARTY_NOTICES.md"


def _normalise(name: str) -> str:
    """PEP 503 name normalisation: ``PyYAML`` and ``pyyaml`` are one package."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared_runtime_dependencies() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    requirements = data["project"]["dependencies"]
    # Strip the version specifier and any extras: ``langgraph-cli[inmem]>=0.4``.
    return {_normalise(re.split(r"[><=!~\[; ]", req, maxsplit=1)[0]) for req in requirements}


def _documented_dependencies() -> set[str]:
    lines = _NOTICES.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Runtime Dependencies")
    # The list ends at the next top-level section (``## License Texts``).
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return {
        _normalise(line.removeprefix("### ").strip())
        for line in lines[start:end]
        if line.startswith("### ")
    }


def test_every_runtime_dependency_has_a_notices_entry() -> None:
    missing = _declared_runtime_dependencies() - _documented_dependencies()
    assert not missing, (
        f"pyproject.toml declares {sorted(missing)} as runtime dependencies with no "
        "entry in THIRD_PARTY_NOTICES.md. Read the license and copyright line from the "
        "installed dist-info, not from memory."
    )


def test_no_notices_entry_outlives_its_dependency() -> None:
    stale = _documented_dependencies() - _declared_runtime_dependencies()
    assert not stale, (
        f"THIRD_PARTY_NOTICES.md documents {sorted(stale)}, which pyproject.toml no "
        "longer declares as a runtime dependency."
    )
