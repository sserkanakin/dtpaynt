"""
Wrapper class for dtcontrol interactions with validation and result verification.

This module provides a clean interface to dtcontrol with:
- Automatic input/output handling
- Result validation
- Error checking and reporting
- Logging and debugging support
"""

import os
import json
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class DtcontrolResult:
    """Result object from dtcontrol execution."""
    
    def __init__(self, success: bool, tree_data: Optional[Dict] = None, 
                 output_path: Optional[str] = None, stderr: str = "", 
                 stdout: str = "", error_msg: str = ""):
        self.success = success
        self.tree_data = tree_data
        self.output_path = output_path
        self.stderr = stderr
        self.stdout = stdout
        self.error_msg = error_msg
    
    def __repr__(self):
        status = "✓ SUCCESS" if self.success else "✗ FAILED"
        return f"DtcontrolResult({status}, tree_size={len(self.tree_data) if self.tree_data else 0} bytes)"
    
    def validate(self) -> bool:
        """Validate the result structure."""
        if not self.success:
            return False
        
        if not self.tree_data:
            logger.error("Tree data is empty")
            return False
        
        if not isinstance(self.tree_data, dict):
            logger.error("Tree data is not a dictionary")
            return False
        
        return True
    
    def get_tree_stats(self) -> Dict[str, Any]:
        """Extract statistics from the tree."""
        if not self.tree_data:
            return {}
        
        stats = {
            "total_nodes": 0,
            "leaf_nodes": 0,
            "decision_nodes": 0,
            "max_depth": 0,
            "raw_size_bytes": len(json.dumps(self.tree_data)),
        }
        
        def count_nodes(node, depth=0):
            if node is None:
                return
            
            stats["total_nodes"] += 1
            stats["max_depth"] = max(stats["max_depth"], depth)
            
            if isinstance(node, dict):
                if node.get("type") == "leaf":
                    stats["leaf_nodes"] += 1
                elif node.get("type") == "node":
                    stats["decision_nodes"] += 1
                    
                    for child in node.get("children", []):
                        count_nodes(child, depth + 1)
            elif isinstance(node, list):
                for child in node:
                    count_nodes(child, depth + 1)
        
        # Try to count from the root
        if "root" in self.tree_data:
            count_nodes(self.tree_data["root"])
        
        return stats


