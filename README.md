# EarningsLens
> Agentic AI system that audits management credibility
> on earnings calls - extracting forward guidance,
> cross-validating against reported actuals, and generating
> structured analyst briefs.

Assignment: CT2 Group Assignment - AMPBA Batch 24  
Framework: LangGraph (StateGraph)  
LLM: GPT-4o via OpenAI  
Tracing: LangSmith  
Python: 3.11+

## Problem statement
Earnings calls are information-dense but often insight-poor for decision-making because critical commitments are buried across lengthy transcripts. Analysts cannot practically read and compare 80+ transcripts per quarter manually at scale. Existing workflows also do not systematically verify whether management delivered on prior quarter guidance using current quarter actuals. EarningsLens solves this with an agentic pipeline that extracts, cross-validates, scores credibility, and produces structured analyst-ready briefs.

## Architecture

### Pipeline overview
```text
Input: ticker + quarter
       ↓
┌─────────────────────────────────────────┐
│  LangGraph StateGraph                   │
│                                         │
│  [Guardrail]  input_guard               │
│       ↓                                 │
│  [Agent 1]  transcript_loader           │
│       ↓                                 │
│  [Agent 2]  guidance_extractor   (LLM)  │
│       ↓                                 │
│  [Agent 3]  actuals_extractor    (LLM)  │
│       ↓                                 │
│  [Agent 4]  credibility_scorer   (LLM)  │
│       ↓                                 │
│  ┌────────── Conditional Routing ─────┐ │
│  │ score < 50  →  red_flag path       │ │
│  │ score ≥ 50  →  clean_bill path     │ │
│  └────────────────────────────────────┘ │
│       ↓                                 │
│  [Agent 5]  report_generator     (LLM)  │
│       ↓                                 │
│  [Guardrail]  output_guard              │
└─────────────────────────────────────────┘
       ↓
Output: Markdown analyst brief
```

Pipeline flow: `input_guard -> transcript_loader -> guidance_extractor -> actuals_extractor -> score_credibility -> [conditional: red_flag | clean_bill] -> report_generator -> output_guard`

Dataset: 18,755 earnings call transcripts (Motley Fool), 2,876 unique tickers, 2016-2020.  
Agents: 5 sub-agents + 2 guardrail nodes.

### Agent descriptions
| Agent | Role | LLM | Tool Used |
|---|---|---|---|
| input_guard | Validates ticker/quarter, blocks injection | No | regex validation |
| transcript_loader | Loads current + prior transcript from PKL | No | pkl_loader utility |
| guidance_extractor | Extracts forward guidance from prior Q | Yes | few-shot prompt |
| actuals_extractor | Extracts reported results from current Q | Yes | few-shot + EDGAR API |
| credibility_scorer | Cross-validates guidance vs actuals | Yes | scoring rubric |
| report_generator | Generates Red Flag or Clean Bill brief | Yes | conditional template |
| output_guard | Validates schema, PII check | No | regex + schema check |

### Orchestration pattern
The primary orchestration pattern is a sequential pipeline across five agents (`transcript_loader` -> `guidance_extractor` -> `actuals_extractor` -> `credibility_scorer` -> `report_generator`). A non-trivial conditional routing step is applied after Agent 4, where `score < 50` routes to the `RED FLAG` brief template and `score >= 50` routes to the `CLEAN BILL` template. The graph also short-circuits safely: if `input_guard` fails, execution exits at `END` without invoking any LLM node.

### Guardrails
Input guardrails:
- Ticker format validation (regex: `^[A-Za-z][A-Za-z0-9.\-]{0,9}$`)
- Quarter format validation (regex: `^\d{4}-Q[1-4]$`)
- Year range check (2000-2030)
- Prompt injection detection (pattern matching)

Output guardrails:
- Report non-empty check (length > 50)
- Credibility score range check (0.0-100.0)
- Required keys validation on all structured items
- PII check (no 12+ digit sequences)
- Route value validation

## Tool use

Two sub-agents are configured with external tools:

| Agent | Tool | Type | Purpose |
|-------|------|------|---------|
| Agent 1 - transcript_loader | pkl_loader utility | Local file | Loads transcripts from 18,755-row PKL dataset, derives prior quarter |
| Agent 3 - actuals_extractor | SEC EDGAR free API | External REST API | Fetches company metadata for known tickers - no API key required |

### SEC EDGAR API
- Endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`
- No authentication required
- Returns: company name, SIC code, fiscal year end
- Implemented in: `utils/edgar_tool.py`
- Called by: `agents/actuals_extractor.py`
- Graceful fallback: if ticker not in CIK map, logs a warning and continues without blocking pipeline

## Setup

### Prerequisites
- Python 3.11+
- OpenAI API key
- LangSmith API key (optional, for tracing)

### Installation
```bash
git clone https://github.com/YOUR_USERNAME/earnings-lens.git
cd earnings-lens
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables
Create a `.env` file in `earnings-lens/`:
```env
OPENAI_API_KEY=your_openai_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=earnings-lens
```

