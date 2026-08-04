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

"""Sweep every published LangChain4j release for the spellings the Rules match.

Reads the jars Maven Central serves. A type is observed when the artifact ships a
class file of that name; a method -- which is how LangChain4j spells a builder
argument -- is observed when some class in the artifact *declares* it, read out
of the class file's own method table rather than by searching the bytes. The
difference matters for short names: ``name``, ``content`` and ``tools`` occur in
the constant pool of almost any Java class as strings and descriptors, so a byte
search would report them present in every artifact ever published and measure
nothing.

**What "in scope" means, so the next sweep is comparable.** Every version the
artifact's own ``maven-metadata.xml`` lists, which for these is every release
ever published. Unlike PyPI, nothing here is filtered as a pre-release: the
``-betaNN`` suffix is not a pre-release marker but part of how every release of
the Skills artifacts is named.

**Four artifacts on three version lines.** The Analyzer matches spellings
published by ``langchain4j-skills``, the shell artifact, ``langchain4j-core``
(the ``@Tool`` annotation) and ``langchain4j-mcp``. ``langchain4j-core`` is
released without the ``-betaNN`` suffix, so each artifact is swept over its own
history rather than over one shared spine -- and each is reported under its own
heading, so a range is never read across artifacts that do not share one.
"""

from __future__ import annotations

import io
import re
import struct
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Final

from contrib.vocabulary_sweep.roles import (
    CORE_ARTIFACT,
    LANGCHAIN4J_ARTIFACTS,
    LANGCHAIN4J_ROLES,
    MCP_ARTIFACT,
    SHELL_ARTIFACT,
    SKILLS_ARTIFACT,
    Role,
    assign,
    assign_artifacts,
)
from skillspector.langchain4j import vocabulary

_CENTRAL: Final[str] = "https://repo1.maven.org/maven2"

#: The artifact id behind each symbolic key. The shell artifact's id is read from
#: the inventory rather than written here: it is the one of the four that
#: :mod:`skillspector.langchain4j.vocabulary` owns, and a second copy would be a
#: spelling outside the guard's reach.
_ARTIFACT_IDS: Final[dict[str, str]] = {
    SKILLS_ARTIFACT: "langchain4j-skills",
    SHELL_ARTIFACT: vocabulary.SHELL_ARTIFACT_ID,
    CORE_ARTIFACT: "langchain4j-core",
    MCP_ARTIFACT: "langchain4j-mcp",
}

# Constant-pool tags whose entries are wider than the two-byte default, and the
# two that consume a second slot. Both come from the class file format itself.
_WIDE_TAGS: Final[dict[int, int]] = {
    3: 4,  # Integer
    4: 4,  # Float
    5: 8,  # Long
    6: 8,  # Double
    7: 2,  # Class
    8: 2,  # String
    9: 4,  # Fieldref
    10: 4,  # Methodref
    11: 4,  # InterfaceMethodref
    12: 4,  # NameAndType
    15: 3,  # MethodHandle
    16: 2,  # MethodType
    17: 4,  # Dynamic
    18: 4,  # InvokeDynamic
    19: 2,  # Module
    20: 2,  # Package
}
_UTF8: Final[int] = 1
_TAKES_TWO_SLOTS: Final[frozenset[int]] = frozenset({5, 6})

# `maven-metadata.xml` also carries `<latest>` and `<release>`; only the list
# inside `<versions>` is the published history.
_VERSIONS_BLOCK: Final[re.Pattern[str]] = re.compile(r"<versions>(.*?)</versions>", re.DOTALL)
_VERSION: Final[re.Pattern[str]] = re.compile(r"<version>([^<]+)</version>")


@dataclass(frozen=True)
class Occurrences:
    """Every type and declared method one release's artifact ships."""

    types: frozenset[str]
    methods: frozenset[str]

    def carries(self, spelling: str, role: Role) -> bool:
        """Whether the release writes *spelling* in *role*."""
        if role is Role.DEFINED_NAME:
            return spelling in self.types
        if role is Role.BOUND_NAME:
            return spelling in self.methods
        return False


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 -- https, fixed index
        return bytes(response.read())


