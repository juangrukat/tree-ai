#!/usr/bin/env python3
"""
Checkpoint management module for tree-ai

Provides functions to save and resume analysis progress,
enabling crash recovery and seamless re-runs.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

CHECKPOINT_VERSION = "1.0"


def _get_checkpoint_dir(target_dir: str, folder_name: str = ".tree-ai") -> Path:
    """Get the checkpoint directory path."""
    return Path(target_dir) / folder_name


def _get_checkpoint_file(target_dir: str, folder_name: str = ".tree-ai") -> Path:
    """Get the checkpoint file path."""
    return _get_checkpoint_dir(target_dir, folder_name) / "checkpoint.json"


def _get_results_dir(target_dir: str, folder_name: str = ".tree-ai") -> Path:
    """Get the results directory path."""
    return _get_checkpoint_dir(target_dir, folder_name) / "results"


def _get_file_hash(file_path: str) -> str:
    """Generate a hash for a file path to use in result filename."""
    return hashlib.md5(file_path.encode('utf-8')).hexdigest()


def _get_result_file_path(target_dir: str, file_path: str, folder_name: str = ".tree-ai") -> Path:
    """Get the result file path for a given source file."""
    file_hash = _get_file_hash(file_path)
    # Use relative path for cleaner filenames, fallback to hash
    try:
        rel_path = Path(file_path).relative_to(target_dir)
        safe_name = str(rel_path).replace('/', '_').replace('\\', '_')
        filename = f"{safe_name}_{file_hash[:8]}.json"
    except ValueError:
        filename = f"{file_hash}.json"
    return _get_results_dir(target_dir, folder_name) / filename


def init_checkpoint(target_dir: str, total_files: int, model: str, folder_name: str = ".tree-ai") -> None:
    """Initialize a new checkpoint for a fresh analysis run."""
    checkpoint_dir = _get_checkpoint_dir(target_dir, folder_name)
    results_dir = _get_results_dir(target_dir, folder_name)
    
    # Create directories
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint = {
        "version": CHECKPOINT_VERSION,
        "target_dir": str(Path(target_dir).resolve()),
        "started_at": datetime.utcnow().isoformat() + "Z",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_files": total_files,
        "completed_files": 0,
        "model": model,
        "status": "in_progress",
        "files": {}
    }
    
    _save_checkpoint_file(target_dir, checkpoint, folder_name)


def _save_checkpoint_file(target_dir: str, checkpoint: dict, folder_name: str = ".tree-ai") -> None:
    """Save checkpoint to disk using atomic write (temp file + rename)."""
    checkpoint_path = _get_checkpoint_file(target_dir, folder_name)
    temp_path = checkpoint_path.with_suffix('.tmp')
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)
        # Atomic rename to prevent corruption during write
        temp_path.replace(checkpoint_path)
    except Exception as e:
        # Clean up temp file if it exists
        if temp_path.exists():
            temp_path.unlink()
        raise e


def load_checkpoint(target_dir: str, folder_name: str = ".tree-ai") -> Optional[dict]:
    """Load existing checkpoint if it exists and is valid."""
    checkpoint_path = _get_checkpoint_file(target_dir, folder_name)
    
    if not checkpoint_path.exists():
        return None
    
    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
        
        # Validate checkpoint
        if checkpoint.get("version") != CHECKPOINT_VERSION:
            print(f"Warning: Checkpoint version mismatch, starting fresh")
            return None
        
        # Check if target directory matches
        resolved_target = str(Path(target_dir).resolve())
        if checkpoint.get("target_dir") != resolved_target:
            print(f"Warning: Checkpoint is for different directory, starting fresh")
            return None
        
        # Check if checkpoint is already completed
        if checkpoint.get("status") == "completed":
            return None
        
        return checkpoint
        
    except (json.JSONDecodeError, KeyError, IOError) as e:
        print(f"Warning: Failed to load checkpoint ({e}), starting fresh")
        return None


def save_file_result(target_dir: str, file_path: str, analysis: dict, 
                     folder_name: str = ".tree-ai") -> None:
    """Save the analysis result for a single file and update checkpoint."""
    # Save individual result file
    result_path = _get_result_file_path(target_dir, file_path, folder_name)
    result_data = {
        "file_path": file_path,
        "explication": analysis.get("explication", ""),
        "content": analysis.get("content", ""),
        "analyzed_at": datetime.utcnow().isoformat() + "Z"
    }
    
    # Atomic write for result file
    temp_path = result_path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2)
        temp_path.replace(result_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e
    
    # Update checkpoint
    checkpoint = load_checkpoint(target_dir, folder_name)
    if checkpoint:
        checkpoint["files"][file_path] = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "result_file": str(result_path.name)
        }
        checkpoint["completed_files"] = len(checkpoint["files"])
        checkpoint["last_updated"] = datetime.utcnow().isoformat() + "Z"
        _save_checkpoint_file(target_dir, checkpoint, folder_name)


def get_completed_files(target_dir: str, folder_name: str = ".tree-ai") -> Tuple[List[str], Dict[str, dict]]:
    """
    Get list of completed files and their analysis results.
    Returns: (completed_file_paths, analysis_results_dict)
    """
    checkpoint = load_checkpoint(target_dir, folder_name)
    if not checkpoint:
        return [], {}
    
    completed_files = []
    analysis_results = {}
    
    for file_path, file_info in checkpoint.get("files", {}).items():
        if file_info.get("status") == "completed":
            # Try to load the result file
            result_path = _get_result_file_path(target_dir, file_path, folder_name)
            try:
                if result_path.exists():
                    with open(result_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    analysis_results[file_path] = {
                        "explication": result_data.get("explication", ""),
                        "content": result_data.get("content", "")
                    }
                    completed_files.append(file_path)
                else:
                    # Result file missing, mark as not completed
                    print(f"Warning: Result file missing for {file_path}, will re-analyze")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load result for {file_path} ({e}), will re-analyze")
    
    return completed_files, analysis_results


def mark_completed(target_dir: str, folder_name: str = ".tree-ai") -> None:
    """Mark the checkpoint as completed."""
    checkpoint = load_checkpoint(target_dir, folder_name)
    if checkpoint:
        checkpoint["status"] = "completed"
        checkpoint["last_updated"] = datetime.utcnow().isoformat() + "Z"
        _save_checkpoint_file(target_dir, checkpoint, folder_name)


def cleanup_checkpoint(target_dir: str, folder_name: str = ".tree-ai") -> None:
    """Remove checkpoint files after successful completion."""
    checkpoint_dir = _get_checkpoint_dir(target_dir, folder_name)
    if checkpoint_dir.exists():
        import shutil
        try:
            shutil.rmtree(checkpoint_dir)
        except OSError as e:
            print(f"Warning: Failed to cleanup checkpoint directory: {e}")


def get_progress(target_dir: str, folder_name: str = ".tree-ai") -> Tuple[int, int]:
    """Get current progress (completed, total). Returns (0, 0) if no checkpoint."""
    checkpoint = load_checkpoint(target_dir, folder_name)
    if not checkpoint:
        return 0, 0
    return checkpoint.get("completed_files", 0), checkpoint.get("total_files", 0)
