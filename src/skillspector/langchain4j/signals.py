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
before importing tree-sitter, and that decision is made here -- so a Scan the
Analyzer declines never loads a parser, and an installation missing one still
declines quietly on every input the Analyzer does not own.

The file predicates mirror ``skillspector.framework``'s rather than importing
them: detection asks "is this tree LangChain4j at all", this module asks "which
of its files do I open". The two questions drift apart as later Rules land, and
this repository merges upstream, so a private helper of a phase-1 module is the
wrong thing to couple to.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

JAVA_SUFFIX: Final[str] = ".java"

# Matched on basename at any depth: a multi-module Maven build declares its
# dependencies in a child module's ``pom.xml``, not only at the scan root.
_JVM_BUILD_FILES: Final[tuple[str, ...]] = ("pom.xml",)
_JVM_BUILD_PREFIX: Final[str] = "build.gradle"

# The Maven artifact id of LangChain4j's shell mode. Its presence on the
# classpath is the capability: upstream documents shell execution as running
# "without any sandboxing, containerization, or privilege restriction".
SHELL_ARTIFACT_ID: Final[str] = "langchain4j-experimental-skills-shell"


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


def find_shell_artifact_declarations(file_cache: Mapping[str, str]) -> dict[str, int]:
    """Map each build file declaring LangChain4j's shell module to that line.

    Textual on purpose. Maven declares the artifact id as XML, Gradle as a
    coordinate string, and a Gradle version catalog as TOML; the artifact id
    itself is the one spelling all three share.
    """
    declarations: dict[str, int] = {}
    for path, content in jvm_build_files(file_cache).items():
        for number, line in enumerate(content.splitlines(), start=1):
            if SHELL_ARTIFACT_ID in line:
                declarations[path] = number
                break
    return declarations
