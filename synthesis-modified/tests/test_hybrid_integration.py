"""
Integration tests for hybrid synthesis.

End-to-end tests for the complete hybrid synthesis pipeline.
"""

import pytest
import logging
import os
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the synthesis-modified directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hybrid_synthesis import HybridSynthesizer, DtcontrolExecutor

logger = logging.getLogger(__name__)


class TestDtcontrolExecutor:
    """Tests for DTCONTROL executor."""
    
    def test_is_dtcontrol_available(self):
        """Test checking if dtcontrol is available."""
        # This test will pass or fail depending on system setup
        result = DtcontrolExecutor.is_dtcontrol_available()
        assert isinstance(result, bool)
    
    @patch('subprocess.run')
    def test_run_dtcontrol_success(self, mock_run):
        """Test successful dtcontrol execution."""
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
    
    @patch('subprocess.run')
    def test_run_dtcontrol_failure(self, mock_run):
        """Test dtcontrol execution failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error"
        )
        
        result = DtcontrolExecutor.run_dtcontrol(
            "model.prism",
            "model.props"
        )
        
        assert result is None
    
    @patch('subprocess.run')
    def test_run_dtcontrol_timeout(self, mock_run):
        """Test dtcontrol timeout."""
        mock_run.side_effect = TimeoutError()
        
        result = DtcontrolExecutor.run_dtcontrol(
            "model.prism",
            "model.props",
            timeout=1
        )
        
        assert result is None


class TestHybridSynthesizer:
    """Tests for the hybrid synthesizer."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for test outputs."""
        return str(tmp_path)
    
    @pytest.fixture
    def test_model_files(self, tmp_path):
        """Create dummy model and properties files for testing."""
        model_path = tmp_path / "model.prism"
        model_path.write_text("dtmc\n s0=1: true;\nendmodule")
        
        props_path = tmp_path / "model.props"
        props_path.write_text("P=? [F goal]")
        
        return str(model_path), str(props_path)
    
    def test_synthesizer_initialization(self, temp_dir, test_model_files):
        """Test initializing the hybrid synthesizer."""
        model_path, props_path = test_model_files
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir,
            enable_hybridization=False
        )
        
        assert synth.model_path == model_path
        assert synth.properties_path == props_path
        assert os.path.isdir(temp_dir)
    
    def test_synthesizer_parameters(self, temp_dir, test_model_files):
        """Test synthesizer with custom parameters."""
        model_path, props_path = test_model_files
        
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
    
    def test_time_remaining(self, temp_dir, test_model_files):
        """Test time remaining calculation."""
        model_path, props_path = test_model_files
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir,
            timeout=100
        )
        
        # Before starting
        remaining = synth._time_remaining()
        assert remaining == 100
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    def test_generate_initial_tree(self, mock_dtcontrol, temp_dir, test_model_files):
        """Test generating initial tree with dtcontrol."""
        model_path, props_path = test_model_files
        
        mock_dot = "digraph { node0 [label=\"x<=5\"]; }"
        mock_dtcontrol.return_value = mock_dot
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir
        )
        synth.start_time = 0  # Mock start time
        
        result = synth._generate_initial_tree()
        
        assert result == mock_dot
        assert synth.refinement_stats['dtcontrol_calls'] == 1
        assert synth.refinement_stats['dtcontrol_successes'] == 1
        
        # Check that DOT file was saved
        dot_file = os.path.join(temp_dir, "initial_tree.dot")
        assert os.path.exists(dot_file)
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    def test_generate_initial_tree_failure(self, mock_dtcontrol, temp_dir, test_model_files):
        """Test handling of dtcontrol failure."""
        model_path, props_path = test_model_files
        
        mock_dtcontrol.return_value = None
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir
        )
        synth.start_time = 0
        
        result = synth._generate_initial_tree()
        
        assert result is None
        assert synth.refinement_stats['dtcontrol_calls'] == 1
        assert synth.refinement_stats['dtcontrol_successes'] == 0
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    def test_extract_and_refine_subproblems_disabled(self, mock_dtcontrol, temp_dir, test_model_files):
        """Test sub-problem extraction with hybridization disabled."""
        model_path, props_path = test_model_files
        
        mock_dot = "digraph { node0 [label=\"x<=5\"]; }"
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir,
            enable_hybridization=False
        )
        
        result = synth._extract_and_refine_subproblems(mock_dot)
        
        assert result is True
        assert synth.optimized_tree == mock_dot
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    def test_save_results(self, mock_dtcontrol, temp_dir, test_model_files):
        """Test saving synthesis results."""
        model_path, props_path = test_model_files
        
        mock_dot = "digraph { node0 [label=\"x<=5\"]; }"
        
        synth = HybridSynthesizer(
            model_path=model_path,
            properties_path=props_path,
            output_dir=temp_dir
        )
        synth.start_time = 0
        synth.optimized_tree = mock_dot
        
        synth.save_results()
        
        # Check final tree file
        final_tree = os.path.join(temp_dir, "final_tree.dot")
        assert os.path.exists(final_tree)
        
        with open(final_tree) as f:
            content = f.read()
        assert content == mock_dot
        
        # Check stats file
        stats_file = os.path.join(temp_dir, "synthesis_stats.json")
        assert os.path.exists(stats_file)
        
        with open(stats_file) as f:
            stats = json.load(f)
        assert 'total_time' in stats
        assert 'refinement_stats' in stats


class TestEndToEndMockExecution:
    """End-to-end tests with mocked external tools."""
    
    @patch('hybrid_synthesis.DtcontrolExecutor.run_dtcontrol')
    def test_full_pipeline_mock(self, mock_dtcontrol, tmp_path):
        """Test the complete pipeline with mocked dtcontrol."""
        # Setup
        model_path = tmp_path / "model.prism"
        model_path.write_text("dtmc\n")
        
        props_path = tmp_path / "model.props"
        props_path.write_text("P=?[F goal]")
        
        output_dir = tmp_path / "output"
        
        mock_dot = """
        digraph DecisionTree {
            node0 [label="x <= 5", shape=box];
            node1 [label="action_a", shape=ellipse];
            node2 [label="action_b", shape=ellipse];
            node0 -> node1 [label="true"];
            node0 -> node2 [label="false"];
        }
        """
        mock_dtcontrol.return_value = mock_dot
        
        # Run
        synth = HybridSynthesizer(
            model_path=str(model_path),
            properties_path=str(props_path),
            output_dir=str(output_dir),
            enable_hybridization=False,
            timeout=10
        )
        
        success = synth.run()
        
        # Verify
        assert success is True
        assert os.path.exists(str(output_dir / "final_tree.dot"))
        assert os.path.exists(str(output_dir / "synthesis_stats.json"))
        assert synth.refinement_stats['dtcontrol_successes'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
