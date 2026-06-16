# AI Summary Report Generator

Generate beautiful HTML reports from Elasticsearch data using AI. Supports 14+ intent types including enumeration, analysis, comparison, trends, predictions, and more.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Web UI](#web-ui)
  - [API](#api)
  - [CLI](#cli)
- [Intent Types](#intent-types)
- [API Reference](#api-reference)
- [Examples](#examples)

## Features

- **14+ Intent Types** — Automatically detects query intent and routes to optimal processing pipeline
- **Direct Enumeration** — "List all X" queries return complete results in seconds (no LLM needed)
- **Chunked LLM Processing** — Large datasets processed in chunks, then synthesized
- **Async Generation** — Non-blocking API with job polling
- **Beautiful HTML Reports** — Styled, printable reports with source citations
- **Swagger API Docs** — Interactive API documentation at `/apidocs`
- **Source Citations** — Every report cites which documents support each point
- **Data Completeness Warnings** — Transparent about coverage gaps
- **Filtering** — Narrow scope by activity type, form type, source type, location, activity
- **Multi-Document Chat** — Query across all uploaded documents or specific ones

## Architecture

```
User Query
    │
    ▼
┌─────────────────┐
│ Intent Classifier│  ← 14+ intent types, keyword + pattern matching
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌─────────────┐
│ direct │  │ aggregation │
│  agg   │  │  + LLM      │
└───┬────┘  └──────┬──────┘
    │              │
    ▼              ▼
┌─────────────────────┐
│  Report Renderer     │  → Beautiful HTML with sources, warnings, citations
└─────────────────────┘
```

### Processing Strategies

| Intent | Strategy | LLM? | Speed |
|--------|----------|------|-------|
| enumeration | Direct aggregation from ES | No | ~3s |
| count | Direct aggregation from ES | No | ~3s |
| top_n | Direct aggregation from ES | No | ~3s |
| distribution | Aggregation + single LLM | Yes | ~30s |
| lookup | kNN + single LLM | Yes | ~30s |
| search | kNN + single LLM | Yes | ~30s |
| detail | kNN + single LLM | Yes | ~30s |
| recent | kNN + single LLM | Yes | ~30s |
| related | kNN + single LLM | Yes | ~30s |
| analytical | kNN + chunked LLM | Yes | ~60-120s |
| comparison | kNN + chunked LLM | Yes | ~60-120s |
| trend | kNN + chunked LLM | Yes | ~60-120s |
| prediction | kNN + chunked LLM | Yes | ~60-120s |
| summary | kNN + chunked LLM | Yes | ~60-120s |

## Installation

### Prerequisites

- Python 3.10+
- Elasticsearch 8.x running with `vec_fatboy_data` index (1000 docs with 768-dim embeddings)
- Ollama running with `llama3:8b-instruct-q8_0` model
- Git

### Setup

```bash
# Clone the repository
git clone git@github.com:sreshtantbohidar/ai_summary.git
cd ai_summary/report_generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Pull required Ollama models
ollama pull llama3:8b-instruct-q8_0
ollama pull nomic-embed-text
```

## Configuration

Edit `config.py` to match your environment:

```python
# Elasticsearch
ELASTIC_HOST = '192.168.1.125'
ELASTIC_PORT = 9200
ELASTIC_CLIENT_SCHEME = 'https'
ELASTICSEARCH_USERNAME = 'elastic'
ELASTICSEARCH_PASSWORD = 'your_password'

# Ollama
OLLAMA_URL = 'http://192.168.1.125:11434'
LLM_MODEL = 'llama3:8b-instruct-q8_0'
EMBED_MODEL = 'nomic-embed-text'

# Report settings
REPORT_DIR = './reports'
MAX_CONTEXT_CHARS = 8000
TOP_K_RESULTS = 10
```

## Usage

### Web UI

```bash
python app.py
# Open http://localhost:5001
```

The web interface provides:
- Mode selector (Answer / Analyze / Predict / Summarize)
- Query input with example placeholders
- Collapsible filters (activity type, form type, source type, location, activity)
- Recent reports sidebar with clickable history
- Live system status (ES + Ollama health)

### API

```bash
# Swagger documentation
http://localhost:5001/apidocs
```

#### Start a Report Generation

```bash
curl -X POST http://localhost:5001/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "List all locations",
    "mode": "answer"
  }'
```

Response: `{"job_id": "abc123def456", "status": "queued"}`

#### Check Job Status

```bash
curl http://localhost:5001/jobs/abc123def456
```

Response: `{"status": "done", "report_id": "xyz789", "generation_time": 2.6}`

#### View Report

```bash
# HTML report
curl http://localhost:5001/report/xyz789

# Download as file
curl http://localhost:5001/report/xyz789/download -o report.html

# JSON data
curl http://localhost:5001/report/xyz789/json
```

#### System Status

```bash
curl http://localhost:5001/api/status
```

#### List Recent Reports

```bash
curl http://localhost:5001/api/reports?limit=10
```

#### Get Filter Values

```bash
curl http://localhost:5001/api/filters
```

### CLI

```bash
# Basic usage
python cli_generate.py "List all locations"

# With mode
python cli_generate.py "Analyze deployment patterns" --mode analyze

# Save to file
python cli_generate.py "List all activity types" -o activities.html

# With filters
python cli_generate.py "List all locations" --filter activity_type=Deployment

# Text preview (no HTML file)
python cli_generate.py "Summarize equipment records" --preview
```

## Intent Types

The system automatically detects 14+ intent types from the query:

| Intent | Keywords | Example Query |
|--------|----------|---------------|
| **enumeration** | list all, show all, every, distinct, unique | "List all locations" |
| **count** | how many, count of, number of, total | "How many deployment activities?" |
| **top_n** | top 10, most common, highest, ranking | "Top 5 most frequent locations" |
| **distribution** | distribution of, breakdown by, grouped by | "Distribution of activity types" |
| **lookup** | what is, define, explain, meaning | "What is deployment?" |
| **search** | find, search for, locate, retrieve | "Find all patrol records" |
| **detail** | details of, info on, in depth, comprehensive | "Details of Site Alpha activities" |
| **recent** | recent, latest, newest, last week | "Recent deployment activities" |
| **related** | related to, similar to, connected with | "Activities related to Site Alpha" |
| **analytical** | analyze, examine, investigate, study | "Analyze deployment patterns" |
| **comparison** | compare, versus, difference between, vs | "Compare Site Alpha and Site Beta" |
| **trend** | trends, over time, patterns, evolution | "Trends in equipment procurement" |
| **prediction** | predict, forecast, will happen, future | "Predict maintenance needs" |
| **summary** | summarize, overview, brief, outline | "Summarize all activities" |

### Supported Filter Fields

| Field | Aliases |
|-------|---------|
| `location_name` | location, locations, site, sites, place, places, area, areas, region, regions, city, cities, country, countries, address, venue, destination, origin |
| `activity_name` | activity, activities, action, actions, task, tasks, operation, operations, mission, missions, event, events |
| `activity_type` | activity_type, activity_types |
| `form_type` | type, types, form_type, form_types, category, categories, class, classes, kind, kinds |
| `source_type` | source, sources, source_type, source_types |
| `equipment_name` | equipment, equipments, device, devices, tool, tools, asset, assets |
| `status` | status, state, state, phase, phase, stage, stage, priority, level, severity, impact, risk, issue, problem, incident |

## API Reference

### POST /generate

Start a report generation job.

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | The question or prompt |
| mode | string | No | answer, analyze, predict, summarize (default: answer) |
| activity_type | string | No | Filter by activity type |
| form_type | string | No | Filter by form type |
| source_type | string | No | Filter by source type |
| location_name | string | No | Filter by location |
| activity_name | string | No | Filter by activity |

**Response (202):**
```json
{
  "job_id": "abc123def456",
  "status": "queued"
}
```

### GET /jobs/{job_id}

Check job status.

**Response:**
```json
{
  "status": "done",
  "report_id": "xyz789",
  "title": "📋 Enumeration: location_name (82 values)",
  "generation_time": 2.6
}
```

### GET /report/{report_id}

View HTML report.

### GET /report/{report_id}/download

Download report as HTML file.

### GET /report/{report_id}/json

Get report data as JSON.

### GET /api/reports

List recent reports.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | integer | 20 | Max reports to return |

### GET /api/status

System status (ES + Ollama health).

### GET /api/filters

Get available filter values from ES aggregations.

## Examples

### Enumeration Query

**Query:** `List all locations`

**Response:** Complete numbered list of all 82 locations with document counts, generated in ~3 seconds.

### Analytical Query

**Query:** `Analyze deployment patterns at Site Alpha`

**Response:** Multi-section report with executive summary, key findings, detailed analysis, and source citations. Uses chunked LLM processing for large datasets.

### Comparison Query

**Query:** `Compare deployment activities at Site Alpha vs Site Beta`

**Response:** Side-by-side analysis with similarities, differences, and strategic insights.

### Trend Query

**Query:** `Show trends in equipment procurement over time`

**Response:** Time-series analysis with patterns, growth/decline indicators, and future projections.

## Project Structure

```
report_generator/
├── app.py                  # Flask web app with Swagger docs
├── cli_generate.py         # CLI script for terminal use
├── config.py               # ES + Ollama connection constants
├── rag_engine.py           # Core RAG pipeline (intent classification, chunking, aggregation)
├── report_renderer.py      # HTML report template with styling
├── report_store.py         # Save/load reports as JSON
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Web UI (dark theme, mode selector, filters)
├── reports/                # Generated reports (auto-created)
│   ├── report_*.json       # Report data
│   └── report_*.html       # Downloadable HTML
└── logs/
    └── app.log             # Application logs
```

## License

MIT