def _class_members(data: bytes) -> tuple[list[str], list[str]]:
    """The Utf8 constants of one class file, and the names of the methods it declares.

    Parsed rather than searched. A method a class *declares* is a name upstream
    published; a name that merely appears in the constant pool may have arrived
    through a call to somebody else's API.
    """
    pool: dict[int, str] = {}
    offset = 10  # magic, minor, major, constant_pool_count
    count = struct.unpack_from(">H", data, 8)[0]
    index = 1
    while index < count:
        tag = data[offset]
        offset += 1
        if tag == _UTF8:
            (length,) = struct.unpack_from(">H", data, offset)
            offset += 2
            pool[index] = data[offset : offset + length].decode("utf-8", errors="replace")
            offset += length
        else:
            offset += _WIDE_TAGS[tag]
        index += 2 if tag in _TAKES_TWO_SLOTS else 1

    offset += 6  # access_flags, this_class, super_class
    (interfaces,) = struct.unpack_from(">H", data, offset)
    offset += 2 + 2 * interfaces
    for section in range(2):  # fields, then methods
        (members,) = struct.unpack_from(">H", data, offset)
        offset += 2
        names: list[int] = []
        for _member in range(members):
            name_index = struct.unpack_from(">H", data, offset + 2)[0]
            names.append(name_index)
            offset += 6  # access_flags, name_index, descriptor_index
            (attributes,) = struct.unpack_from(">H", data, offset)
            offset += 2
            for _attribute in range(attributes):
                (length,) = struct.unpack_from(">I", data, offset + 2)
                offset += 6 + length
        if section == 1:
            return list(pool.values()), [pool[name] for name in names if name in pool]
    return list(pool.values()), []


def versions(artifact_id: str) -> list[str]:
    """Every version of *artifact_id* Maven Central lists, oldest first.

    Read with a pattern rather than an XML parser. The document is a flat version
    list served by a fixed index, and every stdlib XML parser is entity-expansion
    material this tool has no reason to accept.
    """
    metadata = _fetch(
        f"{_CENTRAL}/{vocabulary.GROUP_COORDINATE.replace('.', '/')}/"
        f"{artifact_id}/maven-metadata.xml"
    ).decode("utf-8", errors="replace")
    listed = _VERSIONS_BLOCK.search(metadata)
    return _VERSION.findall(listed.group(1)) if listed else []


def read_release(artifact_id: str, version: str) -> Occurrences | None:
    """Every type and declared method one published jar ships, or ``None`` if absent.

    An absent jar is not an empty one. A version listed for a sibling artifact but
    never published for this one has to read as "not published", not as "every
    spelling gone" -- that distinction is the whole point of watching for the
    shell artifact's graduation rename.
    """
    url = (
        f"{_CENTRAL}/{vocabulary.GROUP_COORDINATE.replace('.', '/')}/"
        f"{artifact_id}/{version}/{artifact_id}-{version}.jar"
    )
    try:
        payload = _fetch(url)
    except urllib.error.HTTPError:
        return None
    types: set[str] = set()
    methods: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if not name.endswith(".class"):
                continue
            types.add(name.removesuffix(".class").rsplit("/", 1)[-1].rsplit("$", 1)[-1])
            _pool, declared = _class_members(archive.read(name))
            methods.update(declared)
    return Occurrences(types=frozenset(types), methods=frozenset(methods))


def sweep() -> dict[str, dict[str, dict[str, bool]]]:
    """Each artifact's own history, spelling by spelling. Artifact -> spelling -> version."""
    assigned = assign(vocabulary, LANGCHAIN4J_ROLES)
    located = assign_artifacts(vocabulary, LANGCHAIN4J_ROLES, LANGCHAIN4J_ARTIFACTS)
    swept: dict[str, dict[str, dict[str, bool]]] = {}
    for key, artifact_id in _ARTIFACT_IDS.items():
        wanted = {
            spelling: assigned[spelling][0] for spelling in located if located[spelling] == key
        }
        if not wanted:
            continue
        published = versions(artifact_id)
        observed: dict[str, dict[str, bool]] = {spelling: {} for spelling in wanted}
        for version in published:
            release = read_release(artifact_id, version)
            for spelling, role in wanted.items():
                observed[spelling][version] = (
                    # The artifact id and the group coordinate are observed by
                    # the jar being served under them at all.
                    release is not None
                    if role is Role.DISTRIBUTION
                    else release is not None and release.carries(spelling, role)
                )
        swept[artifact_id] = observed
    return swept