class DtcontrolWrapper:
    """Wrapper for dtcontrol subprocess calls with validation and error handling."""
    
    DEFAULT_TIMEOUT = 120
    DEFAULT_PRESET = "default"
    
    def __init__(self, dtcontrol_path: str = "dtcontrol", timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize the dtcontrol wrapper.
        
        Args:
            dtcontrol_path: Path to dtcontrol binary
            timeout: Timeout in seconds for dtcontrol execution
        """
        self.dtcontrol_path = dtcontrol_path
        self.timeout = timeout
        self.verify_binary()
    
    def verify_binary(self) -> bool:
        """Verify that dtcontrol binary is available."""
        try:
            result = subprocess.run(
                [self.dtcontrol_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"✓ dtcontrol verified: {result.stdout.strip()}")
                return True
            else:
                logger.warning(f"dtcontrol --version returned {result.returncode}")
                return False
        except FileNotFoundError:
            logger.error(f"✗ dtcontrol binary not found at: {self.dtcontrol_path}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"✗ dtcontrol --version timed out")
            return False
        except Exception as e:
            logger.error(f"✗ Error verifying dtcontrol: {e}")
            return False
    
    def generate_tree_from_scheduler(self, scheduler_json: Union[Dict, str], 
                                    preset: str = DEFAULT_PRESET,
                                    output_dir: Optional[str] = None) -> DtcontrolResult:
        """
        Generate a decision tree from a scheduler using dtcontrol.
        
        Args:
            scheduler_json: Scheduler as dict or JSON string or file path
            preset: dtcontrol preset to use (default, gini, entropy, maxminority)
            output_dir: Directory to save outputs (if None, uses temp dir)
        
        Returns:
            DtcontrolResult with the generated tree and metadata
        """
        temp_dir = None
        try:
            # Create working directory
            if output_dir is None:
                temp_dir = tempfile.mkdtemp(prefix="dtcontrol_")
                work_dir = temp_dir
            else:
                work_dir = output_dir
                os.makedirs(work_dir, exist_ok=True)
            
            logger.info(f"DtControl working directory: {work_dir}")
            
            # Write scheduler to file
            scheduler_path = os.path.join(work_dir, "scheduler.storm.json")
            self._write_scheduler_file(scheduler_json, scheduler_path)
            
            logger.info(f"Scheduler written to: {scheduler_path}")
            
            # Prepare and run dtcontrol command
            cmd = [
                self.dtcontrol_path,
                "--input", "scheduler.storm.json",
                "-r",  # Return decision tree
                "--use-preset", preset
            ]
            
            logger.info(f"Running dtcontrol: {' '.join(cmd)}")
            logger.debug(f"  working directory: {work_dir}")
            logger.debug(f"  timeout: {self.timeout}s")
            
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False  # Don't raise on non-zero return code yet
            )
            
            # Log output
            if result.stdout:
                logger.debug(f"dtcontrol stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"dtcontrol stderr:\n{result.stderr}")
            
            # Check if dtcontrol succeeded
            if result.returncode != 0:
                error_msg = f"dtcontrol failed with return code {result.returncode}"
                logger.error(error_msg)
                logger.error(f"stderr: {result.stderr}")
                return DtcontrolResult(
                    success=False,
                    stderr=result.stderr,
                    stdout=result.stdout,
                    error_msg=error_msg
                )
            
            # Read the generated tree
            tree_path = os.path.join(work_dir, "decision_trees", preset, "scheduler", f"{preset}.json")
            
            if not os.path.exists(tree_path):
                error_msg = f"dtcontrol did not produce expected output at {tree_path}"
                logger.error(error_msg)
                
                # List what was generated
                dt_dir = os.path.join(work_dir, "decision_trees")
                if os.path.exists(dt_dir):
                    logger.debug(f"Contents of decision_trees directory:")
                    for root, dirs, files in os.walk(dt_dir):
                        level = root.replace(dt_dir, '').count(os.sep)
                        indent = ' ' * 2 * level
                        logger.debug(f'{indent}{os.path.basename(root)}/')
                        subindent = ' ' * 2 * (level + 1)
                        for file in files:
                            logger.debug(f'{subindent}{file}')
                
                return DtcontrolResult(
                    success=False,
                    stderr=result.stderr,
                    stdout=result.stdout,
                    error_msg=error_msg
                )
            
            # Load the tree
            with open(tree_path, 'r') as f:
                tree_data = json.load(f)
            
            logger.info(f"✓ dtcontrol generated tree at: {tree_path}")
            
            # Create result object
            dtcontrol_result = DtcontrolResult(
                success=True,
                tree_data=tree_data,
                output_path=tree_path,
                stderr=result.stderr,
                stdout=result.stdout
            )
            
            # Validate result
            if dtcontrol_result.validate():
                stats = dtcontrol_result.get_tree_stats()
                logger.info(f"✓ Tree validation passed. Stats: {stats}")
            else:
                logger.warning("⚠ Tree validation failed")
            
            return dtcontrol_result
            
        except subprocess.TimeoutExpired:
            error_msg = f"dtcontrol timed out after {self.timeout}s"
            logger.error(error_msg)
            return DtcontrolResult(success=False, error_msg=error_msg)
        except FileNotFoundError as e:
            error_msg = f"dtcontrol binary not found: {e}"
            logger.error(error_msg)
            return DtcontrolResult(success=False, error_msg=error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse dtcontrol output: {e}"
            logger.error(error_msg)
            return DtcontrolResult(success=False, error_msg=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg, exc_info=True)
            return DtcontrolResult(success=False, error_msg=error_msg)
        finally:
            # Clean up temp directory if created
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up temp directory: {temp_dir}")
    
    def _write_scheduler_file(self, scheduler_data: Union[Dict, str], output_path: str) -> None:
        """Write scheduler data to file in the correct format."""
        with open(output_path, 'w') as f:
            if isinstance(scheduler_data, dict):
                json.dump(scheduler_data, f, indent=2)
            elif isinstance(scheduler_data, str):
                if scheduler_data.startswith('{'):
                    # It's JSON content
                    f.write(scheduler_data)
                else:
                    # It's a file path
                    with open(scheduler_data, 'r') as src:
                        f.write(src.read())
            else:
                raise ValueError(f"Unsupported scheduler data type: {type(scheduler_data)}")
    
    def compare_presets(self, scheduler_json: Union[Dict, str]) -> Dict[str, DtcontrolResult]:
        """
        Compare different dtcontrol presets on the same scheduler.
        
        Returns dict mapping preset name to DtcontrolResult.
        """
        presets = ["default", "gini", "entropy", "maxminority"]
        results = {}
        
        logger.info(f"Comparing {len(presets)} dtcontrol presets...")
        
        for preset in presets:
            logger.info(f"  Generating tree with preset: {preset}")
            result = self.generate_tree_from_scheduler(scheduler_json, preset=preset)
            results[preset] = result
            
            if result.success:
                stats = result.get_tree_stats()
                logger.info(f"    ✓ {preset}: {stats['total_nodes']} nodes, depth {stats['max_depth']}")
            else:
                logger.info(f"    ✗ {preset}: {result.error_msg}")
        
        return results
    
    def get_best_preset(self, results: Dict[str, DtcontrolResult], 
                       metric: str = "total_nodes") -> Optional[str]:
        """
        Find the best preset based on a metric.
        
        Args:
            results: Dictionary from compare_presets()
            metric: "total_nodes", "leaf_nodes", "max_depth", or "raw_size_bytes"
        
        Returns:
            Name of the best preset, or None if all failed
        """
        valid_results = {
            preset: result for preset, result in results.items() 
            if result.success
        }
        
        if not valid_results:
            logger.warning("No valid results to compare")
            return None
        
        stats_by_preset = {
            preset: result.get_tree_stats() 
            for preset, result in valid_results.items()
        }
        
        best_preset = min(
            stats_by_preset.keys(),
            key=lambda p: stats_by_preset[p].get(metric, float('inf'))
        )
        
        logger.info(f"Best preset by {metric}: {best_preset}")
        return best_preset
