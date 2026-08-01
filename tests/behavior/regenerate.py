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

"""Rewrite the committed Behavior Snapshots -- ``make snapshots``.

Regeneration is always deliberate and always its own commit. It lives here, in a
separate entry point, rather than as a branch inside the test: no environment
variable and no test run may rewrite a golden file.

``--emit NAME`` prints one projection instead of writing it, and ``--emit-all``
prints the whole corpus, both together with the model configuration the run
resolved. The determinism tests use them to compare projections produced by
*separate processes*, which is the only way to see ordering derived from hash
seeds or from the import-time provider resolution.

``--emit-all`` exists so that widening the corpus does not multiply interpreter
spawns: the whole corpus is compared across hash seeds and providers by three
child processes in total, not three per fixture.
"""

from __future__ import annotations

import argparse
import json
import sys

from tests.behavior.projection import (
    CORPUS,
    SNAPSHOT_DIR,
    scan,
    serialize,
    snapshot_path,
)


def _emit(names: list[str]) -> int:
    from skillspector.constants import build_model_config

    payload = {
        "projections": {name: scan(CORPUS[name]) for name in names},
        "model_config": build_model_config(),
    }
    sys.stdout.write(json.dumps(payload))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--emit",
        metavar="NAME",
        help="print one projection as JSON on stdout instead of writing snapshots",
    )
    parser.add_argument(
        "--emit-all",
        action="store_true",
        help="print every corpus projection as JSON on stdout instead of writing snapshots",
    )
    args = parser.parse_args(argv)

    if args.emit_all:
        return _emit(sorted(CORPUS))
    if args.emit:
        return _emit([args.emit])

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for name, skill_path in sorted(CORPUS.items()):
        target = snapshot_path(name)
        # The corpus mirrors the fixture layout, so a name may nest.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialize(scan(skill_path)), encoding="utf-8")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
