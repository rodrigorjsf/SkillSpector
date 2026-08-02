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

"""The canonical Behavior Snapshot projection.

A pure function from the state ``graph.invoke`` returns to a plain, deterministic
dictionary. Specified by ``docs/adr/0003-behavior-snapshot-projection.md`` and
measured by ``docs/behavior-snapshot-projection-findings.md``.

The pipeline is **coerce -> strip -> sort**, in that order. Stripping precedes
sorting because the sort's final tie-breaker is the element's full canonical
serialization: serializing before the ``uuid4()`` identifiers are gone would put
run-unique values back into the sort key, which is the exact nondeterminism the
projection exists to remove.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# The nine state keys the snapshot projects. See ADR 0003.
PROJECTED_STATE_KEYS: tuple[str, ...] = (
    "findings",
    "risk_score",
    "risk_severity",
    "risk_recommendation",
    "component_metadata",
    "has_executable_scripts",
    "manifest",
    "analysis_completeness",
    "sarif_report",
)

# State keys deliberately kept out, each with the reason it is out.
EXCLUDED_STATE_KEYS: Mapping[str, str] = {
    "model_config": "derived from environment variables; would make a snapshot machine-specific",
    "report_body": "carries the wall clock and the absolute input path",
    "skill_path": "an absolute path",
    "temp_dir_for_cleanup": "an absolute path",
}

# Fields stripped from inside the projection, each with the reason.
STRIPPED_FIELDS: Mapping[str, str] = {
    "$.findings[].finding_id": (
        "a fresh uuid4() per Finding, the only measured source of nondeterminism in "
        "state; dropped rather than normalized because nothing else in the projection "
        "references it"
    ),
    "$.sarif_report.runs[].results[].properties.findingId": (
        "SARIF's copy of the same run-unique identifier"
    ),
    "$.sarif_report.runs[].tool.driver.version": (
        "the scanner version; a release bump is not a behavior change"
    ),
}


def _to_plain(value: Any) -> Any:
    """Coerce graph state into JSON-native containers, recursively."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return _to_plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, (str, bytes)):
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    if isinstance(value, Sequence):
        return [_to_plain(item) for item in value]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)


def _strip(projection: dict[str, Any]) -> dict[str, Any]:
    """Remove the stripped fields, addressed by path rather than by key name.

    Addressing by path matters: a recursive "delete every key named ``version``"
    would also eat SARIF's ``semanticVersion`` and any rule-level version, which
    is behavior the gate is supposed to hold still.
    """
    for finding in projection.get("findings", []) or []:
        if isinstance(finding, dict):
            finding.pop("finding_id", None)

    sarif = projection.get("sarif_report")
    if not isinstance(sarif, dict):
        return projection
    for run in sarif.get("runs", []) or []:
        if not isinstance(run, dict):
            continue
        driver = (run.get("tool") or {}).get("driver")
        if isinstance(driver, dict):
            driver.pop("version", None)
        for result in run.get("results", []) or []:
            properties = result.get("properties") if isinstance(result, dict) else None
            if isinstance(properties, dict):
                properties.pop("findingId", None)
    return projection


def _canonical(value: Any) -> str:
    """Return the element's full canonical serialization: the total tie-breaker."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _atom(value: Any) -> tuple[int, float, str]:
    """Return a totally ordered stand-in for one named-key component.

    Named keys mix ``None``, ints and strings (``end_line`` is ``int | None``),
    which are not mutually comparable. The type rank keeps the comparison legal
    while numbers still sort numerically, so the Behavior Snapshot stays grouped by
    file and ascending line -- which is how a reviewer reads a security diff.
    """
    if value is None:
        return (0, 0.0, "")
    if isinstance(value, bool):
        return (1, float(value), "")
    if isinstance(value, (int, float)):
        return (2, float(value), "")
    return (3, 0.0, str(value))


def _named(*values: Any) -> tuple[tuple[int, float, str], ...]:
    return tuple(_atom(value) for value in values)


def _finding_key(finding: Any) -> tuple[Any, ...]:
    if not isinstance(finding, dict):
        return ()
    return _named(
        finding.get("file"),
        finding.get("start_line"),
        finding.get("end_line"),
        finding.get("rule_id"),
        finding.get("message"),
    )


def _sarif_result_key(result: Any) -> tuple[Any, ...]:
    """The ``$.findings`` key, read out of the SARIF result shape."""
    if not isinstance(result, dict):
        return ()
    locations = result.get("locations") or []
    physical = locations[0].get("physicalLocation", {}) if locations else {}
    region = physical.get("region", {}) if isinstance(physical, dict) else {}
    artifact = physical.get("artifactLocation", {}) if isinstance(physical, dict) else {}
    message = result.get("message") or {}
    return _named(
        artifact.get("uri") if isinstance(artifact, dict) else None,
        region.get("startLine") if isinstance(region, dict) else None,
        region.get("endLine") if isinstance(region, dict) else None,
        result.get("ruleId"),
        message.get("text") if isinstance(message, dict) else None,
    )


def _sarif_notification_key(notification: Any) -> tuple[Any, ...]:
    """``(level, message)``, where SARIF's message is ``{"text": ...}``."""
    if not isinstance(notification, dict):
        return ()
    message = notification.get("message") or {}
    return _named(
        notification.get("level"),
        message.get("text") if isinstance(message, dict) else message,
    )


def _field_key(*names: str) -> Callable[[Any], tuple[Any, ...]]:
    def key(element: Any) -> tuple[Any, ...]:
        if not isinstance(element, dict):
            return ()
        return _named(*(element.get(name) for name in names))

    return key


# One ledger exception's identity, shared by the two lists that hold them.
_ledger_exception_key = _field_key(
    "phase", "reason_code", "path", "start_line", "end_line", "message"
)

