"""Unit tests for sens_analytics.parser — STL/AWL MVP parser and Parser facade.

Covers:
  - parse_stl_mvp(): IR generation from raw STL text (instructions, labels, CFG edges)
  - Parser.parse_string_to_pdg(): NetworkX DiGraph construction for the service pipeline
"""

import os
import sys

import networkx as nx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sens_analytics.parser import Parser, parse_stl_mvp

# ---------------------------------------------------------------------------
# parse_stl_mvp — IR level
# ---------------------------------------------------------------------------

class TestParseStlMvp:
    """Low-level IR tests for parse_stl_mvp()."""

    def test_empty_input(self):
        result = parse_stl_mvp("")
        assert result["instructions"] == []
        assert result["labels"] == {}
        assert result["cfg_edges"] == []
        assert result["warnings"] == []

    def test_none_input(self):
        result = parse_stl_mvp(None)
        assert result["instructions"] == []

    def test_simple_instructions(self):
        code = "A Sensor1\n= Actuator1"
        result = parse_stl_mvp(code)
        assert len(result["instructions"]) == 2
        assert result["instructions"][0]["opcode"] == "A"
        assert result["instructions"][0]["operand"] == "Sensor1"
        assert result["instructions"][1]["opcode"] == "="
        assert result["instructions"][1]["operand"] == "Actuator1"

    def test_label_parsing(self):
        code = "START: A Sensor1\n= Actuator1"
        result = parse_stl_mvp(code)
        assert "START" in result["labels"]
        assert result["labels"]["START"] == 0

    def test_duplicate_label_warning(self):
        code = "LBL: A Sensor1\nLBL: = Actuator1"
        result = parse_stl_mvp(code)
        warnings = [w for w in result["warnings"] if w["type"] == "duplicate_label"]
        assert len(warnings) == 1

    def test_jump_unconditional(self):
        code = "START: A Sensor1\nJU START"
        result = parse_stl_mvp(code)
        jump_edges = [e for e in result["cfg_edges"] if e["kind"] == "jump"]
        assert len(jump_edges) == 1
        assert jump_edges[0]["target_label"] == "START"
        assert jump_edges[0]["resolved_target_id"] == 0

    def test_jump_conditional(self):
        code = "START: A Sensor1\nJC START\n= Actuator1"
        result = parse_stl_mvp(code)
        branch_edges = [e for e in result["cfg_edges"] if e["kind"] == "branch_true"]
        fallthrough_edges = [e for e in result["cfg_edges"]
                             if e["kind"] == "fallthrough" and e["from"] == 1]
        assert len(branch_edges) == 1
        assert len(fallthrough_edges) == 1

    def test_unresolved_jump_warning(self):
        code = "JU MISSING_LABEL"
        result = parse_stl_mvp(code)
        warnings = [w for w in result["warnings"] if w["type"] == "unresolved_jump_target"]
        assert len(warnings) == 1

    def test_comments_stripped(self):
        code = "A Sensor1 // this is a comment\n= Actuator1"
        result = parse_stl_mvp(code)
        assert len(result["instructions"]) == 2
        assert result["instructions"][0]["operand"] == "Sensor1"

    def test_blank_lines_skipped(self):
        code = "\n\nA Sensor1\n\n= Actuator1\n\n"
        result = parse_stl_mvp(code)
        assert len(result["instructions"]) == 2

    def test_fallthrough_edges(self):
        code = "A Sensor1\nAN Sensor2\n= Actuator1"
        result = parse_stl_mvp(code)
        fallthrough = [e for e in result["cfg_edges"] if e["kind"] == "fallthrough"]
        assert len(fallthrough) == 2
        assert fallthrough[0]["from"] == 0
        assert fallthrough[0]["resolved_target_id"] == 1

    def test_complex_syntax_stub_warning(self):
        code = "A( Sensor1\n)"
        result = parse_stl_mvp(code)
        warnings = [w for w in result["warnings"] if w["type"] == "complex_syntax_stub"]
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Parser — PDG level (NetworkX DiGraph)
# ---------------------------------------------------------------------------

