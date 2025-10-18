"""
Standalone integration tests for hybrid synthesis.

Tests that can run without full payntbind build using mocks.
"""

import pytest
import logging
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the synthesis-modified directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)


class TestDtcontrolExecutorMocked:
    """Tests for DTCONTROL executor using mocks."""
    
    @patch('subprocess.run')
    def test_run_dtcontrol_success(self, mock_run):
        """Test successful dtcontrol execution."""
        # Import here to avoid early loading
        from hybrid_synthesis import DtcontrolExecutor
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="digraph { node0 -> node1; }",
            stderr=""
        )
        
        result = DtcontrolExecutor.run_dtcontrol(
            "model.prism",
            "model.props"
        )
        
        assert result is not None
        assert "digraph" in result
        assert "node0" in result
    
    @patch('subprocess.run')
    def test_run_dtcontrol_failure(self, mock_run):
        """Test dtcontrol execution failure."""
        from hybrid_synthesis import DtcontrolExecutor
        
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: Model file not found"
        )
        
        result = DtcontrolExecutor.run_dtcontrol(
            "nonexistent.prism",
            "nonexistent.props"
        )
        
        assert result is None
    
    @patch('subprocess.run')
    def test_run_dtcontrol_timeout(self, mock_run):
        """Test dtcontrol timeout handling."""
        from hybrid_synthesis import DtcontrolExecutor
        
        mock_run.side_effect = TimeoutError()
        
        result = DtcontrolExecutor.run_dtcontrol(
            "model.prism",
            "model.props",
            timeout=1
        )
        
        assert result is None


class TestHybridSynthesizerInitialization:
    """Tests for HybridSynthesizer initialization."""
    
    @patch('hybrid_synthesis.DtcontrolExecutor')
    @patch('hybrid_synthesis.SynthesizerAR')
    def test_synthesizer_initialization(self, mock_synthesizer, mock_executor):
        """Test initializing the hybrid synthesizer."""
        from hybrid_synthesis import HybridSynthesizer
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "model.prism")
            props_path = os.path.join(temp_dir, "model.props")
            
            # Create dummy files
            Path(model_path).write_text("dtmc\n s0=1: true;\nendmodule")
            Path(props_path).write_text("P=? [F goal]")
            
            synth = HybridSynthesizer(
                model_path=model_path,
                properties_path=props_path,
                output_dir=temp_dir,
                enable_hybridization=False
            )
            
            assert synth.model_path == model_path
            assert synth.properties_path == props_path
            assert synth.enable_hybridization is False
    
    @patch('hybrid_synthesis.DtcontrolExecutor')
    @patch('hybrid_synthesis.SynthesizerAR')
    def test_synthesizer_with_parameters(self, mock_synthesizer, mock_executor):
        """Test synthesizer with custom parameters."""
        from hybrid_synthesis import HybridSynthesizer
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "model.prism")
            props_path = os.path.join(temp_dir, "model.props")
            
            Path(model_path).write_text("dtmc\n s0=1: true;\nendmodule")
            Path(props_path).write_text("P=? [F goal]")
            
            synth = HybridSynthesizer(
                model_path=model_path,
                properties_path=props_path,
                output_dir=temp_dir,
                max_subtree_depth=5,
                max_loss=0.1,
                timeout=1800,
                enable_hybridization=True
            )
            
            assert synth.max_subtree_depth == 5
            assert synth.max_loss == 0.1
            assert synth.timeout == 1800
            assert synth.enable_hybridization is True


class TestHybridSynthesizerPipeline:
    """Tests for hybrid synthesis pipeline."""
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    @patch('hybrid_synthesis.SynthesizerAR')
    def test_pipeline_initialization(self, mock_synthesizer, mock_dtcontrol):
        """Test that pipeline can initialize without crashing."""
        from hybrid_synthesis import HybridSynthesizer
        from paynt.parser.dot_parser import DotParser
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "model.prism")
            props_path = os.path.join(temp_dir, "model.props")
            
            Path(model_path).write_text("dtmc\n s0=1: true;\nendmodule")
            Path(props_path).write_text("P=? [F goal]")
            
            # Mock DTCONTROL output
            sample_dot = """
            digraph DecisionTree {
                node0 [label="x <= 5", shape=box];
                node1 [label="action_a", shape=ellipse];
                node2 [label="action_b", shape=ellipse];
                node0 -> node1 [label="true"];
                node0 -> node2 [label="false"];
            }
            """
            
            synth = HybridSynthesizer(
                model_path=model_path,
                properties_path=props_path,
                output_dir=temp_dir,
                enable_hybridization=True
            )
            
            # Verify pipeline state
            assert synth is not None
            assert os.path.exists(synth.output_dir)
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    @patch('hybrid_synthesis.SynthesizerAR')
    def test_time_tracking(self, mock_synthesizer, mock_dtcontrol):
        """Test timeout and timing tracking."""
        from hybrid_synthesis import HybridSynthesizer
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "model.prism")
            props_path = os.path.join(temp_dir, "model.props")
            
            Path(model_path).write_text("dtmc\n s0=1: true;\nendmodule")
            Path(props_path).write_text("P=? [F goal]")
            
            synth = HybridSynthesizer(
                model_path=model_path,
                properties_path=props_path,
                output_dir=temp_dir,
                timeout=60
            )
            
            # Time remaining should be approximately the timeout value
            remaining = synth._time_remaining()
            assert 50 < remaining <= 60  # Allow small time difference


class TestDotParserIntegration:
    """Integration tests for DOT parser with tree slicer."""
    
    def test_dot_to_tree_pipeline(self):
        """Test full DOT to tree extraction pipeline."""
        from paynt.parser.dot_parser import DotParser
        from paynt.utils.tree_slicer import TreeSlicer
        
        dot_input = """
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
        
        # Parse DOT
        parsed = DotParser.parse_dot(dot_input)
        assert parsed is not None
        assert len(parsed['nodes']) == 5
        
        # Build tree structure
        tree_struct = DotParser.build_tree_structure(parsed)
        assert tree_struct is not None
        assert tree_struct['root_id'] == 'node0'
        
        # Get tree statistics
        # Note: This would need DecisionTreeNode conversion in production
        assert tree_struct['children_map'] is not None


class TestPathConditionIntegration:
    """Integration tests for path conditions."""
    
    def test_path_condition_formatting(self):
        """Test path condition formatting for SMT constraints."""
        from paynt.utils.tree_slicer import PathCondition
        
        # Create a path condition
        decisions = [
            {'variable': 'x', 'operator': '<=', 'value': 5},
            {'variable': 'y', 'operator': '>', 'value': 3},
            {'variable': 'z', 'operator': '==', 'value': 10}
        ]
        
        path_cond = PathCondition(decisions=decisions)
        
        # Convert to string
        cond_str = path_cond.to_string()
        
        assert 'x' in cond_str
        assert '<=' in cond_str
        assert '5' in cond_str
        assert len(path_cond.decisions) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
