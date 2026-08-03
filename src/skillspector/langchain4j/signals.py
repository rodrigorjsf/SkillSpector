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

"""Which files of a Scan the LangChain4j Analyzer inspects, and cheap signals over them.

Deliberately parser-free. The Analyzer decides whether it is applicable at all
before importing tree-sitter, and that decision is made here -- so a Scan with
nothing applicable reports ``not_applicable`` without ever loading a parser, and
an installation missing one still declines quietly on every input the Analyzer
does not own.

The file predicates mirror ``skillspector.framework``'s rather than importing
them: detection asks "is this tree LangChain4j at all", this module asks "which
of its files do I open". The two questions drift apart as later Rules land, and
this repository merges upstream, so a private helper of a phase-1 module is the
wrong thing to couple to.

That decoupling is about the two *predicates*, not about the words they are
written in. Both modules read their LangChain4j spellings from
:mod:`skillspector.langchain4j.vocabulary`, because the spelling of an artifact
id is one fact rather than two, and a rename that reached only one of them would
leave the other matching nothing in silence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

# Its presence on the classpath is the capability: upstream documents shell
# execution as running "without any sandboxing, containerization, or privilege
# restriction". Imported rather than spelled here -- ``vocabulary`` is the
# single home for anything a LangChain4j release can rename.
from skillspector.langchain4j.vocabulary import SHELL_ARTIFACT_ID

JAVA_SUFFIX: Final[str] = ".java"

# Matched on basename at any depth: a multi-module Maven build declares its
# dependencies in a child module's ``pom.xml``, not only at the scan root.
_JVM_BUILD_FILES: Final[tuple[str, ...]] = ("pom.xml",)
_JVM_BUILD_PREFIX: Final[str] = "build.gradle"

# Comment syntaxes, keyed by the build file that can hold them. Applied per file
# kind rather than all at once: a ``//`` sweep over XML would blank the tail of
# any line carrying a URL, and an XML-comment sweep over Gradle would match
# nothing but cost a scan.
_XML_COMMENT: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->", re.DOTALL)
_GRADLE_BLOCK_COMMENT: Final[re.Pattern[str]] = re.compile(r"/\*.*?\*/", re.DOTALL)
_GRADLE_LINE_COMMENT: Final[re.Pattern[str]] = re.compile(r"//[^\n]*")
_NON_NEWLINE: Final[re.Pattern[str]] = re.compile(r"[^\n]")


def _basename(path: str) -> str:
    """Return the final segment of a component path.

    ``file_cache`` keys always use forward slashes -- ``build_context``
    normalizes them so they stay portable as dict keys and SARIF locations.
    """
    return path.rsplit("/", 1)[-1]


def is_java_source(path: str) -> bool:
    """Whether *path* names a Java compilation unit."""
    return path.endswith(JAVA_SUFFIX)


def is_jvm_build_file(path: str) -> bool:
    """Whether *path* names a Maven or Gradle build file."""
    name = _basename(path)
    return name in _JVM_BUILD_FILES or name.startswith(_JVM_BUILD_PREFIX)


def java_sources(file_cache: Mapping[str, str]) -> dict[str, str]:
    """The readable Java compilation units of a Scan, by path.

    Reads ``file_cache`` rather than ``components`` on purpose: a component
    listed but unreadable has no source to parse. The content is whatever
    ``build_context`` cached, which is the full file -- the static runner's
    per-file character cap lives in the static runner and is not inherited here.
    """
    return {path: content for path, content in file_cache.items() if is_java_source(path)}


def jvm_build_files(file_cache: Mapping[str, str]) -> dict[str, str]:
    """The readable Maven and Gradle build files of a Scan, by path."""
    return {path: content for path, content in file_cache.items() if is_jvm_build_file(path)}


def applicable_files(file_cache: Mapping[str, str]) -> dict[str, str]:
    """The Components the LangChain4j Analyzer opens, by path.

    Applicability is this one predicate: a Java compilation unit or a JVM build
    file, whether or not the build file declares the shell module. The Analyzer
    gates on this result being empty and derives its planned work from the same
    result, so what it opens and what it reports opening cannot disagree -- the
    drift ``docs/adr/0006-langchain4j-applicability-is-what-it-opens.md``
    records, where a build file with no shell declaration was opened by the
    accounting and closed out by the gate.

    Named for the word the Ledger already uses: an Analyzer with none of these
    reports ``no_applicable_files``, so the code and the report describe
    applicability in one vocabulary rather than two.
    """
    return {
        path: content
        for path, content in file_cache.items()
        if is_java_source(path) or is_jvm_build_file(path)
    }


def _without_comments(path: str, content: str) -> str:
    """Blank out *content*'s comments, leaving every newline where it was.

    Line numbers survive because only non-newline characters are replaced, so a
    match found afterwards still reports the line the reader sees.
    """
    patterns = (
        (_XML_COMMENT,)
        if _basename(path) in _JVM_BUILD_FILES
        else (_GRADLE_BLOCK_COMMENT, _GRADLE_LINE_COMMENT)
    )
    for pattern in patterns:
        content = pattern.sub(lambda match: _NON_NEWLINE.sub(" ", match.group(0)), content)
    return content


def shell_artifact_declaration_lines(file_cache: Mapping[str, str]) -> dict[str, int]:
    """Map each build file that declares LangChain4j's shell module to its line.

    Textual on purpose. Maven declares the artifact id as XML, Gradle as a
    coordinate string, and a Gradle version catalog as TOML; the artifact id
    itself is the one spelling all three share, and no parser is shared.

    Comments are blanked first, so a build file that names the artifact only to
    say it was *removed* is not read as declaring it -- a substring scan cannot
    tell the two apart, and would report both the false positive and the
    comment's line as the location.

    One line per file: the first live declaration. A second in the same build
    file is the same capability, and pointing at both would add noise rather
    than a second thing to fix.
    """
    declarations: dict[str, int] = {}
    for path, content in jvm_build_files(file_cache).items():
        for number, line in enumerate(_without_comments(path, content).splitlines(), start=1):
            if SHELL_ARTIFACT_ID in line:
                declarations[path] = number
                break
    return declarations
