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

"""Reading the host code of a LangChain4j application.

The security-relevant configuration of a LangChain4j Skill lives in Java, not in
its ``SKILL.md``: which loader found the Skill, whether it runs in shell mode,
what its tools may do. This package is what makes that Java readable to the
``framework_langchain4j`` Analyzer.

The split across modules exists to keep the parser optional at the right moment:

* :mod:`skillspector.langchain4j.signals` needs no parser. It answers which files
  of a Scan are Java or JVM build files, and scans build files textually. The
  Analyzer imports it at module top and uses it to decide applicability *before*
  reaching for tree-sitter.
* :mod:`skillspector.langchain4j.java_parser` binds tree-sitter and nothing else.
* Rule modules such as :mod:`skillspector.langchain4j.shell_skills` import the
  parser and are therefore imported lazily, inside the Analyzer's node function.

This module imports none of them, so ``import skillspector.langchain4j`` never
pulls tree-sitter in on its own.
"""
