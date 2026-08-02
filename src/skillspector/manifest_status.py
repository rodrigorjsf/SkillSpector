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

"""Why a Scan's Manifest looks the way it does.

An empty ``manifest`` dict is an overloaded sentinel: the Skill declared
nothing, its declaration block could not be turned into a mapping, the file
could not be read, or -- the case issue #11 tracks -- there was no Skill in the
scanned directory at all. All four produce a byte-identical ``{}`` downstream,
so a directory that is not a Skill returns a scored verdict indistinguishable
from a real Skill that declares nothing.

``ManifestStatus`` names the distinction. It travels beside ``manifest`` rather
than inside it: every reader of ``manifest`` keeps the value and the type it
reads today.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class ManifestStatus(StrEnum):
    """Why the Manifest of a Scan holds what it holds.

    Every path out of the Manifest parser maps to exactly one member; none may
    fall through to a default.
    """

    PRESENT = "present"
    EMPTY = "empty"
    UNPARSEABLE = "unparseable"
    UNREADABLE = "unreadable"
    ABSENT = "absent"


MANIFEST_STATUS_MESSAGES: Final[dict[ManifestStatus, str]] = {
    ManifestStatus.PRESENT: "A Manifest was declared and parsed.",
    ManifestStatus.EMPTY: "The Skill declares a Manifest that carries no recognized field.",
    ManifestStatus.UNPARSEABLE: (
        "The Skill declares a Manifest block that could not be read as a mapping."
    ),
    ManifestStatus.UNREADABLE: "The file declaring the Manifest could not be read.",
    ManifestStatus.ABSENT: (
        "No SKILL.md was found: the scanned directory declares no Agent Skills Skill."
    ),
}
