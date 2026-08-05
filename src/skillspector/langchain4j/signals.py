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
from dataclasses import dataclass
from typing import Final

# Its presence on the classpath is the capability: upstream documents shell
# execution as running "without any sandboxing, containerization, or privilege
# restriction". Imported rather than spelled here -- ``vocabulary`` is the
# single home for anything a LangChain4j release can rename.
from skillspector.langchain4j.vocabulary import SHELL_ARTIFACT_PATTERN

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


def _refusal_subtree(tag: str, enclosing: str) -> re.Pattern[str]:
    """Match one XML subtree that names an artifact in order to *refuse* it.

    A plain ``<tag>.*?</tag>`` pairs an **unclosed** opening tag with the next
    closing tag anywhere later in the file and blanks every declaration between
    them -- trading a false positive for the false negative issue #45 exists to
    prevent. So the region is tempered twice: it may cross neither a second
    ``<tag`` opening nor the close of *enclosing*, the element the subtree
    always lives inside. An unclosed tag then matches nothing that reaches past
    its own element, and the build file loses the blanking rather than a
    Finding.

    What survives both tempers is an unclosed tag and an orphan close inside one
    *enclosing* element, with a declaration between them. A textual scan cannot
    tell that apart from a well-formed subtree containing the same line, and
    neither can a reader.
    """
    return re.compile(
        rf"<{tag}\b(?:(?!<{tag}\b|</{enclosing}\b).)*?</{tag}\s*>",
        re.DOTALL,
    )


# The two Maven subtrees that name an artifact in order to refuse it: a
# dependency's ``<exclusions>``, and the Enforcer plugin's
# ``<bannedDependencies>``. Both say in XML what ``_XML_COMMENT`` already blanks
# when it is said in a comment.
#
# Blanking all of ``<bannedDependencies>`` takes its ``<includes>`` with it --
# the exception list that allows a banned artifact back. That is the right way
# round: an artifact allowed back through an Enforcer exception is still not
# *declared* by this build file, and reading it as one would restore the
# inversion for the narrower case.
_XML_EXCLUSIONS: Final[re.Pattern[str]] = _refusal_subtree("exclusions", "dependency")
_XML_BANNED_DEPENDENCIES: Final[re.Pattern[str]] = _refusal_subtree("bannedDependencies", "rules")

# Gradle says in an ``exclude`` call what Maven says in ``<exclusions>``, and
# says it in many spellings: two DSLs, an optional group, named or positional
# arguments, wrapped across lines or not. Issue #88 surveyed 262 real build files
# and observed eight of the ten below; the two wrapped forms are predicted rather
# than observed -- measured against this function, which does fire on them, and
# produced by any 100-column formatter, but absent from the surveyed population.
#
# The anchor is the call and its argument list -- never the line holding them.
# Anchoring to the call is what collapses every spelling into one recognizer:
# what is sought is the word ``exclude`` and its arguments, not which arguments
# it was given. It is also what keeps a real declaration that excludes something
# else on the *same* line, a shape Maven cannot produce: the text before the call
# survives the blanking.
#
# Two boundaries, because the two DSLs end an argument list differently. A
# parenthesised list ends at its ``)``, one level of nesting deep so Shadow's
# ``exclude(dependency("g:a:v"))`` is one match. An unparenthesised Groovy list
# runs to end of line, and continues while the line ends in a comma -- the shape
# any 100-column formatter produces.
#
# Each branch is tempered, the way ``_refusal_subtree`` is, and each keeps a
# residual hole the way that one does too. The parenthesised branch may cross
# neither ``{`` nor ``}``, which no legitimate ``exclude`` argument contains, so
# an unclosed ``exclude(`` inside a closure stops at that closure's brace rather
# than pairing with a ``)`` further down the file and blanking a real declaration
# between them -- the false negative issue #45 exists to prevent. It also refuses
# to start the line branch, so an unclosed call cannot fall through and eat lines
# by their trailing commas instead.
#
# What survives both tempers, and is accepted rather than fixed: an unclosed
# ``exclude(`` and an orphan ``)`` with no brace between them, and a Groovy
# ``exclude`` line whose trailing comma is followed by a declaration rather than
# by the rest of its own argument list. Both take malformed or unformattable
# input, both blank a declaration a reader can see, and closing either needs the
# brace-nesting this module exists without -- exactly the tradeoff
# ``_refusal_subtree`` records for the Maven side. Issue #91 keeps the analysis.
_GRADLE_EXCLUDE_CALL: Final[re.Pattern[str]] = re.compile(
    r"\bexclude\b(?:"
    r"\s*\((?:[^(){}]|\([^(){}]*\))*\)"
    r"|(?!\s*\()(?:[^\n]*,[ \t]*\n)*[^\n]*"
    r")"
)

# Compiled here rather than in ``vocabulary``, which stays import-free.
_SHELL_ARTIFACT: Final[re.Pattern[str]] = re.compile(SHELL_ARTIFACT_PATTERN)