class TestParser:
    """Tests for Parser.parse_string_to_pdg() — service-facing facade."""

    @pytest.fixture
    def parser(self):
        return Parser()

    def test_empty_input_raises(self, parser):
        with pytest.raises(ValueError, match="empty"):
            parser.parse_string_to_pdg("")

    def test_whitespace_only_raises(self, parser):
        with pytest.raises(ValueError, match="empty"):
            parser.parse_string_to_pdg("   \n\n  ")

    def test_simple_direct_dependency(self, parser):
        code = "FUNCTION FC_Test\nNETWORK 1\nA Sensor1\n= Actuator1\nEND_FUNCTION"
        graph = parser.parse_string_to_pdg(code)
        assert isinstance(graph, nx.DiGraph)
        assert graph.has_edge("Sensor1", "Actuator1")

    def test_inverted_dependency(self, parser):
        code = "FUNCTION FC_Test\nNETWORK 1\nAN Sensor1\n= Actuator1\nEND_FUNCTION"
        graph = parser.parse_string_to_pdg(code)
        assert graph.has_edge("Sensor1", "Actuator1")
        edge_data = graph.edges["Sensor1", "Actuator1"]
        assert edge_data["input_opcode"] == "AN"

    def test_multiple_sources_to_single_target(self, parser):
        code = ("FUNCTION FC_Test\nNETWORK 1\n"
                "A Sensor1\nAN Sensor2\nO Sensor3\n= Actuator1\n"
                "END_FUNCTION")
        graph = parser.parse_string_to_pdg(code)
        assert graph.has_edge("Sensor1", "Actuator1")
        assert graph.has_edge("Sensor2", "Actuator1")
        assert graph.has_edge("Sensor3", "Actuator1")

    def test_no_self_loops(self, parser):
        code = "FUNCTION FC_Test\nNETWORK 1\nA Tag1\n= Tag1\nEND_FUNCTION"
        graph = parser.parse_string_to_pdg(code)
        assert not graph.has_edge("Tag1", "Tag1")

    def test_block_name_extraction(self, parser):
        code = 'FUNCTION FC_Cylinder_Control\nNETWORK 5\nA Sensor1\n= Actuator1\nEND_FUNCTION'
        graph = parser.parse_string_to_pdg(code)
        edge_data = graph.edges["Sensor1", "Actuator1"]
        assert edge_data["block_name"] == "FC_Cylinder_Control"
        assert edge_data["network_number"] == 5

    def test_network_boundary_resets_sources(self, parser):
        code = ("FUNCTION FC_Test\n"
                "NETWORK 1\nA Sensor1\n= Actuator1\n"
                "NETWORK 2\nA Sensor2\n= Actuator2\n"
                "END_FUNCTION")
        graph = parser.parse_string_to_pdg(code)
        assert graph.has_edge("Sensor1", "Actuator1")
        assert graph.has_edge("Sensor2", "Actuator2")
        # Sensor1 should NOT reach Actuator2 (different network)
        assert not graph.has_edge("Sensor1", "Actuator2")

    def test_transfer_resets_sources(self, parser):
        """T (Transfer) opcode should clear the accumulator context."""
        code = "FUNCTION FC_Test\nNETWORK 1\nL Sensor1\nT Target1\nA Sensor2\n= Target2\nEND_FUNCTION"
        graph = parser.parse_string_to_pdg(code)
        # After T, Sensor1 should not reach Target2
        assert not graph.has_edge("Sensor1", "Target2")
        assert graph.has_edge("Sensor2", "Target2")

    def test_parse_alias(self, parser):
        """Parser.parse() should behave identically to parse_string_to_pdg()."""
        code = "FUNCTION FC_Test\nNETWORK 1\nA Sensor1\n= Actuator1\nEND_FUNCTION"
        g1 = parser.parse_string_to_pdg(code)
        g2 = parser.parse(code)
        assert set(g1.edges) == set(g2.edges)

    def test_real_world_cylinder_control(self, parser):
        """Realistic STL block from the README example."""
        code = (
            "FUNCTION FC_Cylinder_Control\n"
            "NETWORK 5\n"
            "A A1_Cyl3_Open_Sens\n"
            "AN A1_EStop_Active\n"
            "= A1_Cyl3_Actuate\n"
            "END_FUNCTION"
        )
        graph = parser.parse_string_to_pdg(code)
        assert graph.has_edge("A1_Cyl3_Open_Sens", "A1_Cyl3_Actuate")
        assert graph.has_edge("A1_EStop_Active", "A1_Cyl3_Actuate")
        # Check opcodes
        assert graph.edges["A1_Cyl3_Open_Sens", "A1_Cyl3_Actuate"]["input_opcode"] == "A"
        assert graph.edges["A1_EStop_Active", "A1_Cyl3_Actuate"]["input_opcode"] == "AN"
