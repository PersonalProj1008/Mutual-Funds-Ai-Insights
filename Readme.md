# Canon Wealth — Mutual Fund Comparative Analysis

AI-assisted mutual fund comparison platform designed to turn historical market-capture data into a structured, transparent, investor-friendly comparative report.

The system is intentionally built so that **the numerical ranking is determined by explicit Python rules**, while the AI layer is responsible for **explaining the supplied results in clear, professional language**.

This separation is central to the design:

> **Data → Deterministic Ranking → AI Explanation → PDF Report**

The application supports comparison of **2 to 10 mutual fund schemes** over a selectable historical period of **1, 3, 5, or 10 years**.

---

## Table of Contents

- [Overview](#overview)
- [Core Design Philosophy](#core-design-philosophy)
- [How the System Works](#how-the-system-works)
- [Project Structure](#project-structure)
- [Data Source](#data-source)
- [Input and Validation Rules](#input-and-validation-rules)
- [Metrics Used](#metrics-used)
- [The Five Investor Lenses](#the-five-investor-lenses)
- [Transparent Ranking Rules](#transparent-ranking-rules)
- [Tie-Breaking Rules](#tie-breaking-rules)
- [What Rank 1 Means](#what-rank-1-means)
- [Capture Differential / Capture Spread](#capture-differential--capture-spread)
- [Role of AI](#role-of-ai)
- [AI Safety and Integrity Rules](#ai-safety-and-integrity-rules)
- [Plain-English Terminology](#plain-english-terminology)
- [Report Generation](#report-generation)
- [Backend API](#backend-api)
- [Frontend](#frontend)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Running Locally](#running-locally)
- [Deployment to Render](#deployment-to-render)
- [Methodological Limitations](#methodological-limitations)
- [Security](#security)
- [Future Enhancements](#future-enhancements)
- [License / Usage](#license--usage)

---

# Overview

Canon Wealth Mutual Fund Comparative Analysis is a rules-based comparison application with an AI-assisted interpretation layer.

A user selects mutual funds using either:

1. **Search & Select**
2. **Paste List**

The system then:

1. validates the selected schemes,
2. retrieves market-capture and historical-return data,
3. normalizes the returned data,
4. calculates the application-defined comparative fields,
5. generates rankings under five different investor objectives,
6. sends the already-calculated rankings to the AI explanation layer,
7. validates the AI response,
8. generates a professionally formatted PDF,
9. returns the PDF directly to the browser for download.

The frontend exposes a simple investor workflow while the backend preserves a clear analytical pipeline.

---

# Core Design Philosophy

## 1. Ranking first, explanation second

The most important architectural decision is that the AI model **does not decide the numerical ranking**.

Python calculates the rankings first.

The AI then receives the source metrics and the already-calculated rankings and explains them. It is explicitly instructed to treat those rankings as immutable.

This makes the system easier to audit and reduces the risk of an LLM silently changing a numerical conclusion.

---

## 2. No single universal "best fund"

The application deliberately avoids producing one universal winner.

A mutual fund can be:

- stronger from a downside-protection perspective,
- stronger in upside participation,
- stronger under the capture-efficiency lens,
- stronger in historical return,
- or stronger under the application's balanced-comparison heuristic.

Therefore, the report presents **multiple investor lenses** instead of pretending that one metric can represent every investor objective.

---

## 3. Transparent and deterministic

Each lens has:

- a clearly defined primary metric,
- a defined ranking direction,
- explicit tie-breakers,
- and a plain-English interpretation.

The ranking engine validates the comparison set, prevents duplicate funds, converts numeric values into normalized numeric types, and applies deterministic sorting.

There is no hidden weighted score in the current implementation.

---

# How the System Works

```text
                           USER
                            │
                            ▼
                 ┌─────────────────────┐
                 │  Web Interface      │
                 │  Search / Paste     │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ FastAPI Validation  │
                 │ 2–10 funds          │
                 │ 1/3/5/10 years     │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ AdvisorKhoj         │
                 │ Data Retrieval      │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Data Normalization  │
                 │ & Validation        │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Python FundRanker   │
                 │ 5 Investor Lenses   │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ AI Explanation Layer│
                 │ Explain, don't rank │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ ReportGenerator     │
                 │ Professional PDF    │
                 └──────────┬──────────┘
                            │
                            ▼
                           PDF
```

---

# Project Structure

```text
Axiom_Wealth_pvt_ltd/
│
├── mfs_server/
│   ├── templates/
│   │   └── index.html
│   │
│   ├── __init__.py
│   ├── main.py
│   └── schemas.py
│
├── mutual_funds_summerizer/
│   ├── __init__.py
│   ├── advisorkhoj_scraper.py
│   ├── ai_analyzer.py
│   ├── fund_ranker.py
│   └── report_generator.py
│
├── Readme.md
├── requirements.txt
├── .gitignore
└── .env                  # local only; never commit
```

## Responsibilities

### `mfs_server/main.py`

FastAPI application entry point.

Responsible for:

- serving the web application,
- exposing the health endpoint,
- fund autocomplete/search,
- category retrieval,
- accepting analysis requests,
- orchestrating the complete analysis pipeline,
- generating temporary PDF files,
- returning the generated PDF to the browser,
- cleaning up temporary files.

### `mfs_server/schemas.py`

Defines and validates API request models.

The API accepts:

- pasted fund scheme names, or
- objects containing category + scheme.

The analysis period is restricted to:

```text
1, 3, 5, 10
```

The comparison set is restricted to:

```text
2–10 funds
```

### `mutual_funds_summerizer/advisorkhoj_scraper.py`

Handles source-data retrieval and normalization.

It retrieves:

- Scheme Name
- AMC Name
- Benchmark Name
- Launch Date
- Scheme Return (%)
- Up Market Capture Ratio (%)
- Down Market Capture Ratio (%)
- Capture Ratio

It also provides:

- period validation,
- fund-selection validation,
- category retrieval,
- scheme autocomplete,
- scheme-name resolution,
- multi-fund retrieval.

### `mutual_funds_summerizer/fund_ranker.py`

The deterministic ranking engine.

This module calculates:

- all five lens rankings,
- Capture Differential / Capture Spread,
- ranking-basis metadata,
- factual fund characteristics,
- comparison summaries.

### `mutual_funds_summerizer/ai_analyzer.py`

The interpretation layer.

It:

- receives the source metrics,
- receives the already-calculated Python rankings,
- explains why the ranks occurred,
- writes executive and preference summaries,
- produces structured output,
- validates the returned structure,
- verifies AI-declared winners against Python winners.

### `mutual_funds_summerizer/report_generator.py`

Produces the final PDF report.

The report is designed as a structured research-style document with:

- executive perspective,
- executive summary,
- selected fund snapshot,
- terminology guide,
- investor-objective overview,
- detailed comparative rankings,
- methodology and disclosures.

---

# Data Source

The data retrieval layer is built around **AdvisorKhoj's Market Capture Ratio research page and related scheme autocomplete endpoint**.

For each requested scheme and analysis period, the scraper expects the source data to contain:

```text
Scheme Name
AMC Name
Benchmark Name
Launch Date
Scheme Return (%)
Up Market Capture Ratio (%)
Down Market Capture Ratio (%)
Capture Ratio
```

The scraper checks that the expected columns exist before normalizing the record.

For the requested scheme, the implementation attempts:

1. exact case-insensitive scheme-name matching,
2. a safe fallback for minor formatting differences.

The normalized internal record is then passed to the ranking engine.

---

# Input and Validation Rules

## Supported analysis periods

Only these periods are accepted:

```text
1 year
3 years
5 years
10 years
```

## Supported fund count

The application accepts:

```text
Minimum: 2 funds
Maximum: 10 funds
```

## Duplicate protection

Duplicate schemes are rejected.

The ranking engine also checks for duplicate scheme names in its normalized comparison set.

## Required fund fields

Every normalized fund record must contain:

```text
scheme_name
amc_name
benchmark_name
launch_date
scheme_return
up_capture
down_capture
capture_ratio
```

The four numerical inputs are converted to floating-point values before ranking.

---

# Metrics Used

The analytical framework uses five source values plus one application-defined derived value.

## Scheme Return

The reported historical return for the selected review period.

### In simple terms

How much the fund historically grew or declined during the selected period.

### Important alert

This is backward-looking historical data.

It is **not a forecast** of future returns.

---

## Up-Market Capture

A measure of the scheme's historical participation during positive benchmark periods.

### In simple terms

How strongly the fund tended to participate when the benchmark was rising.

### Used by

**Upside Participation** lens.

### Preferred direction

```text
Higher = Better
```

---

## Down-Market Capture

A measure of the scheme's historical participation during negative benchmark periods.

### In simple terms

How much of a falling benchmark the fund tended to participate in.

### Used by

**Downside Protection** lens.

### Preferred direction

```text
Lower = Better
```

### Important alert

Down-Market Capture should not be interpreted as the fund's exact percentage loss.

It is a relative market-participation measure.

---

## Capture Ratio

The Capture Ratio value supplied by the source dataset.

### In simple terms

A compact source-provided indicator used by the application to compare market-capture characteristics across schemes.

### Important alert

The application uses the supplied value as provided and does not independently recalculate it.

---

## Capture Differential / Capture Spread

The application-defined derived metric is:

```text
Capture Differential
=
Up-Market Capture
-
Down-Market Capture
```

Example:

```text
Up-Market Capture   = 120
Down-Market Capture = 80

Capture Differential = 40
```

### In simple terms

It is the difference between the fund's historical upside participation and downside participation.

### Important alert

**Capture Differential / Capture Spread is not an official AdvisorKhoj metric.**

It is an **application-defined comparative heuristic** used by the Balanced Participation lens.

---

# The Five Investor Lenses

The same selected funds are ranked five different ways.

The important principle is:

> **The fund set stays the same. The investor objective changes.**

---

## 1. Downside Protection

### Investor question

> "Which fund historically participated less in market declines?"

### Primary metric

```text
Down-Market Capture
```

### Rule

```text
LOWER = BETTER
```

### Example

```text
Fund A → 82
Fund B → 105
Fund C → 74
```

Result:

```text
Fund C → #1
Fund A → #2
Fund B → #3
```

### Plain-English interpretation

This lens favours funds with lower historical participation during benchmark down-market periods.

### Tie-breakers

1. Higher Capture Ratio
2. Higher Up-Market Capture
3. Alphabetical scheme name

---

## 2. Balanced Participation

### Investor question

> "Which fund shows a stronger difference between historical upside participation and downside participation?"

### Primary metric

```text
Capture Differential / Capture Spread
```

### Formula

```text
Capture Differential
=
Up-Market Capture
-
Down-Market Capture
```

### Rule

```text
HIGHER = BETTER
```

### Example

```text
Fund A:
Up = 120
Down = 80
Spread = 40

Fund B:
Up = 130
Down = 110
Spread = 20

Fund C:
Up = 105
Down = 70
Spread = 35
```

Result:

```text
Fund A → #1
Fund C → #2
Fund B → #3
```

### Plain-English interpretation

The application prefers a larger difference between historical upside and downside participation.

### Tie-breakers

1. Higher Capture Ratio
2. Lower Down-Market Capture
3. Higher Up-Market Capture
4. Alphabetical scheme name

### Important alert

This is an **application-defined heuristic**, not a published AdvisorKhoj ranking methodology.

---

## 3. Upside Participation

### Investor question

> "Which fund historically participated more strongly when the benchmark was rising?"

### Primary metric

```text
Up-Market Capture
```

### Rule

```text
HIGHER = BETTER
```

### Plain-English interpretation

This lens favours schemes that historically captured more of positive benchmark periods.

### Tie-breakers

1. Higher Capture Ratio
2. Lower Down-Market Capture
3. Alphabetical scheme name

---

## 4. Capture Efficiency

### Investor question

> "Which scheme has the stronger source-provided Capture Ratio?"

### Primary metric

```text
Capture Ratio
```

### Rule

```text
HIGHER = BETTER
```

The source-provided Capture Ratio is used directly.

### Tie-breakers

1. Higher Up-Market Capture
2. Lower Down-Market Capture
3. Alphabetical scheme name

### Plain-English interpretation

This lens uses the supplied Capture Ratio as a compact comparison of market-capture characteristics.

---

## 5. Historical Return

### Investor question

> "Which scheme reported the highest historical return over the selected period?"

### Primary metric

```text
Scheme Return
```

### Rule

```text
HIGHER = BETTER
```

### Plain-English interpretation

This lens compares the reported historical return of the selected schemes over the selected review period.

### Tie-breakers

1. Higher Capture Ratio
2. Lower Down-Market Capture
3. Higher Up-Market Capture
4. Alphabetical scheme name

### Important alert

Historical Return is backward-looking and should not be treated as a forecast.

---

# Transparent Ranking Rules

The ranking engine follows an explicit sequence:

```text
Primary metric
        ↓
First tie-break
        ↓
Second tie-break
        ↓
Third tie-break
        ↓
Alphabetical final tie-break
```

There is no hidden machine-learned weighting in the current ranking implementation.

For example, the Balanced lens does **not** silently calculate:

```text
40% return
30% upside
20% downside
10% capture ratio
```

Instead, it directly compares the defined primary metric and follows documented tie-breakers.

This makes the result:

- reproducible,
- deterministic,
- explainable,
- inspectable.

---

# Tie-Breaking Rules

## Defensive / Downside Protection

```text
1. Lower Down-Market Capture
2. Higher Capture Ratio
3. Higher Up-Market Capture
4. Alphabetical scheme name
```

## Balanced Participation

```text
1. Higher Capture Differential
2. Higher Capture Ratio
3. Lower Down-Market Capture
4. Higher Up-Market Capture
5. Alphabetical scheme name
```

## Growth / Upside Participation

```text
1. Higher Up-Market Capture
2. Higher Capture Ratio
3. Lower Down-Market Capture
4. Alphabetical scheme name
```

## Capture Efficiency

```text
1. Higher Capture Ratio
2. Higher Up-Market Capture
3. Lower Down-Market Capture
4. Alphabetical scheme name
```

## Historical Return

```text
1. Higher Scheme Return
2. Higher Capture Ratio
3. Lower Down-Market Capture
4. Higher Up-Market Capture
5. Alphabetical scheme name
```

Alphabetical scheme name is used as the final ordering criterion where defined, ensuring stable results when the analytical values are indistinguishable.

---

# What Rank 1 Means

This application intentionally uses the phrase **leading scheme** rather than implying an absolute universal winner.

> **Rank 1 means the best-ranked scheme among the selected comparison set for that specific lens.**

For example:

```text
Downside Protection
    → Fund A #1

Upside Participation
    → Fund B #1

Historical Return
    → Fund C #1
```

This is expected.

Different schemes can have different historical characteristics.

A fund ranking #1 under one lens can rank lower under another.

---

# Capture Differential / Capture Spread

This derived metric deserves special attention because it is unique to the application's framework.

## Formula

```text
Capture Differential
=
Up-Market Capture
-
Down-Market Capture
```

## Example

```text
Scheme X

Up-Market Capture   = 115
Down-Market Capture = 75

Capture Differential = 40
```

## Interpretation

A higher number means the observed historical gap between upside participation and downside participation is larger.

The application uses this measure to rank the **Balanced Participation** lens.

## What it is not

It is not:

- an official AdvisorKhoj field,
- a forecast,
- a risk score,
- a guarantee of future performance,
- or a standalone suitability measure.

It is an explicit application-level comparative heuristic.

---

# Role of AI

The AI layer is deliberately placed **after** the deterministic ranking engine.

## Python determines

- rank,
- rank order,
- winner,
- primary metric,
- ranking direction,
- tie-break criteria,
- numerical values.

## AI determines only

- how those results are explained,
- how the report is written,
- how the findings are summarized,
- how technical concepts are communicated to readers.

The model is therefore an **interpretation and communication layer**, not the numerical decision-maker.

---

# AI Safety and Integrity Rules

The AI prompt contains explicit restrictions.

## Never change a rank

Python rankings are treated as immutable.

## Never invent data

Missing metrics must not be estimated or filled in.

## Never substitute ranking logic

The model cannot decide that another metric "should" have been used.

## Preserve exact scheme names

Fund names supplied by the application must remain unchanged.

## Use only supplied metrics

The model should not introduce unsupported metrics or statistics.

## Explain tie-breaks faithfully

When a primary metric ties, the AI should explain the actual deterministic secondary rule used by Python.

## Do not call historical performance a forecast

Historical results are backward-looking.

## Do not misdescribe Down-Market Capture

Down-Market Capture is not the same thing as the fund's actual realized loss.

## Do not turn Capture Differential into an official metric

It must remain clearly identified as an application-defined heuristic.

## No personalized investment advice

The report is informational and comparative.

## Winner validation

After the model response is parsed, the application compares the AI-declared winner for each lens against the Python winner.

If they differ, the analysis is rejected.

This prevents an otherwise well-written AI response from quietly changing the actual analytical conclusion.

---

# Plain-English Terminology

The PDF uses a formal-to-accessible terminology layer.

## Benchmark

**Formal:** The reference market index used to assess relative performance and market participation.

**In simple terms:** The fund's comparison yardstick.

**Important:** A benchmark is not a guaranteed return or risk-free investment.

---

## Historical Return

**Formal:** The scheme's observed return over the selected historical review period.

**In simple terms:** How much the investment grew or declined in the past.

**Important:** Past performance is backward-looking and does not predict future performance.

---

## Up-Market Capture

**Formal:** A measure of historical participation during positive benchmark periods.

**In simple terms:** How strongly the fund tended to participate when the market was rising.

**Important:** Values above 100% indicate stronger historical participation than the benchmark during the relevant positive periods.

---

## Down-Market Capture

**Formal:** A measure of historical participation during negative benchmark periods.

**In simple terms:** How much of the market's decline the fund tended to participate in.

**Important:** Lower values may be preferable under a downside-protection objective, but the preferred direction depends on the lens.

---

## Capture Ratio

**Formal:** The Capture Ratio value supplied by the source dataset.

**In simple terms:** A source-provided number used here to compare market-capture characteristics.

**Important:** The application uses the supplied value and does not independently recalculate it.

---

## Capture Differential

**Formal:** An application-defined measure calculated as:

```text
Up-Market Capture - Down-Market Capture
```

**In simple terms:** The historical difference between upside and downside participation.

**Important:** This is an application-level comparative heuristic, not an official source metric.

---

# Report Generation

The PDF is generated using ReportLab.

The report is structured as an analytical document rather than a raw data export.

## Section 01 — Executive Perspective

Introduces the purpose of the multi-lens comparison.

## Section 02 — Executive Summary

Contains:

- overall summary,
- five preference summaries,
- major cross-lens observations.

## Section 03 — Selected Fund Snapshot

Shows:

- Scheme
- Historical Return
- Up-Market Capture
- Down-Market Capture
- Capture Ratio
- Capture Differential

## Section 04 — Terminology Guide

Pairs technical definitions with:

- simple explanations,
- methodological alerts.

## Section 05 — Investor Objective Overview

Explains:

- what each lens is trying to measure,
- the primary criterion,
- the leading scheme,
- the practical interpretation.

## Section 06 — Detailed Comparative Rankings

Shows:

- rank for every selected scheme,
- relevant metrics,
- benchmark context,
- AI-generated explanation.

## Section 07 — Methodology & Interpretation

Documents:

- ranking rules,
- important considerations,
- source information,
- analytical framework,
- disclosures.

---

# Backend API

## `GET /`

Serves the web application.

---

## `GET /health`

Health-check endpoint used to confirm that the FastAPI service is alive.

Typical response:

```json
{
  "status": "ok",
  "service": "..."
}
```

---

## `GET /api/categories`

Retrieves AdvisorKhoj category information.

---

## `GET /api/schemes`

Searches for scheme names using the AdvisorKhoj autocomplete function.

Example:

```text
/api/schemes?category=Equity%3A%20Multi%20Cap&query=ICICI
```

The endpoint returns a JSON array of scheme names.

---

## `POST /api/analyze`

Main analysis endpoint.

Example structure:

```json
{
  "funds": [
    {
      "category": "Equity: Large Cap",
      "scheme": "Fund A"
    },
    {
      "category": "Equity: Multi Cap",
      "scheme": "Fund B"
    }
  ],
  "period": "3"
}
```

Pipeline:

```text
Validate request
      ↓
Normalize fund selection
      ↓
Retrieve source data
      ↓
Normalize source metrics
      ↓
Deterministic Python ranking
      ↓
AI explanation
      ↓
AI output validation
      ↓
PDF generation
      ↓
Return application/pdf
```

---

# Frontend

The browser interface is located at:

```text
mfs_server/templates/index.html
```

It supports:

- Search & Select mode
- Paste List mode
- 2–10 funds
- 1 / 3 / 5 / 10 year periods
- responsive layout
- animated gradient background
- animated Canon Wealth splash screen
- starfield visual effects
- progress messaging
- PDF generation
- PDF download
- green Download PDF ready state

The frontend uses relative API paths:

```javascript
const HEALTH_ENDPOINT = "/health";
const CATEGORIES_ENDPOINT = "/api/categories";
const SCHEMES_ENDPOINT = "/api/schemes";
const ANALYZE_ENDPOINT = "/api/analyze";
```

This allows the frontend and backend to be hosted on the same origin.

---

# Installation

## 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

---

## 2. Create a virtual environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

The project currently uses packages for:

- FastAPI
- Uvicorn
- Jinja2
- Requests
- BeautifulSoup
- Pandas
- lxml
- OpenAI-compatible API access
- Pydantic / Pydantic Settings
- python-dotenv
- ReportLab

The pinned versions are maintained in `requirements.txt`.

---

# Environment Variables

Secrets must never be stored directly in source code or committed to GitHub.

Create a local:

```text
.env
```

at the repository root:

```text
Axiom_Wealth_pvt_ltd/
├── .env
├── requirements.txt
├── mfs_server/
└── mutual_funds_summerizer/
```

The local settings may look like:

```env
api_key=YOUR_OPENROUTER_API_KEY
language_model=YOUR_OPENROUTER_MODEL
base_url=https://openrouter.ai/api/v1
```

The real variable names should match the configuration expected by the application.

## `.gitignore`

Make sure the real `.env` is ignored:

```gitignore
.env
.env.*
!.env.example
```

Never commit the actual secret file.

---

# Running Locally

Run the application from the repository root:

```bash
uvicorn mfs_server.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

Development API documentation may also be available at:

```text
http://127.0.0.1:8000/docs
```

---

# Deployment to Render

The application can be deployed as a single Render Web Service.

## Recommended configuration

```text
Service Type:
Web Service

Runtime:
Python 3

Root Directory:
[leave empty]

Build Command:
pip install -r requirements.txt

Start Command:
uvicorn mfs_server.main:app --host 0.0.0.0 --port $PORT
```

## Environment variables

Add the same configuration values in Render's Environment section.

For example:

```text
api_key
language_model
base_url
```

Do not upload the local `.env` file.

## Health check

Use:

```text
/health
```

## Deployment flow

```text
GitHub
   ↓
Render Web Service
   ↓
pip install -r requirements.txt
   ↓
uvicorn mfs_server.main:app --host 0.0.0.0 --port $PORT
   ↓
FastAPI application
```

---

# Methodological Limitations

The framework is intentionally transparent, but it is not a complete investment-decision system.

## 1. Historical data is historical

The analysis describes the selected historical review period.

It does not forecast future returns.

## 2. Rankings are relative

A rank describes the selected comparison set.

It is not an industry-wide ranking of every available mutual fund.

## 3. Different lenses can produce different winners

This is a feature of the design.

Different metrics answer different analytical questions.

## 4. Capture Differential is application-defined

The calculation:

```text
Up-Market Capture - Down-Market Capture
```

is a report-level comparative heuristic.

## 5. Capture Ratio is source-provided

The application uses the source value rather than independently reproducing the source's formula.

## 6. No portfolio-level optimization

The current application does not calculate:

- portfolio allocation,
- fund correlation,
- investor-specific risk tolerance,
- tax impact,
- transaction costs,
- liquidity requirements,
- asset-allocation suitability.

## 7. No personalized advice

The output is intended for informational and comparative purposes and should not be treated as individualized financial advice.

---

# Security

## Never commit secrets

Never commit:

```text
.env
API keys
access tokens
private credentials
```

to GitHub.

## Recommended workflow

```text
Local .env
     ↓
.gitignore
     ↓
Never committed
     ↓
Render Environment Variables
```

If an API credential is ever exposed in a repository, revoke and rotate it immediately.

---

# Future Enhancements

Potential future extensions include:

- additional investor lenses,
- user-defined lens weights,
- portfolio-level analysis,
- risk-adjusted measures,
- benchmark-relative visualizations,
- historical charts,
- peer-group comparisons,
- CSV / Excel export,
- report history,
- authentication,
- multi-user workspaces,
- caching of source data,
- configurable AI model selection,
- audit logging,
- scheduled report generation.

A future scoring model should preserve the central design principle:

> **Every numerical decision should have a documented rule.**

---

# License / Usage

This repository is intended as a research and application project for comparative mutual-fund analysis.

Generated reports should be treated as historical, informational and comparative material.

They should not be represented as guarantees of future performance or personalized financial advice.

---

# Summary

The application combines:

```text
AdvisorKhoj historical data
        +
Data normalization
        +
Deterministic Python ranking
        +
Five investor lenses
        +
AI-assisted explanation
        +
Structured validation
        +
Professional PDF generation
```

The key architectural rule is:

> **Python decides the rank. AI explains the rank.**

That separation makes the analytical process transparent, reproducible, and easier to audit while allowing the final report to remain readable for both specialist and non-specialist users.