# Named sort keys, addressed by the path notation used in the #6 measurements.
# A list with no entry here is ordered by its canonical serialization alone,
# which is already total; the named key exists to keep the file readable.
NAMED_SORT_KEYS: Mapping[str, Callable[[Any], tuple[Any, ...]]] = {
    "$.findings": _finding_key,
    "$.component_metadata": _field_key("path"),
    "$.manifest.parameters": _field_key("name"),
    "$.analysis_completeness.analyzer_statuses": _field_key("analyzer_id"),
    "$.analysis_completeness.ledger_exceptions": _ledger_exception_key,
    "$.analysis_completeness.scope_exclusions": _ledger_exception_key,
    "$.sarif_report.runs[].results": _sarif_result_key,
    "$.sarif_report.runs[].tool.driver.rules": _field_key("id"),
    "$.sarif_report.runs[].invocations[].toolExecutionNotifications": _sarif_notification_key,
}


def _sort(value: Any, path: str) -> Any:
    """Sort every list in the projection, depth first.

    Children are canonicalized before the parent list is ordered, so the
    serialization tie-breaker compares already-canonical elements.
    """
    if isinstance(value, dict):
        return {key: _sort(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        elements = [_sort(item, f"{path}[]") for item in value]
        named = NAMED_SORT_KEYS.get(path)
        return sorted(elements, key=lambda e: ((named(e) if named else ()), _canonical(e)))
    return value


def project_scan_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project the state ``graph.invoke`` returned into the Behavior Snapshot.

    Pure: the input is not mutated, and the result depends on nothing but it.
    A projected key absent from the state is absent from the result -- a key that
    stops being emitted is itself a behavior change and must show as a diff.
    """
    projection = {key: _to_plain(state[key]) for key in PROJECTED_STATE_KEYS if key in state}
    return _sort(_strip(projection), "$")


def serialize(projection: Mapping[str, Any]) -> str:
    """Render a projection as the bytes committed to a snapshot file."""
    return json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


_BEHAVIOR_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = _BEHAVIOR_DIR / "snapshots"
FIXTURES_DIR = _BEHAVIOR_DIR.parent / "fixtures"

# The scan targets under the gate: every leaf fixture directory, named by its
# path relative to ``tests/fixtures`` so the snapshot layout mirrors the fixture
# one (``sdi/sdi1_mismatch`` -> ``snapshots/sdi/sdi1_mismatch.json``).
#
# A leaf is a directory that is itself a scan target. Twenty-three bear a
# ``SKILL.md``; ``mcp_registry`` bears none and is included anyway, because it is
# scanned in practice and the gate's job is to hold current behavior still --
# including the anonymous-Skill result #11 tracks changing.
#
# ``sdi/``, ``sqp/`` and ``ssd/`` are excluded: they are fixture-layout
# containers holding a family of Skills, not Skills themselves.
CORPUS_NAMES: tuple[str, ...] = (
    "malicious_skill",
    "mcp_clean_skill",
    "mcp_mismatched_skill",
    "mcp_overprivileged_skill",
    "mcp_poisoned_tool",
    "mcp_registry",
    "mcp_underdeclared_skill",
    "safe_skill",
    "sdi/sdi1_mismatch",
    "sdi/sdi2_inappropriate",
    "sdi/sdi3_scope_creep",
    "sdi/sdi4_divergence",
    "sdi/sdi_clean",
    "sqp/sqp1_clean",
    "sqp/sqp1_vague_triggers",
    "sqp/sqp2_clean",
    "sqp/sqp2_missing_warnings",
    "sqp/sqp3_clean",
    "sqp/sqp3_locale_forcing",
    "ssd/ssd1_semantic_injection",
    "ssd/ssd2_novel_phrasing",
    "ssd/ssd3_nl_exfiltration",
    "ssd/ssd4_narrative_deception",
    "ssd/ssd_clean",
)

# The fixture family parents, excluded from the corpus by the rule above. Named
# rather than merely omitted so the exclusion is assertable.
FAMILY_PARENTS: tuple[str, ...] = ("sdi", "sqp", "ssd")

CORPUS: Mapping[str, Path] = {name: FIXTURES_DIR / name for name in CORPUS_NAMES}

# The fixture whose measured shape the shape-specific tests are written against:
# the most projected surface in one target, and the only one measured to hold a
# colliding named sort key.
REFERENCE_FIXTURE = "malicious_skill"


def snapshot_path(name: str) -> Path:
    """Return the committed snapshot file for one corpus entry.

    The name may carry a ``/``, which nests the snapshot exactly as the fixture
    is nested.
    """
    return SNAPSHOT_DIR / f"{name}.json"


def load_snapshot(name: str) -> dict[str, Any]:
    """Read one committed snapshot.

    Deliberately catches nothing: a missing file raises ``FileNotFoundError`` and
    a corrupt one raises ``json.JSONDecodeError``. The gate never self-heals --
    regeneration is only ever the explicit ``make update-snapshots`` target.
    """
    return json.loads(snapshot_path(name).read_text(encoding="utf-8"))


def scan_state(skill_path: Path | str) -> Mapping[str, Any]:
    """Run one Scan and return the raw state, unprojected.

    The single place the graph is invoked, so the gate, the regeneration target
    and any test reasoning about pre-projection state can never drift into
    scanning differently. ``use_llm`` is pinned False here rather than read from
    the environment: an ambient API key must not change what the gate holds
    still.
    """
    from skillspector.graph import graph

    return graph.invoke({"skill_path": str(skill_path), "use_llm": False})


def scan(skill_path: Path | str) -> dict[str, Any]:
    """Scan one Skill and return its Behavior Snapshot projection."""
    return project_scan_state(scan_state(skill_path))
