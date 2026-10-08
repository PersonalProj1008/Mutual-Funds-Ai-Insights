import asyncio
import json
import os

from openai import AsyncOpenAI


class AIAnalyzerError(Exception):
    """Raised when AI analysis fails."""
    pass


class AIAnalyzer:
    SUPPORTED_PERIODS = {"1", "3", "5", "10"}

    PREFERENCES = {
        "defensive": "Protect my downside",
        "balanced": "Balance growth & protection",
        "growth": "Maximize upside",
        "capture_efficiency": "Maximize capture efficiency",
        "historical_return": "Maximize historical returns",
    }

    def __init__(
        self,
        api_key,
        base_url,
        model,
        app_name="Principle Wealth",
        app_url=None,
    ):
        if not api_key:
            raise ValueError("api_key is required.")

        if not base_url:
            raise ValueError("base_url is required.")

        if not model:
            raise ValueError("model is required.")

        self.model = model

        default_headers = {
            "X-Title": app_name,
        }

        if app_url:
            default_headers["HTTP-Referer"] = app_url

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            default_headers=default_headers,
            timeout=90.0,
            max_retries=2,
        )

    async def analyze(self, funds, rankings, period):
        """
        Generate a report-ready AI analysis.

        Python is the source of truth for all ranks.
        The model only explains and summarizes the supplied results.
        """

        self._validate_inputs(funds, rankings, period)

        prompt = self._build_prompt(
            funds=funds,
            rankings=rankings,
            period=period,
        )

        result = await self._call_model(prompt)

        return self._validate_ai_result(
            result=result,
            rankings=rankings,
        )

    def _build_prompt(self, funds, rankings, period):
        fund_data = self._prepare_fund_data(funds)
        ranking_data = self._prepare_ranking_data(rankings)

        return f"""
You are the AI explanation and report-writing layer of a mutual-fund
comparison application.

You are NOT the ranking engine.

Python has already calculated the exact rankings. Your only job is to:
- explain those rankings clearly,
- compare the supplied funds,
- summarize the main findings,
- explain deterministic tie-breaks when they occur,
- produce concise, polished text suitable for a professional PDF.

============================================================
ABSOLUTE RULES
============================================================

1. NEVER change a rank.
2. NEVER invent, estimate, or recalculate missing fund data.
3. NEVER substitute your own ranking logic for the Python ranking.
4. Every explanation must correspond exactly to the supplied
   preference + rank + scheme_name.
5. Preserve fund names exactly as supplied.
6. Use only the supplied metrics.
7. A higher rank does NOT mean a fund is universally better.
   It means it ranked better under that particular investor lens.
8. Do not give personalized investment advice or tell the reader
   what they should buy.
9. Scheme Return is historical/backward-looking and must not be
   presented as a forecast.
10. Capture Spread is:
       Up Market Capture - Down Market Capture
    It is an APP-DEFINED comparative heuristic, not an official
    AdvisorKhoj metric.
11. Capture Ratio is the supplied AdvisorKhoj metric.
12. Do not confuse Down Market Capture with downside return itself.
    Explain it as the supplied capture metric: lower is preferred
    for the defensive lens.
13. Avoid generic filler such as "this analysis evaluates..." when
    writing the overall summary. The overall summary must describe
    the actual findings.

============================================================
INVESTOR LENSES
============================================================

defensive:
    Label: Protect my downside
    Primary criterion: lower Down Market Capture is better.

balanced:
    Label: Balance growth & protection
    Primary criterion: higher Capture Spread is better.
    Tie-breakers must follow the Python ranking data exactly.
    Capture Spread is app-defined.

growth:
    Label: Maximize upside
    Primary criterion: higher Up Market Capture is better.

capture_efficiency:
    Label: Maximize capture efficiency
    Primary criterion: higher Capture Ratio is better.

historical_return:
    Label: Maximize historical returns
    Primary criterion: higher Scheme Return is better.
    This is historical and backward-looking.

============================================================
HOW TO HANDLE TIES
============================================================

This is critical.

When two funds have the same primary metric, DO NOT stop at the
primary metric.

Use the exact ordering criteria supplied in each fund's
"ranking_basis" and the ranking itself.

For example, if two funds both have Capture Spread = 17.00 and one
is ranked #1 while the other is #2, explicitly explain the
secondary criterion that separates them.

Do NOT write:
"Fund A ranked first because both funds had the same spread."

Instead write the actual deterministic reason, such as:
"Both funds had a Capture Spread of 17.00, but Fund A ranked ahead
because its Capture Ratio was higher (1.21 vs 1.19)."

Only state a tiebreaker when it is supported by the supplied
ranking data.

============================================================
OVERALL SUMMARY
============================================================

The overall_summary must be a genuine finding-oriented synthesis.

It should:
- identify the main cross-lens pattern,
- identify which funds lead which lenses,
- mention meaningful consistency or divergence across lenses,
- mention when no single fund dominates every lens,
- remain comparative rather than advisory.

Aim for 3-5 sentences.

Do NOT merely describe what the application does.

============================================================
PREFERENCE SUMMARIES
============================================================

For each preference:
- explain what the lens reveals,
- identify the leading fund,
- mention the most meaningful metric difference,
- keep it to 2-4 sentences.

============================================================
RANKING EXPLANATIONS
============================================================

Provide exactly one explanation for EVERY ranked fund under EVERY
preference.

Each reason should:
- explain why that exact rank occurred,
- quote the relevant numeric metric(s),
- explain a deterministic tie-break when applicable,
- compare against the closest competing fund when helpful,
- be concise (1-3 sentences),
- never introduce unsupported claims.

============================================================
IMPORTANT NOTES
============================================================

Include useful methodological caveats, but do not repeat the same
note unnecessarily.

Period:
{period} years

============================================================
FUND DATA
============================================================

{json.dumps(fund_data, indent=2, ensure_ascii=False)}

============================================================
DETERMINISTIC RANKING DATA
============================================================

{json.dumps(ranking_data, indent=2, ensure_ascii=False)}

Return ONLY JSON matching the supplied schema.
""".strip()

    def _prepare_fund_data(self, funds):
        data = []

        for fund in funds:
            data.append({
                "scheme_name": fund.get("scheme_name"),
                "amc_name": fund.get("amc_name"),
                "benchmark_name": fund.get("benchmark_name"),
                "launch_date": fund.get("launch_date"),
                "scheme_return": fund.get("scheme_return"),
                "up_capture": fund.get("up_capture"),
                "down_capture": fund.get("down_capture"),
                "capture_ratio": fund.get("capture_ratio"),
            })

        return data

    def _prepare_ranking_data(self, rankings):
        data = {}

        for preference, ranked_funds in rankings.items():
            data[preference] = {
                "label": self.PREFERENCES.get(
                    preference,
                    preference,
                ),
                "ranking_order": [],
                "criteria": [],
                "funds": [],
            }

            for item in ranked_funds:
                data[preference]["ranking_order"].append({
                    "rank": item.get("rank"),
                    "scheme_name": item.get("scheme_name"),
                })

                data[preference]["funds"].append({
                    "rank": item.get("rank"),
                    "scheme_name": item.get("scheme_name"),
                    "ranking_basis": item.get("ranking_basis"),
                    "characteristics": item.get("characteristics"),
                    "up_capture": item.get("up_capture"),
                    "down_capture": item.get("down_capture"),
                    "capture_ratio": item.get("capture_ratio"),
                    "scheme_return": item.get("scheme_return"),
                    "capture_spread": item.get("capture_spread"),
                })

            if ranked_funds:
                basis = ranked_funds[0].get("ranking_basis")

                if isinstance(basis, list):
                    data[preference]["criteria"] = basis
                else:
                    data[preference]["criteria"] = [basis]

        return data

    async def _call_model(self, prompt):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "overall_summary": {
                    "type": "string",
                },
                "preference_summaries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "preference": {
                                "type": "string",
                            },
                            "winner": {
                                "type": "string",
                            },
                            "summary": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "preference",
                            "winner",
                            "summary",
                        ],
                    },
                },
                "ranking_explanations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "preference": {
                                "type": "string",
                            },
                            "rank": {
                                "type": "integer",
                            },
                            "scheme_name": {
                                "type": "string",
                            },
                            "reason": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "preference",
                            "rank",
                            "scheme_name",
                            "reason",
                        ],
                    },
                },
                "important_notes": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "overall_summary",
                "preference_summaries",
                "ranking_explanations",
                "important_notes",
            ],
        }

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise financial-analysis writer. "
                            "Follow the supplied deterministic rankings "
                            "exactly and never invent data."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "mutual_fund_analysis",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
        except Exception as exc:
            raise AIAnalyzerError(
                f"AI request failed: {exc}"
            ) from exc

        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise AIAnalyzerError(
                "AI returned an unexpected or invalid response."
            ) from exc

    def _validate_inputs(self, funds, rankings, period):
        if not isinstance(funds, list) or not funds:
            raise ValueError(
                "funds must be a non-empty list."
            )

        if not isinstance(rankings, dict) or not rankings:
            raise ValueError(
                "rankings must be a non-empty dictionary."
            )

        period = str(period).strip()

        if period not in self.SUPPORTED_PERIODS:
            raise ValueError(
                "period must be one of: 1, 3, 5, 10."
            )

        for fund in funds:
            if not isinstance(fund, dict):
                raise ValueError(
                    "Every fund must be a dictionary."
                )

            if not fund.get("scheme_name"):
                raise ValueError(
                    "Every fund must contain scheme_name."
                )

        for preference, ranked_funds in rankings.items():
            if preference not in self.PREFERENCES:
                raise ValueError(
                    f"Unsupported preference: {preference}"
                )

            if not isinstance(ranked_funds, list) or not ranked_funds:
                raise ValueError(
                    f"Ranking '{preference}' must contain funds."
                )

    def _validate_ai_result(self, result, rankings):
        if not isinstance(result, dict):
            raise AIAnalyzerError(
                "AI result must be a dictionary."
            )

        required_keys = {
            "overall_summary",
            "preference_summaries",
            "ranking_explanations",
            "important_notes",
        }

        missing = required_keys - set(result.keys())

        if missing:
            raise AIAnalyzerError(
                f"AI result is missing fields: {sorted(missing)}"
            )

        expected_pairs = set()

        for preference, ranked_funds in rankings.items():
            for ranked in ranked_funds:
                expected_pairs.add((
                    preference,
                    int(ranked.get("rank")),
                    ranked.get("scheme_name"),
                ))

        actual_pairs = set()

        for item in result["ranking_explanations"]:
            preference = item.get("preference")
            rank = item.get("rank")
            scheme_name = item.get("scheme_name")

            if preference not in rankings:
                raise AIAnalyzerError(
                    f"AI returned unknown preference: {preference}"
                )

            try:
                rank = int(rank)
            except (TypeError, ValueError) as exc:
                raise AIAnalyzerError(
                    f"AI returned invalid rank: {rank}"
                ) from exc

            pair = (
                preference,
                rank,
                scheme_name,
            )

            if pair in actual_pairs:
                raise AIAnalyzerError(
                    f"AI returned a duplicate explanation: {pair}"
                )

            actual_pairs.add(pair)

        if actual_pairs != expected_pairs:
            missing_pairs = expected_pairs - actual_pairs
            extra_pairs = actual_pairs - expected_pairs

            raise AIAnalyzerError(
                "AI ranking explanations do not exactly match the "
                f"deterministic rankings. Missing: {missing_pairs}; "
                f"Extra: {extra_pairs}"
            )

        expected_preferences = set(rankings.keys())
        actual_preferences = {
            item.get("preference")
            for item in result["preference_summaries"]
        }

        if actual_preferences != expected_preferences:
            raise AIAnalyzerError(
                "AI preference summaries do not cover exactly the "
                "same preferences as the deterministic rankings."
            )

        expected_winners = {
            preference: ranked_funds[0].get("scheme_name")
            for preference, ranked_funds in rankings.items()
        }

        for item in result["preference_summaries"]:
            preference = item.get("preference")
            winner = item.get("winner")

            if preference not in expected_winners:
                raise AIAnalyzerError(
                    f"AI returned unknown preference summary: {preference}"
                )

            if winner != expected_winners[preference]:
                raise AIAnalyzerError(
                    f"AI winner mismatch for '{preference}': "
                    f"expected '{expected_winners[preference]}', "
                    f"got '{winner}'"
                )

        return result


# async def main():
#     analyzer = AIAnalyzer(
#         api_key=os.getenv("OPENROUTER_API_KEY"),
#         base_url=os.getenv(
#             "OPENROUTER_BASE_URL",
#             "https://openrouter.ai/api/v1",
#         ),
#         model=os.getenv(
#             "OPENROUTER_MODEL",
#             "google/gemini-3.1-flash-lite",
#         ),
#         app_name="Principle Wealth",
#     )

#     print("AIAnalyzer initialized successfully.")
#     print(f"Model: {analyzer.model}")
#     print(f"Base URL: {analyzer.client.base_url}")


# if __name__ == "__main__":
#     asyncio.run(main())
