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

"""``python -m contrib.vocabulary_sweep <framework>`` -- re-measure one vocabulary.

Both sweeps read a public package index over the network and nothing else. The
procedure they belong to, including what to do with the output, is
``docs/VOCABULARY_REMEASUREMENT.md``.

**Exit code 1 means the sweep found something a maintainer must settle** -- a
spelling removed after appearing, or one never published in the role the Rules
read it in. Both mean the inventory and the published releases disagree, and
neither is a line to skim past on the way to the range.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from contrib.vocabulary_sweep import maven_sweep, pypi_sweep, report

_SWEEPS: dict[str, Callable[[], dict[str, dict[str, bool]]]] = {
    "deepagents": pypi_sweep.sweep,
    "langchain4j": maven_sweep.sweep,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m contrib.vocabulary_sweep")
    parser.add_argument("framework", choices=sorted(_SWEEPS))
    parsed = parser.parse_args(argv)
    swept = _SWEEPS[parsed.framework]()
    print(report.render(swept, framework=parsed.framework))
    return 1 if report.blocking(report.histories(swept)) else 0


if __name__ == "__main__":
    sys.exit(main())
