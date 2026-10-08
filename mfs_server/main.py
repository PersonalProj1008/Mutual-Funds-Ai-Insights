import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from mfs_server.schemas import AnalysisRequest, FundSelection

from mutual_funds_summerizer.advisorkhoj_scraper import (
    FundDataError,
    MarketCaptureScraper,
    get_funds_with_category,
)

from mutual_funds_summerizer.fund_ranker import FundRanker

from mutual_funds_summerizer.ai_analyzer import (
    AIAnalyzer,
    AIAnalyzerError,
)

from mutual_funds_summerizer.report_generator import ReportGenerator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# ENVIRONMENT
# ============================================================

class Settings:
    """
    Settings are loaded from environment variables / .env.
    """


    class Config(BaseSettings):
        api_key: str
        language_model: str
        base_url:str

        model_config = SettingsConfigDict(
            env_file=".env",
            extra="ignore",
        )


env_key_value_obj = Settings.Config()



API_KEY = env_key_value_obj.api_key
BASE_URL =env_key_value_obj.base_url

LLM_MODEL = env_key_value_obj.language_model
APP_URL = "Canon Wealth"


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Canon Wealth Mutual Fund Intelligence",
    description=(
        "AI-powered mutual fund comparative analysis "
        "using AdvisorKhoj market-capture data."
    ),
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ============================================================
# COMMON HELPERS
# ============================================================

def build_scraper():
    return MarketCaptureScraper()


def build_ai_analyzer():
    if not API_KEY:
        raise AIAnalyzerError(
            "API_KEY is not configured on the server."
        )

    if not LLM_MODEL:
        raise AIAnalyzerError(
            "LLM_MODEL is not configured on the server."
        )

    return AIAnalyzer(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=LLM_MODEL,
        app_name="Canon Wealth",
        app_url=APP_URL,
    )


def normalize_request_funds(request_funds):
    """
    Convert either frontend input format into the exact structure
    expected by MarketCaptureScraper.

    Search mode:
        [
            {
                "category": "...",
                "scheme": "..."
            }
        ]

    Paste mode:
        [
            "scheme one",
            "scheme two"
        ]

    Paste mode uses the scraper's category inference function.
    """

    if not request_funds:
        raise ValueError("No funds were provided.")

    all_strings = all(
        isinstance(item, str)
        for item in request_funds
    )

    all_objects = all(
        isinstance(item, FundSelection)
        for item in request_funds
    )

    if all_strings:
        pasted_text = "\n".join(
            item.strip()
            for item in request_funds
        )

        return get_funds_with_category(
            pasted_text
        )

    if all_objects:
        return [
            {
                "category": item.category.strip(),
                "scheme": item.scheme.strip(),
            }
            for item in request_funds
        ]

    raise ValueError(
        "Funds must use either search-selection format "
        "or pasted scheme-name format."
    )


def cleanup_file(file_path):
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass


# ============================================================
# FRONTEND
# ============================================================

@app.get("/", include_in_schema=False)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Canon-wealth-mutual-fund-analysis",
    }


# ============================================================
# FUND SEARCH
# ============================================================

@app.get("/api/schemes")
async def search_schemes(
    category: str = Query(
        ...,
        min_length=1,
        description="Exact AdvisorKhoj category.",
    ),
    query: str = Query(
        ...,
        min_length=2,
        description="Fund scheme search query.",
    ),
):
    """
    Search AdvisorKhoj fund schemes.

    Frontend calls:

        GET /api/schemes?category=Equity%3A%20Multi%20Cap&query=ICICI

    Returns a simple JSON array of scheme names because that directly
    matches the existing AdvisorKhoj autocomplete function.
    """

    category = category.strip()
    query = query.strip()

    if not category:
        raise HTTPException(
            status_code=400,
            detail="Category cannot be empty.",
        )

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    try:
        scraper = build_scraper()

        suggestions = await asyncio.to_thread(
            scraper.suggest_funds,
            query=query,
            category=category,
        )

        cleaned = [
            str(item).strip()
            for item in suggestions
            if str(item).strip()
        ]

        return cleaned

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to search AdvisorKhoj: {exc}",
        ) from exc


# ============================================================
# OPTIONAL CATEGORY ENDPOINT
# ============================================================

@app.get("/api/categories")
async def get_categories():
    """
    Exposes AdvisorKhoj categories.

    The current HTML contains the categories directly, but keeping
    this endpoint makes the backend capable of providing live
    categories in the future.
    """

    try:
        scraper = build_scraper()

        categories = await asyncio.to_thread(
            scraper.get_categories
        )

        return categories

    except FundDataError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to retrieve categories: {exc}",
        ) from exc


# ============================================================
# MAIN ANALYSIS PIPELINE
# ============================================================

@app.post(
    "/api/analyze",
    responses={
        200: {
            "content": {
                "application/pdf": {}
            }
        }
    },
)
async def analyze_funds(request: AnalysisRequest):

    report_path = None

    try:
        # --------------------------------------------------------
        # 1. Normalize and validate the selected/pasted funds
        # --------------------------------------------------------

        selected_funds = normalize_request_funds(
            request.funds
        )


        # --------------------------------------------------------
        # 2. AdvisorKhoj data retrieval
        #
        # This is synchronous HTTP + HTML parsing code, so move
        # it to a worker thread rather than blocking FastAPI's
        # async event loop.
        # --------------------------------------------------------

        scraper = build_scraper()

        funds = await asyncio.to_thread(
            scraper.fetch_multiple_ratios,
            selected_funds,
            request.period,
        )

        # --------------------------------------------------------
        # 3. Deterministic Python ranking
        # --------------------------------------------------------

        ranker = FundRanker()

        rankings = ranker.rank_all_preferences(
            funds
        )
        
        # --------------------------------------------------------
        # 4. AI analysis
        #
        # Python ranking has already been calculated.
        # The AI layer explains those rankings.
        # --------------------------------------------------------

        analyzer = build_ai_analyzer()

        analysis = await analyzer.analyze(
            funds=funds,
            rankings=rankings,
            period=request.period,
        )

        
        # --------------------------------------------------------
        # 5. Generate PDF
        # --------------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            prefix="Canon_mutual_fund_",
            suffix=".pdf",
            delete=False,
        )

        report_path = temp_file.name
        temp_file.close()

        report_generator = ReportGenerator(
            output_path=report_path
        )

        await asyncio.to_thread(
            report_generator.generate,
            funds,
            rankings,
            analysis,
            request.period,
        )

        # --------------------------------------------------------
        # 6. Return PDF directly to browser
        # --------------------------------------------------------

        filename = (
            "Canon_wealth_mutual_fund_analysis_"
            f"{request.period}Y.pdf"
        )

        return FileResponse(
            path=report_path,
            media_type="application/pdf",
            filename=filename,
            background=BackgroundTask(
                cleanup_file,
                report_path,
            ),
        )

    except ValueError as exc:

        if report_path:
            cleanup_file(report_path)

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FundDataError as exc:

        if report_path:
            cleanup_file(report_path)

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except AIAnalyzerError as exc:

        if report_path:
            cleanup_file(report_path)

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        if report_path:
            cleanup_file(report_path)

        raise HTTPException(
            status_code=500,
            detail=(
                "An unexpected error occurred while generating "
                f"the report: {exc}"
            ),
        ) from exc


# ============================================================
# DEVELOPMENT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mfs_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )