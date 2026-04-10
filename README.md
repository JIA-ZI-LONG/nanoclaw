# nanoclaw - Modular Agent Framework

A clean, reusable agent framework with layered architecture.

## Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run REPL
python -m nanoclaw

# Or use the entry script
python run_nanoclaw.py
```

## Project Structure

```
nanoclaw/
├── core/           # Foundation layer (tools, schemas, compression)
├── coordination/   # State management (todos, tasks, skills)
├── execution/      # Agent spawning and background work
├── communication/  # Messaging and protocols
├── team/           # Teammate orchestration
├── agent.py        # Main agent loop
├── cli.py          # REPL entry
└── __main__.py     # Package entry point
```

## Environment Variables

Create `.env` file:
```
ANTHROPIC_BASE_URL=your_base_url
ANTHROPIC_AUTH_TOKEN=your_token
MODEL_ID=claude-sonnet-4-6
```