def _basename(path: str) -> str:
    """Return the final segment of a component path.

    ``file_cache`` keys always use forward slashes -- ``build_context``
    normalizes them so they stay portable as dict keys and SARIF locations.
    """
    return path.rsplit("/", 1)[-1]


def is_java_source(path: str) -> bool:
    """Whether *path* names a Java compilation unit."""
    return path.endswith(JAVA_SUFFIX)


def _is_maven_build_file(path: str) -> bool:
    """Whether *path* names a Maven build file, whose syntax is XML."""
    return _basename(path) in _JVM_BUILD_FILES


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


def _blanked(match: re.Match[str]) -> str:
    """Replace a matched region with spaces, leaving every newline where it was.

    Line numbers survive because only non-newline characters are replaced, so a
    match found afterwards still reports the line the reader sees.
    """
    return _NON_NEWLINE.sub(" ", match.group(0))


def _without_comments(path: str, content: str) -> str:
    """Blank out *content*'s comments, leaving every newline where it was."""
    patterns = (
        (_XML_COMMENT,)
        if _is_maven_build_file(path)
        else (_GRADLE_BLOCK_COMMENT, _GRADLE_LINE_COMMENT)
    )
    for pattern in patterns:
        content = pattern.sub(_blanked, content)
    return content


def _without_refusals(path: str, content: str) -> str:
    """Blank out the regions that name an artifact only to refuse it.

    Per build system, because a Refusal has no shape the two share: Maven says
    it as a ``<exclusions>`` or ``<bannedDependencies>`` subtree, Gradle as an
    ``exclude`` call. Issue #64 settled the Maven side, issue #68 the Gradle one.

    The Gradle recognizer is deliberately **context-free**: any ``exclude`` in a
    ``build.gradle*``, with no tracking of the closure it sits in. Requiring the
    call to sit inside a dependency closure would take the brace-nesting the
    module exists without -- the same parsing ``_refusal_subtree``'s docstring
    declines on the Maven side. Context-freedom buys ``configurations.all`` at no
    cost, and it also blanks Gradle's file-filter ``exclude``
    (``jar { exclude("META-INF/*.SF") }``), which is harmless unless such a call
    names a shell coordinate in its own arguments.

    Run *after* ``_without_comments``: a commented-out ``<exclusions>`` is
    already spaces by then and cannot pair with a live closing tag, and a
    commented-out ``exclude`` cannot swallow the line below it.

    Textual, like everything else here. Reading the element nesting would need
    the XML parser this module exists without, and would buy nothing the
    tempered patterns do not already give.
    """
    patterns = (
        (_XML_EXCLUSIONS, _XML_BANNED_DEPENDENCIES)
        if _is_maven_build_file(path)
        else (_GRADLE_EXCLUDE_CALL,)
    )
    for pattern in patterns:
        content = pattern.sub(_blanked, content)
    return content


@dataclass(frozen=True)
class ShellDeclaration:
    """One build file's declaration of LangChain4j's shell module.

    ``artifact_id`` is the spelling the build file actually used, not the one
    the inventory records. The two are the same today and are expected to differ
    the day the artifact graduates out of ``experimental``, which is exactly when
    a Finding naming the inventoried spelling would be describing a dependency
    the reader cannot find in their own build file.
    """

    line: int
    artifact_id: str


def shell_artifact_declarations(file_cache: Mapping[str, str]) -> dict[str, ShellDeclaration]:
    """Map each build file that declares LangChain4j's shell module to what it declared.

    Textual on purpose. Maven declares the artifact id as XML, Gradle as a
    coordinate string, and a Gradle version catalog as TOML; the artifact id
    itself is the one spelling all three share, and no parser is shared.

    Matched as ``SHELL_ARTIFACT_PATTERN`` rather than as the published artifact
    id, so the Rule survives the graduation rename upstream has signalled by
    naming the artifact ``experimental``. The pattern is confined to a single
    hyphenated ``langchain4j-`` token, so the safe sibling ``langchain4j-skills``
    does not satisfy it -- ``docs/adr/0007-l4j-shell-survives-the-graduation-rename.md``
    records why the match is a pattern rather than an enumeration of spellings.

    A build file that names the artifact only to say it is *not* taken is not
    read as declaring it -- a textual scan cannot tell the two apart, and would
    report the false positive at the refusing line, flagging the reader HIGH for
    the one action that removes the risk. Four spellings say it: a comment, a
    dependency's ``<exclusions>`` subtree, Enforcer's ``<bannedDependencies>``,
    and Gradle's ``exclude`` call in any of its spellings. All four are blanked
    before matching, comments first so a commented-out subtree cannot pair with
    a live closing tag.

    One declaration per file: the first live one. A second in the same build
    file is the same capability, and pointing at both would add noise rather
    than a second thing to fix.
    """
    declarations: dict[str, ShellDeclaration] = {}
    for path, content in jvm_build_files(file_cache).items():
        matchable = _without_refusals(path, _without_comments(path, content))
        for number, line in enumerate(matchable.splitlines(), start=1):
            match = _SHELL_ARTIFACT.search(line)
            if match is not None:
                declarations[path] = ShellDeclaration(line=number, artifact_id=match.group(0))
                break
    return declarations
