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

"""Re-measure what a Framework vocabulary claims, by reading published releases.

Both inventories -- :mod:`skillspector.langchain4j.vocabulary` and
:mod:`skillspector.deepagents.vocabulary` -- carry a stability claim: the
spellings SkillSpector's Rules match on were observed across a range of upstream
releases. A claim like that decays with every release nobody has checked, and the
decay is silent: a renamed identifier stops a Rule matching, the Scan still
succeeds, the Analyzer still reports ``completed``, and the report reads as clean.

This package is what re-measures it. It downloads every published release in
scope straight from the index that serves them, reads the distributions rather
than the documentation, and reports for each inventoried spelling the releases it
was observed in.

The procedure it belongs to -- what to run, what it reads, what output
constitutes the new claim, and the trigger that obliges someone to re-run it --
is ``docs/VOCABULARY_REMEASUREMENT.md``.

Two properties are deliberate.

**The spellings are imported, never written here.** Both inventories are guarded
by a test that fails the build when a spelling is written inline anywhere in
``src/skillspector``; a sweep tool that hardcoded them would be a second
inventory drifting away from the one it measures, outside the guard's reach. What
this package holds instead is a *role* per inventoried constant -- keyed by the
constant's name, never by its value -- because presence alone is not a
measurement for spellings such as ``skills`` or ``mode`` that are also ordinary
English words.

**Standard library only, and nothing here runs in ``make test``.** The root
``pyproject.toml`` sets ``testpaths = ["tests"]``, so this package stays out of
the default suite: it is network-dependent by nature, and a sweep is a
maintainer's deliberate act rather than a check on every commit.
"""
