"""Adapt academic STL PDG graphs into the Sens industrial JSON contract."""

from __future__ import annotations

import json
import re
from typing import Any

import networkx as nx

DEFAULT_BLOCK_NAME = "FC_Unknown"
DEFAULT_NETWORK_NUMBER = 0

_NOISE_RE = re.compile(
    r"^(?:AKKU|ACCU|ACCU[12]|AKKU[12]|AR[12]?|BR|BIE|OV|OS|OR|STA|RLO|"
    r"CC[01]?|DBNO|DINO|STW|TEMP|TMP|#TEMP|P##|L#|W#|B#|DW#|"
    r"[+-]?\d+(?:\.\d+)?|[A-Z]+\d*:)$",
    re.IGNORECASE,
)
_INTERNAL_RE = re.compile(
    r"^(?:M|MB|MW|MD|DB|DBB|DBW|DBD|DI|DIB|DIW|DID|L|LB|LW|LD)\d+(?:\.\d+)?$",
    re.IGNORECASE,
)
_INPUT_RE = re.compile(r"^(?:I|IB|IW|ID|E|EB|EW|ED|PI|PE)\d+(?:\.\d+)?$", re.IGNORECASE)
_OUTPUT_RE = re.compile(r"^(?:Q|QB|QW|QD|A|AB|AW|AD|PQ|PA)\d+(?:\.\d+)?$", re.IGNORECASE)
_ADDRESS_RE = re.compile(r"^[A-Z]{1,3}\d+(?:\.\d+)?$", re.IGNORECASE)
_INVERTED_OPCODES = frozenset(("AN", "ON"))


def transform_pdg_to_sens_json(pdg_graph: nx.DiGraph) -> str:
    """Return a compact Sens JSON dependency graph from an academic PDG.

    Only source-to-target edges that describe real equipment are exported.
    Academic implementation details such as accumulators, processor flags, local
    temporaries and memory/register-like operands are deliberately dropped.
    """

    if not isinstance(pdg_graph, nx.DiGraph):
        raise TypeError("pdg_graph must be a networkx.DiGraph")

    dependencies: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()

    for raw_source, raw_target, edge_data in pdg_graph.edges(data=True):
        source = _node_to_tag(raw_source)
        target = _node_to_tag(raw_target)

        if not _is_physical_source(source) or not _is_physical_target(target):
            continue

        block_name = _clean_block_name(edge_data.get("block_name"))
        network_number = _clean_network_number(edge_data.get("network_number"))
        key = (source, target, block_name, network_number)
        if key in seen:
            continue
        seen.add(key)

        input_opcode = str(edge_data.get("input_opcode", "")).upper()
        dep_type = "inverted" if input_opcode in _INVERTED_OPCODES else "direct_logic"

        dependencies.append(
            {
                "source": source,
                "target": target,
                "block_name": block_name,
                "network_number": network_number,
                "type": dep_type,
            }
        )

    return json.dumps({"dependencies": dependencies}, ensure_ascii=False, separators=(",", ":"))


def _node_to_tag(node: Any) -> str:
    """Extract a stable STL tag name from common NetworkX node payloads."""

    if isinstance(node, str):
        return _normalize_tag(node)

    if isinstance(node, dict):
        for key in ("tag", "name", "operand", "var", "variable", "label", "id"):
            value = node.get(key)
            if value not in (None, ""):
                return _normalize_tag(value)

    for attr in ("tag", "name", "operand", "var", "variable", "label", "id"):
        value = getattr(node, attr, None)
        if value not in (None, ""):
            return _normalize_tag(value)

    return _normalize_tag(node)


def _normalize_tag(value: Any) -> str:
    tag = str(value or "").strip()
    if not tag:
        return ""

    tag = tag.split("//", 1)[0].strip().strip('"').strip("'")
    if ":=" in tag:
        tag = tag.split(":=", 1)[0].strip()
    return tag


def _is_physical_source(tag: str) -> bool:
    if not _is_clean_equipment_tag(tag):
        return False
    return bool(_INPUT_RE.match(tag) or _is_symbolic_tag(tag))


def _is_physical_target(tag: str) -> bool:
    if not _is_clean_equipment_tag(tag):
        return False
    return bool(_OUTPUT_RE.match(tag) or _is_symbolic_tag(tag))


def _is_clean_equipment_tag(tag: str) -> bool:
    if not tag:
        return False

    upper = tag.upper()
    if tag.endswith(":") or tag.startswith(("#", "P#")):
        return False
    if _NOISE_RE.match(tag) or _INTERNAL_RE.match(tag):
        return False
    if _ADDRESS_RE.match(tag) and not (_INPUT_RE.match(tag) or _OUTPUT_RE.match(tag)):
        return False
    if any(token in upper for token in ("AKKU", "ACCU", "RLO", "TEMP", "TMP")):
        return False

    return any(ch.isalpha() for ch in tag)


def _is_symbolic_tag(tag: str) -> bool:
    if not any(ch.isalpha() for ch in tag):
        return False
    return not _ADDRESS_RE.match(tag)


def _clean_block_name(value: Any) -> str:
    block_name = str(value or "").strip().strip('"')
    return block_name or DEFAULT_BLOCK_NAME


def _clean_network_number(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_NETWORK_NUMBER
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_NETWORK_NUMBER
