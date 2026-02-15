# tree ai

A Python CLI tool that recursively analyzes folder structures and uses OpenAI's API to generate contextual explanations of each file's purpose and content.

## What It Does

tree ai walks through your project directory, generates a visual tree of the file structure, and uses OpenAI's GPT models to explain what each file does. The output is a single markdown file perfect for:

- **Onboarding** new team members to a codebase
- **Code review** by providing clear overviews of code structure
- **Documentation** by auto-generating codebase summaries
- **RAG pipelines** feeding code context to AI assistants

## Features

- **Recursive File Tree** — Visual directory structure with indentation
- **AI-Powered Explanations** — Each file gets a clear, concise explanation via OpenAI
- **Gitignore Aware** — Automatically skips files/dirs in your `.gitignore`
- **Configurable** — Exclude hidden files, specific patterns, or directories
- **Structured Output** — JSON-formatted AI responses for easy parsing
- **Rate Limiting** — Configurable delay between API calls to respect limits
- **Concurrent Processing** — Analyze multiple files simultaneously for faster results
- **Crash Recovery** — If interrupted, simply re-run the command to resume where you left off

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set your OpenAI key
echo "OPENAI_API_KEY=sk-..." > .env

# Run
python analyze_folder.py ~/Projects/my-app
```

Results are saved to `file_tree_structure.md` in the target directory.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd tree-ai
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Add your OpenAI API key:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your-api-key-here" > .env
   ```

## Usage

```bash
python analyze_folder.py [target_directory]
```

- If no directory is specified, analyzes the current directory.
- Output is saved to `file_tree_structure.md` in the target folder.

### Example

```bash
python analyze_folder.py ~/Projects/my-app
```

## Configuration

Edit `config.json` to customize behavior:

```json
{
  "openai": {
    "model": "gpt-4o-mini",
    "temperature": 1,
    "max_content_length": 4000,
    "response_format": "json_object"
  },
  "analysis": {
    "prompt_file": "prompt.txt",
    "delay_between_requests": 0.5,
    "use_gitignore": true,
    "exclude_files": ["file_tree_structure.md"],
    "exclude_dirs": ["__pycache__"],
    "exclude_hidden": true
  },
  "output": {
    "filename": "file_tree_structure.md"
  }
}
```

### Configuration Options

| Option | Description |
|--------|-------------|
| `model` | OpenAI model to use (e.g., `gpt-4o-mini`, `gpt-4o`) |
| `temperature` | Sampling temperature (1 = default for most models) |
| `max_content_length` | Maximum characters to analyze per file |
| `prompt_file` | File containing the analysis prompt |
| `delay_between_requests` | Seconds to wait between API calls |
| `max_concurrent_requests` | Number of concurrent API calls (default: 5) |
| `use_gitignore` | Whether to respect `.gitignore` patterns |
| `exclude_files` | Additional files to exclude |
| `exclude_dirs` | Directories to exclude from traversal |
| `exclude_hidden` | Skip hidden files/directories (starting with `.`) |

## Gitignore Integration

tree ai respects your `.gitignore` patterns automatically:

- **Auto-detection** — Looks for `.gitignore` in the target directory
- **Standard patterns** — Supports `*.pyc`, `venv/`, `__pycache__/`, etc.
- **Works with config** — Gitignore exclusions stack with config-based ones

### Supported Patterns

- `*.pyc` — File extension matches
- `__pycache__/` — Directory matches
- `venv/` — Full directory trees
- `*.swp` — Temporary file matches

### Limitations

- Negative patterns (`!`) are not supported
- Nested `.gitignore` files in subdirectories are not processed

## Output Format

The generated `file_tree_structure.md` looks like:

```markdown
# Folder Context Analysis

**Analysis Date:** 2026-02-15 15:49:05
**Target Folder:** /path/to/folder
**AI Model:** gpt-4o-mini

## File Tree Structure

```
|   |-- file1.md
|   |-- file2.py
```

## File

<file1.md>

Explication:
[AI-generated explanation of the file]

File Contents:
```
[Original file content]
```
</file1.md>
+++
```

## Crash Recovery

tree ai automatically saves progress to a hidden `.tree-ai/` folder. If the process is interrupted (power failure, internet drop, Ctrl+C), simply re-run the command and it will resume where it left off.

The checkpoint folder contains:
- `checkpoint.json` — Progress state and file statuses
- `results/` — Individual analysis results for each file

Progress is saved after each file is processed, ensuring minimal work is lost on interruption.

### How It Works

```bash
# First run - starts from scratch
$ python analyze_folder.py ~/Projects/my-app
Found 100 files to analyze
Analyzing file 1/100: src/main.py
Analyzing file 2/100: src/utils.py
... (interrupted)

# Re-run - automatically resumes
$ python analyze_folder.py ~/Projects/my-app
Found 100 files to analyze
Loading previous progress... 45 files already completed
Analyzing file 46/100: src/models.py
...
```

### Configuration

The checkpoint folder can be configured in `config.json`:

```json
{
  "output": {
    "filename": "file_tree_structure.md",
    "checkpoint_folder": ".tree-ai",
    "cleanup_checkpoint": true
  }
}
```

- `checkpoint_folder` — Name of the hidden folder (default: `.tree-ai`)
- `cleanup_checkpoint` — Remove checkpoint after successful completion (default: `true`)

## Project Files

- `analyze_folder.py` — Main analysis script
- `checkpoint.py` — Checkpoint management for crash recovery
- `config.json` — Configuration file
- `prompt.txt` — Analysis prompt template
- `requirements.txt` — Python dependencies
- `.env.example` — Environment variable template

## License

MIT License
