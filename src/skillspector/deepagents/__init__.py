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

"""Reading the host code of a Deep Agents application.

The security-relevant configuration of a Deep Agents Skill lives in the
``create_deep_agent(...)`` call rather than in the Skill directory: which sources
the agent was given, whether it may write to them, whether a human is asked
first. This package is what makes that Python readable to the
``framework_deepagents`` Analyzer.

``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md`` decided the
package exists at all. Not for size -- there is no native dependency here to
isolate, the way ``langchain4j/java_parser.py`` isolates tree-sitter -- but
because the vocabulary enforcement test needs a boundary to sweep, and because
folding the spellings into :mod:`skillspector.framework` would make detection and
the Rules share one inventory, so a single upstream rename would move both at
once.

Six modules today, and the resolver is deliberately alone on its side of the
line: the three judging modules read what it produced and it decides nothing
about what a refusal means. Keeping the judgement out of the resolver is what
lets it refuse to guess in one place.

* :mod:`skillspector.deepagents.vocabulary` is every upstream spelling this
  package matches on, and nothing else. Parser-free.
* :mod:`skillspector.deepagents.signals` answers which Components of a Scan the
  Analyzer opens. It is the one Applicability predicate ADR 0006 requires.
  Parser-free.
* :mod:`skillspector.deepagents.host_config` reads ``create_deep_agent(...)`` and
  resolves a literal and a same-module constant, and says so rather than
  guessing when it cannot. ADR 0008 §1 is why the boundary sits exactly there.
* :mod:`skillspector.deepagents.writability` decides, per resolved Skill source
  path, whether anything denies the agent write access to it -- walking the
  permission rules in the order they were written, because that order is
  semantics upstream. It judges nothing wherever the resolver reported a
  boundary, so
  the two Rules partition a call rather than overlapping on it.
* :mod:`skillspector.deepagents.skill_sources` maps each configured Skill source
  path onto the Components of this Scan -- through the backend root, because that
  is what the paths are relative to -- and confirms a name collision across two
  of them by reading the manifests it mapped to. It is the only module here that
  reasons across sources, and the only one that reads something other than
  Python.
* :mod:`skillspector.deepagents.subagents` says which of a call's custom
  subagents were defined without Skills of their own. It is the smallest verdict
  here and the only one that decides nothing about a path -- upstream states that
  a custom subagent inherits none of the main agent's Skills, so the question is
  answered inside one definition.

The Analyzer reaches for ``ast`` from the standard library, so unlike the
LangChain4j package there is no import ordering to preserve here: nothing this
package imports can be missing from an installation.
"""
