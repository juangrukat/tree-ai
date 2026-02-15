#!/usr/bin/env python3
"""
Folder Context Analyzer - Recursively analyzes a folder structure using AI

This script:
1. Recursively lists files in a directory
2. Generates a file tree structure
3. Analyzes each file using OpenAI API
4. Compiles results into file_tree_structure.md

Usage: python analyze_folder.py [target_directory]
"""

import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import fnmatch

# Import checkpoint module for crash recovery
from checkpoint import (
    init_checkpoint,
    get_completed_files,
    save_file_result,
    mark_completed,
    cleanup_checkpoint,
    get_progress
)

# Load environment variables from .env file
load_dotenv()

# Load configuration from config.json
def load_config() -> dict:
    """Load configuration from config.json file"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json file not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing config.json: {str(e)}")
        sys.exit(1)

config = load_config()

# Load .gitignore patterns if available
def load_gitignore(start_path: str) -> list:
    """Load .gitignore patterns from target directory if exists"""
    gitignore_path = Path(start_path) / ".gitignore"
    patterns = []
    if gitignore_path.exists() and config["analysis"]["use_gitignore"]:
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
            print(f"Loaded {len(patterns)} ignore patterns from .gitignore")
        except Exception as e:
            print(f"Warning: Failed to read .gitignore: {str(e)}")
    return patterns

# Check if file matches any ignore patterns
def is_ignored(file_path: str, start_path: str, patterns: list) -> bool:
    """Check if a file should be ignored based on patterns"""
    relative_path = os.path.relpath(file_path, start_path)
    for pattern in patterns:
        if fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(os.path.basename(relative_path), pattern):
            return True
        if pattern.endswith('/') and os.path.dirname(relative_path).startswith(pattern.rstrip('/')):
            return True
    return False

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def read_prompt() -> str:
    """Read the prompt from prompt file specified in config"""
    prompt_file = config["analysis"]["prompt_file"]
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: {prompt_file} file not found")
        sys.exit(1)


def generate_file_tree(start_path: str, gitignore_patterns: list) -> str:
    """Generate a tree representation of the directory structure"""
    tree = []
    start_path = Path(start_path).resolve()
    
    for root, dirs, files in os.walk(start_path):
        # Remove excluded directories
        dirs[:] = [
            d for d in dirs 
            if not (config["analysis"]["exclude_hidden"] and d.startswith('.')) 
            and d not in config["analysis"]["exclude_dirs"]
            and not is_ignored(os.path.join(root, d), start_path, gitignore_patterns)
        ]
        
        # Get relative paths
        relative_root = Path(root).relative_to(start_path)
        depth = len(relative_root.parts)
        
        # Add directory to tree (only if it's not the root)
        if relative_root != Path('.'):
            tree.append('|   ' * depth + f'|-- {relative_root.name}/')
            
        # Add files to tree
        for file_name in sorted(files):
            file_path = os.path.join(root, file_name)
            # Skip excluded files
            if (config["analysis"]["exclude_hidden"] and file_name.startswith('.')) or \
               file_name in config["analysis"]["exclude_files"] or \
               is_ignored(file_path, start_path, gitignore_patterns):
                continue
            tree.append('|   ' * (depth + 1) + f'|-- {file_name}')
    
    return '\n'.join(tree)


def analyze_file(file_path: str, prompt: str) -> dict:
    """Analyze a single file using OpenAI API"""
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip empty files
        if not content.strip():
            return {
                'explication': 'Empty file',
                'content': ''
            }
        
        # Limit content size for very large files
        max_length = config["openai"]["max_content_length"]
        if len(content) > max_length:
            content = content[:max_length] + '\n\n[Content truncated due to size]'
        
        # Use the OpenAI Chat Completions API
        response = client.chat.completions.create(
            model=config["openai"]["model"],
            messages=[
                {"role": "system", "content": config["system_prompt"]},
                {"role": "user", "content": f"{prompt}\n\nFile Path: {file_path}\n\nFile Content:\n```\n{content}\n```"}
            ],
            temperature=config["openai"]["temperature"],
            response_format={"type": config["openai"]["response_format"]}
        )
        
        # Parse response
        raw_response = response.choices[0].message.content
        
        # Debug: print raw response if it looks malformed
        if not raw_response or not raw_response.strip().startswith('{'):
            print(f"  Warning: Unexpected response format for {file_path}")
            print(f"  Raw response: {raw_response[:200] if raw_response else 'None'}...")
        
        try:
            analysis = json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"  JSON parse error for {file_path}: {str(e)}")
            print(f"  Raw response (first 500 chars): {raw_response[:500] if raw_response else 'None'}")
            return {
                'explication': f"Failed to parse AI response: {str(e)}",
                'content': content
            }
        
        return {
            'explication': analysis.get('explication', 'No explication provided'),
            'content': content
        }
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {str(e)}")
        return {
            'explication': f"Error analyzing file: {str(e)}",
            'content': ''
        }


def compile_results(start_path: str, file_tree: str, analysis_results: dict):
    """Compile all results into file_tree_structure.md"""
    output_path = Path(start_path) / config["output"]["filename"]
    
    with open(output_path, "w", encoding="utf-8") as f:
        # Write header
        f.write(f"# Folder Context Analysis\n\n")
        f.write(f"**Analysis Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Target Folder:** {start_path}\n")
        f.write(f"**AI Model:** {config['openai']['model']}\n\n")
        
        # Write file tree
        f.write("## File Tree Structure\n\n")
        f.write("```\n")
        f.write(file_tree)
        f.write("\n```\n\n")
        
        # Write file analyses
        f.write("## File\n\n")
        
        for file_path, analysis in sorted(analysis_results.items()):
            # Get relative path for display
            relative_path = Path(file_path).relative_to(start_path)
            
            f.write(f"<{relative_path}>\n\n")
            f.write(f"Explication:\n{analysis['explication']}\n\n")
            
            if analysis['content']:
                f.write("File Contents:\n```\n")
                f.write(analysis['content'])
                f.write(f"\n```\n</{relative_path}>\n\n")
            
            f.write("+++\n\n")
    
    print(f"Analysis complete. Results saved to: {output_path}")


def main():
    # Determine target directory
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
        if not os.path.isdir(target_dir):
            print(f"Error: {target_dir} is not a valid directory")
            sys.exit(1)
    else:
        target_dir = "."
    
    print(f"Analyzing folder: {os.path.abspath(target_dir)}")
    print(f"Using AI model: {config['openai']['model']}")
    
    # Load gitignore patterns
    gitignore_patterns = load_gitignore(target_dir)
    
    # Read prompt
    prompt = read_prompt()
    
    # Generate file tree
    print("Generating file tree...")
    file_tree = generate_file_tree(target_dir, gitignore_patterns)
    
    # Collect files to analyze
    files_to_analyze = []
    for root, dirs, files in os.walk(target_dir):
        # Skip excluded directories
        dirs[:] = [
            d for d in dirs 
            if not (config["analysis"]["exclude_hidden"] and d.startswith('.')) 
            and d not in config["analysis"]["exclude_dirs"]
            and not is_ignored(os.path.join(root, d), target_dir, gitignore_patterns)
        ]
        
        for file_name in files:
            file_path = os.path.join(root, file_name)
            # Skip excluded files
            if (config["analysis"]["exclude_hidden"] and file_name.startswith('.')) or \
               file_name in config["analysis"]["exclude_files"] or \
               is_ignored(file_path, target_dir, gitignore_patterns):
                continue
                
            files_to_analyze.append(file_path)
    
    # Check for existing checkpoint and load completed files
    checkpoint_folder = config["output"].get("checkpoint_folder", ".tree-ai")
    completed_files, analysis_results = get_completed_files(target_dir, checkpoint_folder)
    
    if completed_files:
        print(f"Loading previous progress... {len(completed_files)} files already completed")
    
    # Filter out already completed files
    files_to_process = [f for f in files_to_analyze if f not in completed_files]
    
    # Initialize checkpoint if starting fresh
    if not completed_files:
        init_checkpoint(target_dir, len(files_to_analyze), config["openai"]["model"], checkpoint_folder)
    
    print(f"Found {len(files_to_analyze)} files to analyze ({len(files_to_process)} remaining)")
    
    delay = config["analysis"]["delay_between_requests"]
    for i, file_path in enumerate(files_to_process, 1):
        relative_path = os.path.relpath(file_path, target_dir)
        completed_count = len(completed_files)
        print(f"Analyzing file {completed_count + i}/{len(files_to_analyze)}: {relative_path}")
        
        analysis = analyze_file(file_path, prompt)
        analysis_results[file_path] = analysis
        
        # Save checkpoint after each file
        save_file_result(target_dir, file_path, analysis, checkpoint_folder)
        
        # Add delay to avoid rate limits
        time.sleep(delay)
    
    # Mark checkpoint as completed
    mark_completed(target_dir, checkpoint_folder)
    
    # Compile results
    compile_results(target_dir, file_tree, analysis_results)
    
    # Cleanup checkpoint if configured
    if config["output"].get("cleanup_checkpoint", True):
        cleanup_checkpoint(target_dir, checkpoint_folder)


if __name__ == "__main__":
    main()