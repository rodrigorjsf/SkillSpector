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

"""``find_chains_missing_setters`` asks about several spellings, not one.

The Analyzer's own tests already cover what each Rule reports. What they cannot
cover is the call that *looks* right and silently answers a different question:
a ``str`` satisfies ``Sequence[str]`` as a sequence of its own characters, so
one spelling passed where a sequence belongs looks for six setters named ``f``,
``i``, ``l`` ... and reports every chain. That is exactly the defect issue #82
fixed, and nothing in this repo type-checks the call.
"""

from __future__ import annotations

import pytest

from skillspector.langchain4j import tool_surface

SCOPED_AND_UNSCOPED = """class Wiring {
    ToolProvider scoped(McpClient client) {
        return McpToolProvider.builder()
                .mcpClients(client)
                .filter((mcpClient, tool) -> tool.name().startsWith("inventory_"))
                .build();
    }

    ToolProvider unscoped(McpClient client) {
        return McpToolProvider.builder()
                .mcpClients(client)
                .build();
    }
}
"""


class TestOneSpellingIsNotASequenceOfThem:
    def test_a_bare_string_is_refused(self) -> None:
        with pytest.raises(TypeError, match="not one spelling"):
            tool_surface.find_chains_missing_setters(
                SCOPED_AND_UNSCOPED, "McpToolProvider", "filter"
            )

    def test_the_same_spelling_in_a_sequence_reports_only_the_unscoped_chain(self) -> None:
        # The control. Without it the refusal above would also pass if the
        # function refused everything.
        missing = tool_surface.find_chains_missing_setters(
            SCOPED_AND_UNSCOPED, "McpToolProvider", ("filter",)
        )

        assert [chain.line for chain in missing] == [10]
