"""
Test suite for DtcontrolWrapper class.

Tests include:
- Binary verification
- Scheduler file writing
- Tree generation with mocked subprocess
- Result validation
- Preset comparison
- Error handling
"""

import pytest
import os
import json
import tempfile
from unittest import mock

from paynt.synthesizer.dtcontrol_wrapper import DtcontrolWrapper, DtcontrolResult


class TestDtcontrolResult:
    """Test DtcontrolResult class."""
    
    def test_success_result(self):
        """Test creating a successful result."""
        tree_data = {"type": "decision_tree", "root": {"type": "leaf"}}
        result = DtcontrolResult(success=True, tree_data=tree_data)
        
        assert result.success
        assert result.tree_data == tree_data
        assert result.validate()
    
    def test_failed_result(self):
        """Test creating a failed result."""
        result = DtcontrolResult(success=False, error_msg="Test error")
        
        assert not result.success
        assert result.error_msg == "Test error"
        assert not result.validate()
    
    def test_empty_tree_validation(self):
        """Test that empty tree fails validation."""
        result = DtcontrolResult(success=True, tree_data={})
        
        assert not result.validate()
    
    def test_tree_stats_simple(self):
        """Test extracting stats from a simple tree."""
        tree_data = {
            "root": {
                "type": "node",
                "children": [
                    {"type": "leaf"},
                    {"type": "leaf"}
                ]
            }
        }
        result = DtcontrolResult(success=True, tree_data=tree_data)
        
        stats = result.get_tree_stats()
        assert stats["total_nodes"] == 3  # root + 2 leaves
        assert stats["leaf_nodes"] == 2
        assert stats["decision_nodes"] == 1
    
    def test_result_repr(self):
        """Test result string representation."""
        result = DtcontrolResult(success=True)
        assert "SUCCESS" in repr(result)
        
        result = DtcontrolResult(success=False)
        assert "FAILED" in repr(result)


