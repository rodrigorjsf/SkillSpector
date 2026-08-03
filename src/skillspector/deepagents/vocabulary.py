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

"""Every Deep Agents spelling SkillSpector's Rules match on, and nothing else.

The reason is the one ``docs/adr/0005-langchain4j-upstream-vocabulary.md`` gives
for the Java track and ``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md``
copies for this one: when upstream renames a keyword argument or a type, a Rule
that matches it stops producing Findings and **nothing says so**. The Scan still
succeeds, the Analyzer still reports itself as having run, and the report reads
as clean. So the spellings live in one file, and
``tests/unit/test_deepagents_vocabulary.py`` fails the build when one is written
inline anywhere else in the source tree.

What ADR 0005's second half is *not* copied: it measured the stability claim
rather than asserting it -- seventeen Maven releases swept, recorded in
``OBSERVED_VERSION_RANGE``. No equivalent measurement exists for Deep Agents yet.
Producing it, and the re-measurement procedure for both Frameworks, is issue #75.
Until that lands this module carries no version range, deliberately, rather than
carrying an unmeasured one.

Two entries today, and **nothing imports either of them yet**: the Analyzer that
owns them carries no Rules. Issue #70 placed the module in that slice all the
same, so the guard is in force from the first Rule rather than retrofitted
around five, and ADR 0008 makes the module a consequence of the decisions rather
than of the Rules. An empty inventory was the alternative, and it would have made
the guard vacuous -- every assertion passing over nothing. So the two below are
seeded: the spellings that *define* the Framework, the constructor its whole
surface is configured through and the distribution that provides it, which every
later Ticket's Rule starts from. Issues #71 through #74 add the rest of the
inventory ADR 0008 enumerates; none of them writes a spelling anywhere else.

**These are a second copy of what :mod:`skillspector.framework` matches on for
detection, and that is deliberate.** ADR 0008 rejected sharing one inventory
between detection and the Rules outright: they answer different questions -- "is
this tree Deep Agents at all" versus "what does this call configure" -- and an
upstream rename that legitimately moves one of them should not silently move the
other. The guard therefore sweeps the whole source tree *except* ``framework.py``.

Deliberately import-free, so nothing here can fail to load.

Provenance
----------

Captured from ``docs/references/langchain-deepagents-skills.md`` (upstream
<https://docs.langchain.com/labs/deep-agents/skills>).
"""

from __future__ import annotations

from typing import Final

# -- The Framework itself ---------------------------------------------------- #

# The constructor every host-side setting is passed to. Upstream names it in the
# first line of every example on the captured page.
CREATE_DEEP_AGENT: Final[str] = "create_deep_agent"

# The distribution that provides it, as a Python requirement file spells it.
DISTRIBUTION: Final[str] = "deepagents"
