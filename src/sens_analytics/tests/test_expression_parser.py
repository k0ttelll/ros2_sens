"""Unit tests for sens_analytics.expression_parser — boolean expression tree builder.

Covers:
  - Single operands (A, AN, O, ON)
  - Nested blocks A(, O(, )
  - Empty and whitespace-only input
  - Tree serialization (to_dict)
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sens_analytics.expression_parser import ExprNode, build_expression


class TestBuildExpression:
    """Tests for the build_expression() function."""

    def test_single_and(self):
        tree = build_expression(["A Sensor1"])
        assert tree is not None
        assert tree.type == "AND"
        assert tree.value == "Sensor1"

    def test_single_and_not(self):
        tree = build_expression(["AN Sensor1"])
        assert tree.type == "AND_NOT"
        assert tree.value == "Sensor1"

    def test_single_or(self):
        tree = build_expression(["O Sensor1"])
        assert tree.type == "OR"
        assert tree.value == "Sensor1"

    def test_single_or_not(self):
        tree = build_expression(["ON Sensor1"])
        assert tree.type == "OR_NOT"
        assert tree.value == "Sensor1"

    def test_and_block(self):
        tree = build_expression(["A(", "A Sensor1", "A Sensor2", ")"])
        assert tree.type == "AND_BLOCK"
        assert len(tree.children) == 2
        assert tree.children[0].type == "AND"
        assert tree.children[0].value == "Sensor1"
        assert tree.children[1].value == "Sensor2"

    def test_or_block(self):
        tree = build_expression(["O(", "O Sensor1", "O Sensor2", ")"])
        assert tree.type == "OR_BLOCK"
        assert len(tree.children) == 2

    def test_nested_blocks(self):
        tree = build_expression([
            "A(",
            "A Sensor1",
            "O(",
            "O Sensor2",
            "O Sensor3",
            ")",
            ")",
        ])
        assert tree.type == "AND_BLOCK"
        assert len(tree.children) == 2
        assert tree.children[0].type == "AND"
        assert tree.children[1].type == "OR_BLOCK"
        assert len(tree.children[1].children) == 2

    def test_empty_input(self):
        tree = build_expression([])
        assert tree is None

    def test_blank_lines_skipped(self):
        tree = build_expression(["", "  ", "A Sensor1", ""])
        assert tree is not None
        assert tree.value == "Sensor1"

    def test_multiple_flat_operands(self):
        tree = build_expression(["A Sensor1", "AN Sensor2", "O Sensor3"])
        # First operand becomes root, rest are children
        assert tree.type == "AND"
        assert tree.value == "Sensor1"
        assert len(tree.children) == 2


class TestExprNodeSerialization:
    """Tests for ExprNode.to_dict() serialization."""

    def test_leaf_node(self):
        node = ExprNode("AND", "Sensor1")
        d = node.to_dict()
        assert d["type"] == "AND"
        assert d["value"] == "Sensor1"
        assert d["children"] == []

    def test_tree_serialization_roundtrip(self):
        tree = build_expression(["A(", "A Sensor1", "O Sensor2", ")"])
        d = tree.to_dict()
        assert d["type"] == "AND_BLOCK"
        assert len(d["children"]) == 2
        assert d["children"][0]["value"] == "Sensor1"
        assert d["children"][1]["value"] == "Sensor2"
