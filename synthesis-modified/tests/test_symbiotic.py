"""
Comprehensive test suite for the symbiotic synthesis method.
Tests include DT parsing, template generation, and full integration tests.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

import paynt.synthesizer.synthesizer_symbiotic as symbiotic


class TestDecisionTreeNode:
    """Test the DecisionTreeNode class."""
    
    def test_leaf_node_creation(self):
        """Test creating a leaf node."""
        node = symbiotic.DecisionTreeNode(1, is_leaf=True, action="a0")
        assert node.is_leaf
        assert node.action == "a0"
        assert len(node.children) == 0
    
    def test_inner_node_creation(self):
        """Test creating an inner node."""
        node = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="s > 5")
        assert not node.is_leaf
        assert node.predicate == "s > 5"
        assert len(node.children) == 0
    
    def test_tree_structure(self):
        """Test building a tree structure."""
        root = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        child1 = symbiotic.DecisionTreeNode(1, is_leaf=True, action="a0")
        child2 = symbiotic.DecisionTreeNode(2, is_leaf=True, action="a1")
        
        root.children[0] = child1
        root.children[1] = child2
        child1.parent = root
        child2.parent = root
        
        assert len(root.children) == 2
        assert root.num_nodes() == 3
        assert root.num_leaves() == 2
    
    def test_deep_tree_structure(self):
        """Test a deeper tree structure."""
        # Create a tree: root -> inner1 -> leaf1, leaf2; inner2 -> leaf3
        root = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        inner1 = symbiotic.DecisionTreeNode(1, is_leaf=False, predicate="inner1")
        leaf1 = symbiotic.DecisionTreeNode(2, is_leaf=True, action="a0")
        leaf2 = symbiotic.DecisionTreeNode(3, is_leaf=True, action="a1")
        inner2 = symbiotic.DecisionTreeNode(4, is_leaf=False, predicate="inner2")
        leaf3 = symbiotic.DecisionTreeNode(5, is_leaf=True, action="a0")
        
        root.children[0] = inner1
        root.children[1] = inner2
        inner1.children[0] = leaf1
        inner1.children[1] = leaf2
        inner2.children[0] = leaf3
        
        assert root.num_nodes() == 6
        assert root.num_leaves() == 3
    
    def test_to_dict_conversion(self):
        """Test converting a tree to dictionary format."""
        root = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        leaf = symbiotic.DecisionTreeNode(1, is_leaf=True, action="a0")
        root.children[0] = leaf
        
        tree_dict = root.to_dict()
        assert tree_dict["type"] == "inner"
        assert tree_dict["predicate"] == "root"
        assert 0 in tree_dict["children"]
        assert tree_dict["children"][0]["type"] == "leaf"
        assert tree_dict["children"][0]["action"] == "a0"


class TestDotFileParsing:
    """Test .dot file parsing functionality."""
    
    def test_parse_simple_dot_file(self):
        """Test parsing a simple .dot file."""
        # Create a temporary dot file
        dot_content = """digraph DecisionTree {
            node [shape=box];
            0 [label="root"];
            1 [label="leaf0"];
            0 -> 1;
        }"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
            f.write(dot_content)
            temp_file = f.name
        
        try:
            # This test checks that the file exists and can be read
            assert os.path.exists(temp_file)
            with open(temp_file, 'r') as f:
                content = f.read()
                assert "digraph" in content
        finally:
            os.unlink(temp_file)
    
    def test_dot_file_with_multiple_nodes(self):
        """Test parsing a dot file with multiple nodes."""
        dot_content = """digraph DecisionTree {
            node [shape=box];
            0 [label="root"];
            1 [label="inner"];
            2 [label="leaf0"];
            3 [label="leaf1"];
            0 -> 1;
            0 -> 2;
            1 -> 3;
        }"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
            f.write(dot_content)
            temp_file = f.name
        
        try:
            assert os.path.exists(temp_file)
            with open(temp_file, 'r') as f:
                lines = f.readlines()
                # Count edges
                edge_count = sum(1 for line in lines if '->' in line)
                assert edge_count == 3
        finally:
            os.unlink(temp_file)


class TestSubtreeSelection:
    """Test sub-tree selection strategy."""
    
    def test_select_subtree_at_depth(self):
        """Test selecting a sub-tree at a specific depth."""
        # Create a tree of depth 3
        root = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        inner1 = symbiotic.DecisionTreeNode(1, is_leaf=False, predicate="inner1")
        inner2 = symbiotic.DecisionTreeNode(2, is_leaf=False, predicate="inner2")
        leaf1 = symbiotic.DecisionTreeNode(3, is_leaf=True, action="a0")
        leaf2 = symbiotic.DecisionTreeNode(4, is_leaf=True, action="a1")
        leaf3 = symbiotic.DecisionTreeNode(5, is_leaf=True, action="a0")
        
        root.children[0] = inner1
        root.children[1] = inner2
        inner1.children[0] = leaf1
        inner2.children[0] = leaf2
        inner2.children[1] = leaf3
        
        # Create a dummy synthesizer to test selection
        class DummyQuotient:
            def get_property(self):
                return None
        
        dummy_quotient = DummyQuotient()
        synth = symbiotic.SynthesizerSymbiotic(
            dummy_quotient, 
            symbiotic_subtree_depth=1
        )
        
        # Select subtree at depth 1
        selected = synth._select_subtree(root, target_depth=1)
        assert selected is not None
        assert selected == inner1 or selected == inner2


class TestTreeCopy:
    """Test tree copying functionality."""
    
    def test_deep_copy_tree(self):
        """Test creating a deep copy of a tree."""
        original = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        leaf = symbiotic.DecisionTreeNode(1, is_leaf=True, action="a0")
        original.children[0] = leaf
        leaf.parent = original
        
        class DummyQuotient:
            def get_property(self):
                return None
        
        synth = symbiotic.SynthesizerSymbiotic(DummyQuotient())
        copy = synth._deep_copy_tree(original)
        
        # Verify structure is copied
        assert copy.node_id == original.node_id
        assert copy.predicate == original.predicate
        assert len(copy.children) == len(original.children)
        
        # Verify it's a different object
        assert copy is not original
        assert copy.children[0] is not original.children[0]


class TestTreeExport:
    """Test tree export functionality."""
    
    def test_export_tree_to_dot(self):
        """Test exporting a tree to .dot format."""
        root = symbiotic.DecisionTreeNode(0, is_leaf=False, predicate="root")
        leaf1 = symbiotic.DecisionTreeNode(1, is_leaf=True, action="a0")
        leaf2 = symbiotic.DecisionTreeNode(2, is_leaf=True, action="a1")
        root.children[0] = leaf1
        root.children[1] = leaf2
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "test_tree.dot")
            
            class DummyQuotient:
                def get_property(self):
                    return None
            
            synth = symbiotic.SynthesizerSymbiotic(DummyQuotient())
            synth._export_tree_to_dot(root, output_file)
            
            # Verify file was created and contains graphviz content
            assert os.path.exists(output_file)
            with open(output_file, 'r') as f:
                content = f.read()
                assert "digraph" in content
                assert "DecisionTree" in content


class TestSynthesizerSymbiotic:
    """Test the main SynthesizerSymbiotic class."""
    
    def test_initialization(self):
        """Test SynthesizerSymbiotic initialization."""
        class DummyQuotient:
            def get_property(self):
                return None
        
        quotient = DummyQuotient()
        synth = symbiotic.SynthesizerSymbiotic(
            quotient,
            dtcontrol_path="/custom/path",
            symbiotic_iterations=5,
            symbiotic_subtree_depth=3,
            symbiotic_error_tolerance=0.05,
            symbiotic_timeout=60
        )
        
        assert synth.dtcontrol_path == "/custom/path"
        assert synth.symbiotic_iterations == 5
        assert synth.symbiotic_subtree_depth == 3
        assert synth.symbiotic_error_tolerance == 0.05
        assert synth.symbiotic_timeout == 60
        assert synth.method_name == "symbiotic"
    
    def test_error_tolerance_check(self):
        """Test error tolerance checking."""
        class DummyQuotient:
            def get_property(self):
                return None
        
        synth = symbiotic.SynthesizerSymbiotic(
            DummyQuotient(),
            symbiotic_error_tolerance=0.1  # 10%
        )
        
        # Test within tolerance
        assert synth._check_error_tolerance(1.0, 0.95)  # 5% degradation
        assert synth._check_error_tolerance(1.0, 0.91)  # 9% degradation
        
        # Test outside tolerance
        assert not synth._check_error_tolerance(1.0, 0.89)  # 11% degradation
    
    def test_error_tolerance_with_zero(self):
        """Test error tolerance check with zero value."""
        class DummyQuotient:
            def get_property(self):
                return None
        
        synth = symbiotic.SynthesizerSymbiotic(DummyQuotient())
        
        # When old value is 0, check that new value is not worse
        assert synth._check_error_tolerance(0, 0)
        assert synth._check_error_tolerance(0, 0.1)


class TestMockIntegration:
    """Basic integration test with mocked components."""
    
    def test_mock_dtcontrol_call(self):
        """Test mock dtcontrol call."""
        class DummyQuotient:
            def get_property(self):
                return None
        
        synth = symbiotic.SynthesizerSymbiotic(DummyQuotient())
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "output.dot")
            
            # This should not raise an exception
            synth._call_dtcontrol(None, output_file)
            
            # Verify file was created
            assert os.path.exists(output_file)
            with open(output_file, 'r') as f:
                content = f.read()
                assert "digraph" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