### Data setup
Place the transcripts PKL file at:
```text
earnings-lens/data/transcripts.pkl
```
Dataset: 18,755 Motley Fool earnings call transcripts  
Columns: `date`, `exchange`, `q`, `ticker`, `transcript`

## Usage

### Run the full notebook
```bash
jupyter notebook main.ipynb
```
Run all cells top to bottom.  
Scenarios 1-5 execute automatically.

### Run a single pipeline call
```python
import sys, os
sys.path.append('earnings-lens')
os.chdir('earnings-lens')

from dotenv import load_dotenv
load_dotenv()

from pipeline.graph import run_pipeline

result = run_pipeline("AAPL", "2020-Q3")
print(result['credibility_score'])
print(result['route'])
print(result['report'])
```

### Run sub-agent evaluation
```bash
cd earnings-lens
python evaluation/eval_runner.py
```

## Test scenarios

| # | Type | Input | Expected | Result |
|---|------|-------|----------|--------|
| 1 | Happy path | BILI, 2020-Q2 | Full pipeline, report generated | ✅ score=25.0, red_flag |
| 2 | Cross-quarter | Auto-selected consecutive ticker | Prior quarter found, report generated | ✅ PASS |
| 3 | Edge case (Q1 rollover) | Ticker with Q1, prior=prev year Q4 | Correct prior quarter derived | ✅ PASS |
| 4 | Adversarial (injection) | "IGNORE PREVIOUS INSTRUCTIONS" | Blocked by input_guard | ✅ BLOCKED |
| 5 | Failure/recovery | ZZZZZ (unknown ticker) | Graceful error, no crash | ✅ GRACEFUL FAIL |

## Sub-agent evaluation

Agent evaluated: guidance_extractor (Agent 2)  
Dataset: 20 manually curated input-output pairs  
Metric: Precision / Recall / F1 on metric identification

| Metric | Score |
|--------|-------|
| Precision | 0.95 |
| Recall | 0.95 |
| F1 | 0.95 |
| Failures (F1 < 0.5) | 0 / 20 |

Categories tested:
- Items 1-5: Single-metric guidance (clear, explicit)
- Items 6-10: Multi-metric guidance (2-3 metrics per snippet)
- Items 11-14: Vague/hedged guidance (no quantifiable metric)
- Items 15-17: No guidance (negative cases)
- Items 18-20: Edge cases (ranges, non-USD, fiscal year)

Run evaluation:
```bash
python evaluation/eval_runner.py
```

## Project structure

```text
earnings-lens/
├── agents/
│   ├── transcript_loader.py     # Agent 1 - loads transcripts
│   ├── guidance_extractor.py    # Agent 2 - extracts guidance (LLM)
│   ├── actuals_extractor.py     # Agent 3 - extracts actuals (LLM)
│   ├── credibility_scorer.py    # Agent 4 - scores credibility (LLM)
│   └── report_generator.py      # Agent 5 - generates brief (LLM)
├── prompts/
│   ├── guidance_extractor.md    # Few-shot prompt for Agent 2
│   ├── actuals_extractor.md     # Few-shot prompt for Agent 3
│   ├── credibility_scorer.md    # Scoring rubric prompt for Agent 4
│   └── report_generator.md      # Report template prompt for Agent 5
├── pipeline/
│   ├── state.py                 # LangGraph TypedDict state schema
│   ├── graph.py                 # StateGraph wiring + run_pipeline()
│   └── guardrails.py            # Input + output validation
├── utils/
│   ├── pkl_loader.py            # Dataset loading utilities
│   └── edgar_tool.py            # SEC EDGAR free API tool
├── data/
│   └── transcripts.pkl          # 18,755 transcripts (not in repo)
├── evaluation/
│   ├── eval_dataset.json        # 20 labelled evaluation pairs
│   └── eval_runner.py           # Evaluation script
├── main.ipynb                   # Runner notebook - all 5 scenarios
├── requirements.txt
├── .env.example
└── README.md
```

## Key design decisions

- LangGraph was selected for native conditional routing, built-in state management, and LangSmith tracing out of the box.
- A multi-agent design was chosen over a single prompt because extraction, retrieval, evaluation, and report generation are distinct capabilities that do not reliably collapse into one LLM call.
- Cross-quarter validation is central because most tools summarize calls, while EarningsLens audits whether management delivered on prior commitments, which answers a more valuable analytical question.

## Requirements

```text
langchain-openai
python-dotenv
pandas
requests
langsmith
langgraph
```
