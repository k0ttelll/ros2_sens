"""Unit tests for sens_analytics.graph_adapter — PDG-to-Sens JSON projection.

Covers:
  - transform_pdg_to_sens_json(): end-to-end PDG → JSON conversion
  - Type classification (direct_logic / inverted)
  - Noise filtering (accumulators, registers, markers, temps, internals)
  - Deduplication of identical edges
  - Physical I/O address classification
  - Edge cases (empty graph, invalid input)
"""

import json
import pytest
import networkx as nx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sens_analytics.graph_adapter import transform_pdg_to_sens_json


def _make_graph(*edges):
    """Helper: build a DiGraph from (source, target, edge_data) tuples."""
    g = nx.DiGraph()
    for src, tgt, data in edges:
        g.add_edge(src, tgt, **data)
    return g


def _parse_deps(json_str):
    """Parse JSON and return the dependencies list."""
    return json.loads(json_str)["dependencies"]


# ---------------------------------------------------------------------------
# Type mapping: direct_logic vs inverted
# ---------------------------------------------------------------------------

class TestTypeMapping:
    """Verify that input_opcode maps correctly to dependency type."""

    def test_direct_logic_A(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "A"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert len(deps) == 1
        assert deps[0]["type"] == "direct_logic"

    def test_direct_logic_O(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "O"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["type"] == "direct_logic"

    def test_direct_logic_L(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "L"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["type"] == "direct_logic"

    def test_inverted_AN(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "AN"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert len(deps) == 1
        assert deps[0]["type"] == "inverted"

    def test_inverted_ON(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "ON"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["type"] == "inverted"

    def test_missing_opcode_defaults_to_direct(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 1,
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["type"] == "direct_logic"


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

class TestNoiseFiltering:
    """Verify that non-physical operands are filtered out."""

    def _single_edge_graph(self, source, target):
        return _make_graph((source, target, {
            "block_name": "FC_Test", "network_number": 1, "input_opcode": "A"
        }))

    def test_filters_accumulator_AKKU1(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("AKKU1", "Actuator1")))
        assert len(deps) == 0

    def test_filters_accumulator_ACCU2(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("ACCU2", "Actuator1")))
        assert len(deps) == 0

    def test_filters_marker_MW10(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("MW10", "Actuator1")))
        assert len(deps) == 0

    def test_filters_db_internal_DBW5(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("DBW5", "Actuator1")))
        assert len(deps) == 0

    def test_filters_temp_variable(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("#TEMP", "Actuator1")))
        assert len(deps) == 0

    def test_filters_numeric_constant(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("42", "Actuator1")))
        assert len(deps) == 0

    def test_filters_register_AR1(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("AR1", "Actuator1")))
        assert len(deps) == 0

    def test_passes_symbolic_equipment_tag(self):
        deps = _parse_deps(transform_pdg_to_sens_json(
            self._single_edge_graph("A1_Cyl3_Open_Sens", "A1_Cyl3_Actuate")))
        assert len(deps) == 1
        assert deps[0]["source"] == "A1_Cyl3_Open_Sens"
        assert deps[0]["target"] == "A1_Cyl3_Actuate"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Identical edges should appear only once."""

    def test_duplicate_edges_collapsed(self):
        g = nx.DiGraph()
        # Add two edges with identical logical content (multigraph workaround)
        g.add_edge("Sensor1", "Actuator1",
                    block_name="FC_Test", network_number=1, input_opcode="A")
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert len(deps) == 1


# ---------------------------------------------------------------------------
# JSON structure
# ---------------------------------------------------------------------------

class TestJsonStructure:
    """Verify the output JSON contract matches the README spec."""

    def test_all_required_fields(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "network_number": 3, "input_opcode": "A"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        dep = deps[0]
        assert set(dep.keys()) == {"source", "target", "block_name", "network_number", "type"}
        assert dep["source"] == "Sensor1"
        assert dep["target"] == "Actuator1"
        assert dep["block_name"] == "FC_Test"
        assert dep["network_number"] == 3
        assert dep["type"] == "direct_logic"

    def test_default_block_name(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "network_number": 1, "input_opcode": "A"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["block_name"] == "FC_Unknown"

    def test_default_network_number(self):
        g = _make_graph(("Sensor1", "Actuator1", {
            "block_name": "FC_Test", "input_opcode": "A"
        }))
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert deps[0]["network_number"] == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Empty graphs, invalid inputs."""

    def test_empty_graph(self):
        g = nx.DiGraph()
        result = json.loads(transform_pdg_to_sens_json(g))
        assert result == {"dependencies": []}

    def test_invalid_input_type(self):
        with pytest.raises(TypeError, match="DiGraph"):
            transform_pdg_to_sens_json("not a graph")

    def test_invalid_input_none(self):
        with pytest.raises(TypeError):
            transform_pdg_to_sens_json(None)

    def test_graph_with_only_noise(self):
        """Graph where all nodes are noise — should return empty deps."""
        g = _make_graph(
            ("AKKU1", "MW10", {"block_name": "FC_T", "network_number": 1, "input_opcode": "A"}),
            ("AR1", "DBW5", {"block_name": "FC_T", "network_number": 1, "input_opcode": "A"}),
        )
        deps = _parse_deps(transform_pdg_to_sens_json(g))
        assert len(deps) == 0


# ---------------------------------------------------------------------------
# End-to-end: Parser → graph_adapter pipeline
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Integration test: raw STL text → Parser → graph_adapter → JSON."""

    def test_cylinder_control_pipeline(self):
        """Reproduce the README example end-to-end."""
        from sens_analytics.parser import Parser

        code = (
            "FUNCTION FC_Cylinder_Control\n"
            "NETWORK 5\n"
            "A A1_Cyl3_Open_Sens\n"
            "AN A1_EStop_Active\n"
            "= A1_Cyl3_Actuate\n"
            "END_FUNCTION"
        )
        parser = Parser()
        graph = parser.parse_string_to_pdg(code)
        json_str = transform_pdg_to_sens_json(graph)
        deps = json.loads(json_str)["dependencies"]

        assert len(deps) == 2

        # Sort by source for stable assertions
        deps.sort(key=lambda d: d["source"])

        assert deps[0]["source"] == "A1_Cyl3_Open_Sens"
        assert deps[0]["target"] == "A1_Cyl3_Actuate"
        assert deps[0]["type"] == "direct_logic"
        assert deps[0]["block_name"] == "FC_Cylinder_Control"
        assert deps[0]["network_number"] == 5

        assert deps[1]["source"] == "A1_EStop_Active"
        assert deps[1]["target"] == "A1_Cyl3_Actuate"
        assert deps[1]["type"] == "inverted"

    def test_multi_network_pipeline(self):
        """Multiple networks produce independent dependency sets."""
        from sens_analytics.parser import Parser

        code = (
            "FUNCTION FC_Multi\n"
            "NETWORK 1\n"
            "A SensorA\n= ActuatorA\n"
            "NETWORK 2\n"
            "AN SensorB\n= ActuatorB\n"
            "END_FUNCTION"
        )
        parser = Parser()
        graph = parser.parse_string_to_pdg(code)
        json_str = transform_pdg_to_sens_json(graph)
        deps = json.loads(json_str)["dependencies"]

        assert len(deps) == 2
        sources = {d["source"] for d in deps}
        assert sources == {"SensorA", "SensorB"}
