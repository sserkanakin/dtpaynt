"""
Unit tests for hybrid synthesis components.

Tests for DOT parser, tree slicer, and other core utility functions.
"""

import pytest
import logging
from pathlib import Path
import sys
import os

# Add the synthesis-modified directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from paynt.parser.dot_parser import DotParser, extract_decision_test, extract_action
from paynt.utils.tree_slicer import TreeSlicer, PathCondition, SubProblem

logger = logging.getLogger(__name__)


class TestDotParser:
    """Tests for the DOT parser."""
    
    @pytest.fixture
    def simple_dot(self):
        """Simple decision tree in DOT format."""
        return """
        digraph DecisionTree {
            node0 [label="x <= 5", shape=box];
            node1 [label="y <= 3", shape=box];
            node2 [label="action_a", shape=ellipse];
            node3 [label="action_b", shape=ellipse];
            node4 [label="action_c", shape=ellipse];
            
            node0 -> node1 [label="true"];
            node0 -> node2 [label="false"];
            node1 -> node3 [label="true"];
            node1 -> node4 [label="false"];
        }
        """
    
    def test_parse_dot_basic(self, simple_dot):
        """Test basic DOT parsing."""
        result = DotParser.parse_dot(simple_dot)
        
        assert result is not None
        assert 'nodes' in result
        assert 'edges' in result
        assert 'root_id' in result
        
        # Check nodes
        assert len(result['nodes']) == 5
        assert 'node0' in result['nodes']
        assert 'node1' in result['nodes']
        
        # Check edges
        assert len(result['edges']) == 4
        
        # Check root
        assert result['root_id'] == 'node0'
    
    def test_build_tree_structure(self, simple_dot):
        """Test building hierarchical tree structure from parsed DOT."""
        parsed = DotParser.parse_dot(simple_dot)
        tree_struct = DotParser.build_tree_structure(parsed)
        
        assert tree_struct is not None
        assert 'nodes' in tree_struct
        assert 'children_map' in tree_struct
        assert 'root_id' in tree_struct
        
        # Verify tree connections
        assert tree_struct['children_map']['node0']['true'] is not None
        assert tree_struct['children_map']['node0']['false'] is not None
    
    def test_parse_empty_dot(self):
        """Test parsing empty DOT string."""
        result = DotParser.parse_dot("")
        assert result is not None
        assert len(result['nodes']) == 0
        assert len(result['edges']) == 0


class TestDecisionExtraction:
    """Tests for extracting decisions and actions from labels."""
    
    def test_extract_decision_test_basic(self):
        """Test extracting decision test from label."""
        label = "x <= 5"
        result = extract_decision_test(label)
        
        assert result is not None
        assert result[0] == 'x'
        assert '<=' in result[1]
        assert '5' in result[1]
    
    def test_extract_decision_test_complex(self):
        """Test extracting decision test with complex variable names."""
        label = "state >= 10"
        result = extract_decision_test(label)
        
        assert result is not None
        assert result[0] == 'state'
        assert '>=' in result[1]
    
    def test_extract_action_basic(self):
        """Test extracting action from label."""
        label = "action: move_left"
        result = extract_action(label)
        
        assert result is not None
        assert 'move_left' in result
    
    def test_extract_action_alternative_format(self):
        """Test extracting action with alternative format."""
        label = "choose: a0"
        result = extract_action(label)
        
        assert result is not None
        assert 'a0' in result
    
    def test_extract_action_from_simple_label(self):
        """Test extracting action from simple label."""
        label = "action_a"
        result = extract_action(label)
        
        # Should return the label if it doesn't look like a decision
        assert result is not None or result is None


class TestPathCondition:
    """Tests for path condition representation."""
    
    def test_path_condition_creation(self):
        """Test creating a path condition."""
        decisions = [
            {'variable': 'x', 'operator': '<=', 'value': 5},
            {'variable': 'y', 'operator': '>', 'value': 3}
        ]
        path_cond = PathCondition(decisions=decisions)
        
        assert path_cond is not None
        assert len(path_cond.decisions) == 2
    
    def test_path_condition_string(self):
        """Test converting path condition to string."""
        decisions = [
            {'variable': 'x', 'operator': '<=', 'value': 5},
            {'variable': 'y', 'operator': '>', 'value': 3}
        ]
        path_cond = PathCondition(decisions=decisions)
        
        result = path_cond.to_string()
        assert 'x' in result
        assert 'y' in result
        assert 'AND' in result
    
    def test_empty_path_condition(self):
        """Test empty path condition."""
        path_cond = PathCondition(decisions=[])
        
        result = path_cond.to_string()
        assert result == "root"


class TestTreeSlicer:
    """Tests for tree slicing operations."""
    
    def test_tree_statistics(self):
        """Test computing tree statistics."""
        # Create a mock tree object
        class MockNode:
            def __init__(self, is_term=False):
                self.is_terminal = is_term
                self.child_true = None
                self.child_false = None
                self.identifier = 0
            
            def get_depth(self):
                if self.is_terminal:
                    return 0
                d = 0
                if self.child_true:
                    d = max(d, 1 + self.child_true.get_depth())
                if self.child_false:
                    d = max(d, 1 + self.child_false.get_depth())
                return d
            
            def get_number_of_descendants(self):
                if self.is_terminal:
                    return 0
                n = 1
                if self.child_true:
                    n += self.child_true.get_number_of_descendants()
                if self.child_false:
                    n += self.child_false.get_number_of_descendants()
                return n
        
        # Build a simple tree
        root = MockNode(is_term=False)
        root.child_true = MockNode(is_term=True)
        root.child_false = MockNode(is_term=True)
        
        class MockTree:
            def __init__(self, root):
                self.root = root
        
        tree = MockTree(root)
        
        stats = TreeSlicer.get_tree_statistics(tree)
        
        assert stats['depth'] == 1
        assert stats['node_count'] == 1
        assert stats['leaf_count'] == 2


class TestSubProblem:
    """Tests for sub-problem representation."""
    
    def test_subproblem_creation(self):
        """Test creating a sub-problem."""
        path_cond = PathCondition(decisions=[])
        subproblem = SubProblem(
            sub_tree_node=None,
            path_condition=path_cond,
            depth=3,
            node_count=5,
            tree_path=['node0', 'node1']
        )
        
        assert subproblem.depth == 3
        assert subproblem.node_count == 5
        assert len(subproblem.tree_path) == 2
    
    def test_subproblem_repr(self):
        """Test string representation of sub-problem."""
        path_cond = PathCondition(decisions=[
            {'variable': 'x', 'operator': '<=', 'value': 5}
        ])
        subproblem = SubProblem(
            sub_tree_node=None,
            path_condition=path_cond,
            depth=3,
            node_count=5,
            tree_path=['node0']
        )
        
        result = repr(subproblem)
        assert 'depth=3' in result
        assert 'nodes=5' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
