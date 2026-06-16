# AI Summary Report Generator

Generate beautiful HTML reports from Elasticsearch data using a local Ollama LLM. Ask questions in natural language and get back styled reports with charts, tables, and source citations.

## Quick Start

```bash
cd report_generator
pip install -r requirements.txt
python app.py
# Open http://localhost:5001
```

Requires:
- Elasticsearch running with your data indexed
- Ollama running with `llama3:8b-instruct-q8_0` (or change in `constants.py`)

## Project Structure

```
ai_summary/
├── constants.py              # Shared ES/Ollama config
├── scripts/
│   └── create_vec_index.py   # Vector index creation for ES
└── report_generator/
    ├── app.py                # Flask app (port 5001) + Swagger at /apidocs
    ├── rag_engine.py         # Core pipeline: 14+ intents, chunking, aggregation
    ├── report_renderer.py    # HTML report template
    ├── report_store.py       # Save/load reports
    ├── cli_generate.py       # CLI script for report generation
    ├── config.py             # Report generator config
    ├── requirements.txt      # flask, elasticsearch, requests, flasgger
    ├── templates/index.html  # Web UI
    ├── reports/              # Generated reports
    └── README.md             # Full documentation
```

## Features

- **14+ Intent Types** — enumeration, analysis, comparison, trends, predictions, etc.
- **Direct Enumeration** — "List all X" queries bypass the LLM entirely (fast)
- **Chunked LLM Processing** — large datasets processed in chunks then synthesized
- **Async Job API** — non-blocking report generation with polling
- **Swagger Docs** — interactive API docs at `/apidocs`
- **Source Citations** — every report cites supporting passages

See [report_generator/README.md](report_generator/README.md) for full documentation including API reference, intent types, and vector index setup.