class TestDtcontrolWrapper:
    """Test DtcontrolWrapper class."""
    
    def test_wrapper_initialization(self):
        """Test wrapper initialization."""
        wrapper = DtcontrolWrapper(dtcontrol_path="dtcontrol", timeout=120)
        
        assert wrapper.dtcontrol_path == "dtcontrol"
        assert wrapper.timeout == 120
    
    def test_write_scheduler_dict(self):
        """Test writing scheduler from dict."""
        wrapper = DtcontrolWrapper()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scheduler.json")
            scheduler = {"states": [0, 1, 2], "choices": [[0], [1], [0, 1]]}
            
            wrapper._write_scheduler_file(scheduler, output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                data = json.load(f)
            assert data == scheduler
    
    def test_write_scheduler_json_string(self):
        """Test writing scheduler from JSON string."""
        wrapper = DtcontrolWrapper()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scheduler.json")
            scheduler_str = '{"test": "data"}'
            
            wrapper._write_scheduler_file(scheduler_str, output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                data = json.load(f)
            assert data == {"test": "data"}
    
    def test_write_scheduler_file_path(self):
        """Test writing scheduler from file path."""
        wrapper = DtcontrolWrapper()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source file
            source_path = os.path.join(temp_dir, "source.json")
            with open(source_path, 'w') as f:
                json.dump({"source": "data"}, f)
            
            # Write to output
            output_path = os.path.join(temp_dir, "output.json")
            wrapper._write_scheduler_file(source_path, output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                data = json.load(f)
            assert data == {"source": "data"}
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_generate_tree_success(self, mock_run):
        """Test successful tree generation with mocked dtcontrol."""
        wrapper = DtcontrolWrapper()
        
        # Mock dtcontrol execution
        def mock_subprocess_run(*args, **kwargs):
            cwd = kwargs.get('cwd', '.')
            
            # Create expected directory structure
            output_dir = os.path.join(cwd, "decision_trees", "default", "scheduler")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create tree output
            tree_data = {
                "type": "decision_tree",
                "root": {
                    "type": "node",
                    "test": "s0 < 5",
                    "children": [
                        {"type": "leaf", "action": "a0"},
                        {"type": "leaf", "action": "a1"}
                    ]
                }
            }
            
            output_path = os.path.join(output_dir, "default.json")
            with open(output_path, 'w') as f:
                json.dump(tree_data, f)
            
            # Return mock result
            result = mock.Mock()
            result.returncode = 0
            result.stdout = "dtcontrol success"
            result.stderr = ""
            return result
        
        mock_run.side_effect = mock_subprocess_run
        
        # Test generation
        scheduler = {"test": "scheduler"}
        result = wrapper.generate_tree_from_scheduler(scheduler)
        
        assert result.success
        assert result.tree_data is not None
        assert result.tree_data["type"] == "decision_tree"
        assert result.validate()
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_generate_tree_failure(self, mock_run):
        """Test failed tree generation."""
        wrapper = DtcontrolWrapper()
        
        # Mock dtcontrol failure
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "dtcontrol error"
        mock_run.return_value = mock_result
        
        # Test generation
        scheduler = {"test": "scheduler"}
        result = wrapper.generate_tree_from_scheduler(scheduler)
        
        assert not result.success
        assert result.error_msg
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_generate_tree_timeout(self, mock_run):
        """Test tree generation timeout."""
        wrapper = DtcontrolWrapper(timeout=1)
        
        # Mock timeout
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("dtcontrol", 1)
        
        # Test generation
        scheduler = {"test": "scheduler"}
        result = wrapper.generate_tree_from_scheduler(scheduler)
        
        assert not result.success
        assert "timeout" in result.error_msg.lower()
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_binary_verification(self, mock_run):
        """Test binary verification."""
        # Mock successful version check
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "dtcontrol version 1.0"
        mock_run.return_value = mock_result
        
        wrapper = DtcontrolWrapper()
        assert wrapper.verify_binary()
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_binary_not_found(self, mock_run):
        """Test binary not found."""
        mock_run.side_effect = FileNotFoundError("dtcontrol not found")
        
        wrapper = DtcontrolWrapper()
        assert not wrapper.verify_binary()
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_compare_presets(self, mock_run):
        """Test comparing multiple presets."""
        wrapper = DtcontrolWrapper()
        
        def mock_subprocess_run(*args, **kwargs):
            cwd = kwargs.get('cwd', '.')
            
            # Get the preset from command args
            cmd = args[0]
            preset_idx = cmd.index("--use-preset") + 1 if "--use-preset" in cmd else None
            preset = cmd[preset_idx] if preset_idx else "default"
            
            # Create output structure
            output_dir = os.path.join(cwd, "decision_trees", preset, "scheduler")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create tree with varying sizes based on preset
            depth_map = {"default": 3, "gini": 2, "entropy": 4, "maxminority": 3}
            depth = depth_map.get(preset, 3)
            
            tree_data = {
                "type": "decision_tree",
                "root": {
                    "type": "node",
                    "depth": depth,
                    "children": [{"type": "leaf"} for _ in range(depth)]
                }
            }
            
            output_path = os.path.join(output_dir, f"{preset}.json")
            with open(output_path, 'w') as f:
                json.dump(tree_data, f)
            
            result = mock.Mock()
            result.returncode = 0
            result.stdout = f"dtcontrol {preset} success"
            result.stderr = ""
            return result
        
        mock_run.side_effect = mock_subprocess_run
        
        scheduler = {"test": "scheduler"}
        results = wrapper.compare_presets(scheduler)
        
        assert len(results) == 4
        assert all(r.success for r in results.values())
    
    @mock.patch('paynt.synthesizer.dtcontrol_wrapper.subprocess.run')
    def test_get_best_preset(self, mock_run):
        """Test selecting best preset."""
        wrapper = DtcontrolWrapper()
        
        def mock_subprocess_run(*args, **kwargs):
            cwd = kwargs.get('cwd', '.')
            cmd = args[0]
            preset_idx = cmd.index("--use-preset") + 1 if "--use-preset" in cmd else None
            preset = cmd[preset_idx] if preset_idx else "default"
            
            output_dir = os.path.join(cwd, "decision_trees", preset, "scheduler")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create trees with different node counts
            node_counts = {"default": 10, "gini": 5, "entropy": 8, "maxminority": 12}
            num_nodes = node_counts.get(preset, 10)
            
            tree_data = {
                "type": "decision_tree",
                "root": {
                    "type": "node",
                    "children": [{"type": "leaf"} for _ in range(num_nodes)]
                }
            }
            
            output_path = os.path.join(output_dir, f"{preset}.json")
            with open(output_path, 'w') as f:
                json.dump(tree_data, f)
            
            result = mock.Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result
        
        mock_run.side_effect = mock_subprocess_run
        
        scheduler = {"test": "scheduler"}
        results = wrapper.compare_presets(scheduler)
        
        # gini should have smallest tree
        best = wrapper.get_best_preset(results, metric="total_nodes")
        assert best == "gini"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
