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

"""What one published release was observed to write, and how a release is fetched.

Shared by both sweeps, because "a spelling occurs in this release in this role"
is one question whatever the index served. The two readers differ -- one parses
Python syntax trees, the other class files -- but what they *produce* does not,
and two copies of the answer would be two chances to disagree about what an
observation means.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

from contrib.vocabulary_sweep.roles import Role


@dataclass(frozen=True)
class Occurrences:
    """Every spelling one release writes, grouped by the role it writes it in."""

    by_role: Mapping[Role, frozenset[str]]

    def carries(self, spelling: str, role: Role) -> bool:
        """Whether the release writes *spelling* in *role*.

        A role the reader collects nothing for answers ``False`` rather than
        raising: ``DISTRIBUTION`` is observed from the index and ``NOT_MEASURED``
        from nowhere, and neither is a question about an archive's contents.
        """
        return spelling in self.by_role.get(role, frozenset())


def fetch(url: str) -> bytes:
    """One archive or index document, over HTTPS, from a fixed public index."""
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 -- https, fixed index
        return bytes(response.read())
