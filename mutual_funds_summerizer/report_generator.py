
from pathlib import Path
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


class ReportGenerator:
    """
    Production-grade A4 mutual-fund comparative research report generator.

    The analytical inputs and ranking logic remain external to this class.
    This layer is responsible for presenting the supplied analysis in a
    polished, client-friendly, institutional-style report.

    Accessibility principle:
    Every specialised investment term is presented with a formal definition,
    a plain-English explanation, and (where helpful) a contextual alert.
    """

    PAGE_WIDTH, PAGE_HEIGHT = A4

    # ------------------------------------------------------------------
    # Corporate visual system
    # ------------------------------------------------------------------

    NAVY = colors.HexColor("#15324B")
    INK = colors.HexColor("#1F2D38")
    BLUE = colors.HexColor("#2F6BFF")
    CYAN = colors.HexColor("#0E9FC1")
    GREEN = colors.HexColor("#168A63")
    ORANGE = colors.HexColor("#D98524")
    RED = colors.HexColor("#C94A5B")
    PURPLE = colors.HexColor("#6D56C9")

    TEXT = colors.HexColor("#26343F")
    MUTED = colors.HexColor("#71808D")
    SOFT_TEXT = colors.HexColor("#87939D")
    LIGHT_BG = colors.HexColor("#F6F8FB")
    PALE_BLUE = colors.HexColor("#EEF4FF")
    PALE_GREEN = colors.HexColor("#EEF8F4")
    PALE_ORANGE = colors.HexColor("#FFF6E9")
    PALE_PURPLE = colors.HexColor("#F4F0FF")
    PALE_CYAN = colors.HexColor("#ECF9FC")
    PALE_RED = colors.HexColor("#FFF1F3")
    BORDER = colors.HexColor("#DDE5EC")
    BORDER_DARK = colors.HexColor("#C8D3DC")
    WHITE = colors.white

    LENS_META = {
        "defensive": {
            "label": "Downside Protection",
            "short": "Downside Protection",
            "color": GREEN,
            "soft": PALE_GREEN,
            "metric": "Lower Down-Market Capture",
            "description": (
                "Prioritises relative resilience during benchmark down-market "
                "periods."
            ),
            "plain": (
                "In simple terms: favour funds that historically participated "
                "less in market declines."
            ),
        },
        "balanced": {
            "label": "Balanced Participation",
            "short": "Balanced Participation",
            "color": BLUE,
            "soft": PALE_BLUE,
            "metric": "Higher Capture Differential",
            "description": (
                "Balances participation in up markets against participation "
                "in down markets."
            ),
            "plain": (
                "In simple terms: look for more upside participation relative "
                "to downside participation."
            ),
        },
        "growth": {
            "label": "Upside Participation",
            "short": "Upside Participation",
            "color": ORANGE,
            "soft": PALE_ORANGE,
            "metric": "Higher Up-Market Capture",
            "description": (
                "Prioritises stronger historical participation during benchmark "
                "up-market periods."
            ),
            "plain": (
                "In simple terms: favour funds that historically captured more "
                "of rising markets."
            ),
        },
        "capture_efficiency": {
            "label": "Capture Efficiency",
            "short": "Capture Efficiency",
            "color": PURPLE,
            "soft": PALE_PURPLE,
            "metric": "Higher Capture Ratio",
            "description": (
                "Prioritises the supplied capture-ratio measure as an efficiency "
                "indicator."
            ),
            "plain": (
                "In simple terms: compare a source-provided measure of how the "
                "fund participated across market phases."
            ),
        },
        "historical_return": {
            "label": "Historical Return",
            "short": "Historical Return",
            "color": CYAN,
            "soft": PALE_CYAN,
            "metric": "Higher Scheme Return",
            "description": (
                "Prioritises historical scheme return over the selected "
                "review period."
            ),
            "plain": (
                "In simple terms: compare how much the fund grew historically "
                "over the selected period."
            ),
        },
    }

    # Formal terminology -> accessible communication layer.
    TERMINOLOGY = [
        {
            "term": "Benchmark",
            "definition": (
                "The reference market index used to assess a scheme's relative "
                "performance and market participation."
            ),
            "layman": "Think of it as the fund's comparison yardstick.",
            "alert": (
                "A benchmark is not a guaranteed return and is not the same "
                "as a risk-free investment."
            ),
            "tone": BLUE,
            "soft": PALE_BLUE,
        },
        {
            "term": "Historical Return",
            "definition": (
                "The scheme's observed return over the selected historical "
                "review period."
            ),
            "layman": "How much the investment grew or declined in the past.",
            "alert": (
                "Past performance is backward-looking and does not predict "
                "future performance."
            ),
            "tone": CYAN,
            "soft": PALE_CYAN,
        },
        {
            "term": "Up-Market Capture",
            "definition": (
                "A measure of how much of the benchmark's positive-market "
                "participation the scheme historically captured."
            ),
            "layman": "How strongly the fund tended to participate when the "
                      "market was rising.",
            "alert": (
                "A value above 100% indicates stronger historical participation "
                "than the benchmark during the relevant up-market periods."
            ),
            "tone": ORANGE,
            "soft": PALE_ORANGE,
        },
        {
            "term": "Down-Market Capture",
            "definition": (
                "A measure of how much of the benchmark's negative-market "
                "participation the scheme historically captured."
            ),
            "layman": "How much of the market's decline the fund tended to "
                      "participate in when the market was falling.",
            "alert": (
                "Lower values can be favourable under a downside-protection "
                "objective, but the preferred value depends on the objective "
                "being assessed."
            ),
            "tone": GREEN,
            "soft": PALE_GREEN,
        },
        {
            "term": "Capture Ratio",
            "definition": (
                "The capture-ratio measure supplied by the source dataset and "
                "used as one comparative indicator in the assessment."
            ),
            "layman": "A single number used here to compare market-capture "
                      "efficiency across schemes.",
            "alert": (
                "This report uses the supplied source value exactly as provided; "
                "it is not recalculated within the reporting layer."
            ),
            "tone": PURPLE,
            "soft": PALE_PURPLE,
        },
        {
            "term": "Capture Differential",
            "definition": (
                "An application-defined comparative measure calculated as "
                "Up-Market Capture minus Down-Market Capture."
            ),
            "layman": "The difference between how much upside and downside the "
                      "fund historically participated in.",
            "alert": (
                "This is a report-level comparative heuristic, not an official "
                "source metric."
            ),
            "tone": BLUE,
            "soft": PALE_BLUE,
        },
    ]

    def __init__(self, output_path):
        self.output_path = Path(output_path)
        self.styles = self._build_styles()

    def generate(self, funds, rankings, analysis, period):
        self._validate_input(funds, rankings, analysis, period)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        document = BaseDocTemplate(
            str(self.output_path),
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=19 * mm,
            bottomMargin=17 * mm,
            title="Principle Wealth | Mutual Fund Comparative Analysis",
            author="Principle Wealth",
            subject="Institutional-style mutual fund comparative analysis",
        )

        frame = Frame(
            document.leftMargin,
            document.bottomMargin,
            document.width,
            document.height,
            id="main",
        )

        document.addPageTemplates(
            [
                PageTemplate(
                    id="report",
                    frames=[frame],
                    onPage=self._draw_page,
                )
            ]
        )

        story = []
        story.extend(self._build_cover_section(funds, period))
        story.extend(self._build_executive_summary(analysis))
        story.extend(self._build_fund_snapshot(funds))

        story.extend(self._build_terminology_guide())

        story.append(PageBreak())
        story.extend(
            self._build_lens_overview(
                rankings=rankings,
                analysis=analysis,
            )
        )

        story.append(PageBreak())
        story.extend(
            self._build_detailed_rankings(
                funds=funds,
                rankings=rankings,
                analysis=analysis,
            )
        )

        story.extend(self._build_methodology(period))
        document.build(story)
        return str(self.output_path)

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _build_styles(self):
        styles = getSampleStyleSheet()

        return {
            "cover_kicker": ParagraphStyle(
                "CoverKicker",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=self.BLUE,
                spaceAfter=4,
            ),
            "title": ParagraphStyle(
                "ReportTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=25,
                leading=29,
                textColor=self.NAVY,
                alignment=TA_LEFT,
                spaceAfter=5,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=10.2,
                leading=14,
                textColor=self.MUTED,
                spaceAfter=9,
            ),
            "section": ParagraphStyle(
                "Section",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=17,
                leading=21,
                textColor=self.NAVY,
                spaceBefore=1,
                spaceAfter=5,
            ),
            "section_num": ParagraphStyle(
                "SectionNum",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=9,
                textColor=self.BLUE,
                spaceAfter=3,
            ),
            "subsection": ParagraphStyle(
                "Subsection",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=10.5,
                leading=14,
                textColor=self.TEXT,
                spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "Body",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=9,
                leading=13.2,
                textColor=self.TEXT,
                spaceAfter=6,
            ),
            "body_compact": ParagraphStyle(
                "BodyCompact",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=8.1,
                leading=11.3,
                textColor=self.TEXT,
                spaceAfter=3,
            ),
            "small": ParagraphStyle(
                "Small",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=7.3,
                leading=9.6,
                textColor=self.MUTED,
            ),
            "tiny": ParagraphStyle(
                "Tiny",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=6.7,
                leading=8.8,
                textColor=self.MUTED,
            ),
            "metric_label": ParagraphStyle(
                "MetricLabel",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=6.7,
                leading=8.5,
                textColor=self.MUTED,
            ),
            "metric_value": ParagraphStyle(
                "MetricValue",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=15,
                textColor=self.NAVY,
            ),
            "rank": ParagraphStyle(
                "Rank",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=self.WHITE,
                alignment=TA_CENTER,
            ),
            "fund": ParagraphStyle(
                "Fund",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=8.7,
                leading=11.5,
                textColor=self.TEXT,
            ),
            "fund_meta": ParagraphStyle(
                "FundMeta",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=7.2,
                leading=9.5,
                textColor=self.MUTED,
            ),
            "reason": ParagraphStyle(
                "Reason",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=8.1,
                leading=11.4,
                textColor=self.TEXT,
            ),
            "callout": ParagraphStyle(
                "Callout",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=8.4,
                leading=11,
                textColor=self.NAVY,
            ),
            "white_callout": ParagraphStyle(
                "WhiteCallout",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=8.4,
                leading=11,
                textColor=self.WHITE,
            ),
            "term_title": ParagraphStyle(
                "TermTitle",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=8.7,
                leading=10.5,
                textColor=self.NAVY,
                spaceAfter=2,
            ),
            "term_body": ParagraphStyle(
                "TermBody",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=self.TEXT,
                spaceAfter=2,
            ),
            "term_layman": ParagraphStyle(
                "TermLayman",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=10,
                textColor=self.TEXT,
                spaceAfter=2,
            ),
            "alert": ParagraphStyle(
                "Alert",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=7.0,
                leading=9.2,
                textColor=self.TEXT,
            ),
        }

    # ------------------------------------------------------------------
    # Page chrome
    # ------------------------------------------------------------------

    def _draw_page(self, canvas, document):
        canvas.saveState()

        if document.page > 1:
            canvas.setFillColor(self.NAVY)
            canvas.rect(
                0,
                self.PAGE_HEIGHT - 3.5 * mm,
                self.PAGE_WIDTH,
                3.5 * mm,
                fill=1,
                stroke=0,
            )

            canvas.setStrokeColor(self.BORDER)
            canvas.setLineWidth(0.55)
            canvas.line(
                document.leftMargin,
                self.PAGE_HEIGHT - 11.5 * mm,
                self.PAGE_WIDTH - document.rightMargin,
                self.PAGE_HEIGHT - 11.5 * mm,
            )

            canvas.setFont("Helvetica-Bold", 7.2)
            canvas.setFillColor(self.NAVY)
            canvas.drawString(
                document.leftMargin,
                self.PAGE_HEIGHT - 9.5 * mm,
                "PRINCIPLE WEALTH",
            )

            canvas.setFont("Helvetica", 6.8)
            canvas.setFillColor(self.MUTED)
            canvas.drawRightString(
                self.PAGE_WIDTH - document.rightMargin,
                self.PAGE_HEIGHT - 9.5 * mm,
                "MUTUAL FUND COMPARATIVE ANALYSIS",
            )

        canvas.setStrokeColor(self.BORDER)
        canvas.setLineWidth(0.45)
        canvas.line(
            document.leftMargin,
            10 * mm,
            self.PAGE_WIDTH - document.rightMargin,
            10 * mm,
        )

        canvas.setFont("Helvetica", 6.7)
        canvas.setFillColor(self.SOFT_TEXT)
        canvas.drawString(
            document.leftMargin,
            6.3 * mm,
            "For research and comparative purposes. Historical observations do not indicate future outcomes.",
        )

        canvas.drawRightString(
            self.PAGE_WIDTH - document.rightMargin,
            6.3 * mm,
            f"PAGE {document.page}",
        )

        canvas.restoreState()

    # ------------------------------------------------------------------
    # Cover
    # ------------------------------------------------------------------

    def _build_cover_section(self, funds, period):
        story = [
            Spacer(1, 4 * mm),
            Paragraph(
                "PRINCIPLE WEALTH  /  INVESTMENT RESEARCH",
                self.styles["cover_kicker"],
            ),
            Paragraph(
                "Mutual Fund<br/>Comparative Analysis",
                self.styles["title"],
            ),
            Paragraph(
                f"{period}-Year Market Capture Review & Comparative Assessment",
                self.styles["subtitle"],
            ),
        ]

        hero = Table(
            [[
                Paragraph(
                    "<b>Research objective</b><br/>"
                    "Evaluate the selected schemes across distinct investor objectives "
                    "using a consistent, rules-based comparative framework.",
                    self.styles["white_callout"],
                ),
                Paragraph(
                    "<b>Interpretation principle</b><br/>"
                    "A leading scheme under one objective may not lead under another. "
                    "The report is designed to make those trade-offs visible.",
                    self.styles["white_callout"],
                ),
            ]],
            colWidths=[86 * mm, 86 * mm],
        )
        hero.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.NAVY),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(hero)
        story.append(Spacer(1, 7 * mm))

        kpis = [
            ("SELECTED SCHEMES", str(len(funds))),
            ("REVIEW PERIOD", f"{period} YEARS"),
            ("ASSESSMENT DIMENSIONS", "5"),
            ("REPORT TYPE", "COMPARATIVE"),
        ]
        cells = []
        for label, value in kpis:
            cells.append(
                [
                    Paragraph(label, self.styles["metric_label"]),
                    Paragraph(value, self.styles["metric_value"]),
                ]
            )

        kpi_table = Table([cells], colWidths=[43 * mm] * 4)
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.LIGHT_BG),
                    ("BOX", (0, 0), (-1, -1), 0.65, self.BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.45, self.BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 7 * mm))

        story.append(self._section_heading("01", "Executive Perspective"))
        story.append(
            Paragraph(
                "This report is designed to support structured fund comparison rather "
                "than produce a single universal winner. Each scheme is assessed through "
                "five distinct objectives so that relative strengths, weaknesses and "
                "trade-offs can be understood in context.",
                self.styles["body"],
            )
        )

        reader_note = Table(
            [[
                Paragraph(
                    "<b>How to read this report</b><br/>"
                    "Technical terms are accompanied by plain-English explanations. "
                    "Where a metric is application-defined or objective-specific, "
                    "an explicit terminology alert is shown.",
                    self.styles["body_compact"],
                )
            ]],
            colWidths=[172 * mm],
        )
        reader_note.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.6, self.BORDER),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, self.BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(reader_note)
        story.append(Spacer(1, 6 * mm))

        story.append(
            Paragraph(
                "Prepared using supplied source data and comparative analysis inputs "
                "provided to the reporting layer.",
                self.styles["tiny"],
            )
        )

        return story

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    def _build_executive_summary(self, analysis):
        story = [
            self._section_heading("02", "Executive Summary"),
            Paragraph(
                self._safe_text(
                    analysis.get(
                        "overall_summary",
                        "The comparative assessment highlights relative strengths "
                        "across the selected schemes and investor objectives.",
                    )
                ),
                self.styles["body"],
            ),
        ]

        summaries = analysis.get("preference_summaries", [])
        if summaries:
            cards = []
            for item in summaries[:5]:
                preference = item.get("preference", "")
                meta = self.LENS_META.get(
                    preference,
                    {
                        "short": preference or "Assessment",
                        "color": self.BLUE,
                        "soft": self.PALE_BLUE,
                    },
                )
                cards.append(
                    [
                        Paragraph(
                            self._safe_text(meta["short"]).upper(),
                            self.styles["metric_label"],
                        ),
                        Paragraph(
                            self._safe_text(item.get("summary", "")),
                            self.styles["body_compact"],
                        ),
                    ]
                )

            summary_table = Table(
                [cards],
                colWidths=[34.4 * mm] * len(cards),
            )
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), self.LIGHT_BG),
                        ("BOX", (0, 0), (-1, -1), 0.6, self.BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.45, self.BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story.append(summary_table)
            story.append(Spacer(1, 6 * mm))

        return story

    # ------------------------------------------------------------------
    # Fund snapshot
    # ------------------------------------------------------------------

    def _build_fund_snapshot(self, funds):
        story = [
            self._section_heading("03", "Selected Fund Snapshot"),
            Paragraph(
                "A consolidated view of the supplied historical performance and "
                "market-capture indicators. A terminology alert is included below "
                "the table to reduce the risk of misreading the figures.",
                self.styles["body"],
            ),
        ]

        headers = [
            "Scheme",
            "Historical<br/>Return",
            "Up-Market<br/>Capture",
            "Down-Market<br/>Capture",
            "Capture<br/>Ratio",
            "Capture<br/>Differential",
        ]
        rows = [[
            Paragraph(h, self.styles["small"]) for h in headers
        ]]

        for fund in funds:
            spread = float(fund["up_capture"]) - float(fund["down_capture"])
            rows.append(
                [
                    Paragraph(
                        f"<b>{self._safe_text(fund['scheme_name'])}</b><br/>"
                        f"<font size='6.7'>{self._safe_text(fund.get('amc_name', ''))}</font>",
                        self.styles["fund"],
                    ),
                    Paragraph(
                        self._format_percent(fund["scheme_return"]),
                        self.styles["small"],
                    ),
                    Paragraph(
                        self._format_percent(fund["up_capture"]),
                        self.styles["small"],
                    ),
                    Paragraph(
                        self._format_percent(fund["down_capture"]),
                        self.styles["small"],
                    ),
                    Paragraph(
                        self._format_ratio(fund["capture_ratio"]),
                        self.styles["small"],
                    ),
                    Paragraph(
                        self._format_pp(spread),
                        self.styles["small"],
                    ),
                ]
            )

        table = LongTable(
            rows,
            colWidths=[66 * mm, 20 * mm, 23 * mm, 25 * mm, 22 * mm, 20 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), self.WHITE),
                    ("BACKGROUND", (0, 1), (-1, -1), self.WHITE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [self.WHITE, self.LIGHT_BG]),
                    ("GRID", (0, 0), (-1, -1), 0.45, self.BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 3.5 * mm))

        story.append(
            self._terminology_alert(
                title="Terminology alert: Capture Differential",
                text=(
                    "<b>Formula:</b> Up-Market Capture minus Down-Market Capture. "
                    "<b>Layman view:</b> the gap between how much upside and downside "
                    "the fund historically participated in. It is useful for the "
                    "balanced comparison in this report, but it is an application-defined "
                    "heuristic rather than an official source metric."
                ),
                tone=self.BLUE,
            )
        )
        story.append(Spacer(1, 4 * mm))

        story.append(
            Paragraph(
                "<b>Benchmark reference:</b> each scheme is evaluated against the "
                "benchmark supplied by the source dataset for that scheme.",
                self.styles["small"],
            )
        )
        return story

    # ------------------------------------------------------------------
    # Terminology guide
    # ------------------------------------------------------------------

    def _build_terminology_guide(self):
        story = [
            self._section_heading("04", "Terminology Guide"),
            Paragraph(
                "Designed for readers with different levels of investment knowledge. "
                "Formal research terminology is paired with plain-English definitions "
                "and practical alerts.",
                self.styles["body"],
            ),
        ]

        cards = []
        for item in self.TERMINOLOGY:
            inner = Table(
                [[
                    [
                        Paragraph(
                            self._safe_text(item["term"]),
                            self.styles["term_title"],
                        ),
                        Paragraph(
                            f"<b>Formal definition:</b> "
                            f"{self._safe_text(item['definition'])}",
                            self.styles["term_body"],
                        ),
                        Paragraph(
                            f"<b>In simple terms:</b> "
                            f"{self._safe_text(item['layman'])}",
                            self.styles["term_layman"],
                        ),
                        Paragraph(
                            f"<b>Important:</b> "
                            f"{self._safe_text(item['alert'])}",
                            self.styles["alert"],
                        ),
                    ]
                ]],
                colWidths=[82.5 * mm],
            )
            inner.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), item["soft"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, self.BORDER),
                        ("LINEBEFORE", (0, 0), (0, -1), 3, item["tone"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            cards.append(inner)

        rows = []
        for i in range(0, len(cards), 2):
            right = cards[i + 1] if i + 1 < len(cards) else Spacer(1, 1)
            rows.append([cards[i], right])

        glossary = Table(
            rows,
            colWidths=[84 * mm, 84 * mm],
            hAlign="LEFT",
        )
        glossary.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            )
        )
        story.append(glossary)
        story.append(Spacer(1, 0.5 * mm))
        return story

    # ------------------------------------------------------------------
    # Investor lens overview
    # ------------------------------------------------------------------

    def _build_lens_overview(self, rankings, analysis):
        story = [
            self._section_heading("05", "Investor Objective Overview"),
            Paragraph(
                "The same set of schemes can produce different leaders depending on "
                "the investment objective under review. This section explains the "
                "objective behind each ranking before showing detailed positions.",
                self.styles["body"],
            ),
        ]

        summaries = {
            item.get("preference"): item
            for item in analysis.get("preference_summaries", [])
        }

        for preference, ranked_funds in rankings.items():
            if not ranked_funds:
                continue

            meta = self.LENS_META.get(
                preference,
                {
                    "label": preference,
                    "short": preference,
                    "color": self.BLUE,
                    "soft": self.PALE_BLUE,
                    "metric": "",
                    "description": "",
                    "plain": "",
                },
            )

            winner = ranked_funds[0]
            summary = summaries.get(preference, {}).get("summary", "")

            header = Table(
                [[
                    Paragraph(
                        f"<b>{self._safe_text(meta['short']).upper()}</b><br/>"
                        f"<font size='6.5'>{self._safe_text(meta['metric'])}</font>",
                        self.styles["white_callout"],
                    ),
                    Paragraph(
                        f"<b>LEADING SCHEME</b><br/>"
                        f"<font size='10'>{self._safe_text(winner['scheme_name'])}</font>",
                        self.styles["callout"],
                    ),
                ]],
                colWidths=[58 * mm, 114 * mm],
            )
            header.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), meta["color"]),
                        ("TEXTCOLOR", (0, 0), (0, 0), self.WHITE),
                        ("BACKGROUND", (1, 0), (1, 0), meta["soft"]),
                        ("BOX", (0, 0), (-1, -1), 0.6, self.BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )

            story.append(header)
            story.append(Spacer(1, 1.5 * mm))

            body = (
                f"<b>Assessment focus:</b> {self._safe_text(meta['description'])}"
                f"<br/><b>In simple terms:</b> {self._safe_text(meta['plain'])}"
            )
            if summary:
                body += (
                    f"<br/><b>Comparative read:</b> "
                    f"{self._safe_text(summary)}"
                )

            story.append(
                Paragraph(body, self.styles["body_compact"])
            )
            story.append(Spacer(1, 4 * mm))

        story.append(
            self._terminology_alert(
                title="Objective alert",
                text=(
                    "A rank of #1 means #1 within the selected funds and the specific "
                    "objective shown. It does not mean the scheme is universally the "
                    "best fund for every investor."
                ),
                tone=self.RED,
                soft=self.PALE_RED,
            )
        )
        return story

    # ------------------------------------------------------------------
    # Detailed rankings
    # ------------------------------------------------------------------

    def _build_detailed_rankings(self, funds, rankings, analysis):
        story = [
            self._section_heading("06", "Detailed Comparative Rankings"),
            Paragraph(
                "Rankings are produced from the supplied metrics using the defined "
                "comparative rules for each investor objective. Interpretive commentary "
                "is presented after the comparative position has been established.",
                self.styles["body"],
            ),
        ]

        explanation_lookup = {}
        for item in analysis.get("ranking_explanations", []):
            key = (
                item.get("preference"),
                int(item.get("rank", 0)),
                item.get("scheme_name"),
            )
            explanation_lookup[key] = item.get("reason", "")

        fund_lookup = {
            fund["scheme_name"]: fund
            for fund in funds
        }

        for preference, ranked_funds in rankings.items():
            if not ranked_funds:
                continue

            meta = self.LENS_META.get(
                preference,
                {
                    "label": preference,
                    "short": preference,
                    "color": self.BLUE,
                    "soft": self.PALE_BLUE,
                    "metric": "",
                },
            )

            lens_title = Table(
                [[
                    Paragraph(
                        self._safe_text(meta["short"]).upper(),
                        self.styles["white_callout"],
                    ),
                    Paragraph(
                        f"<b>Assessment criterion:</b> "
                        f"{self._safe_text(meta['metric'])}",
                        self.styles["small"],
                    ),
                ]],
                colWidths=[68 * mm, 104 * mm],
            )
            lens_title.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), meta["color"]),
                        ("TEXTCOLOR", (0, 0), (0, 0), self.WHITE),
                        ("BACKGROUND", (1, 0), (1, 0), meta["soft"]),
                        ("BOX", (0, 0), (-1, -1), 0.6, self.BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(lens_title)
            story.append(Spacer(1, 1.5 * mm))

            for ranked in ranked_funds:
                scheme_name = ranked["scheme_name"]
                rank = int(ranked["rank"])
                fund = fund_lookup.get(scheme_name, {})

                reason = explanation_lookup.get(
                    (preference, rank, scheme_name),
                    "No interpretive commentary was supplied for this position.",
                )

                spread = ranked.get("capture_spread")
                if spread is None and fund:
                    spread = (
                        float(fund.get("up_capture", 0))
                        - float(fund.get("down_capture", 0))
                    )

                metrics = (
                    f"Historical return {self._format_percent(fund.get('scheme_return'))}"
                    f"  |  Up-market {self._format_percent(fund.get('up_capture'))}"
                    f"  |  Down-market {self._format_percent(fund.get('down_capture'))}"
                    f"  |  Capture ratio {self._format_ratio(fund.get('capture_ratio'))}"
                )
                if spread is not None:
                    metrics += f"  |  Capture differential {self._format_pp(spread)}"

                row = Table(
                    [[
                        Paragraph(str(rank), self.styles["rank"]),
                        [
                            Paragraph(
                                self._safe_text(scheme_name),
                                self.styles["fund"],
                            ),
                            Paragraph(
                                self._safe_text(fund.get("benchmark_name", "")),
                                self.styles["fund_meta"],
                            ),
                            Paragraph(metrics, self.styles["fund_meta"]),
                        ],
                        Paragraph(
                            self._safe_text(reason),
                            self.styles["reason"],
                        ),
                    ]],
                    colWidths=[10 * mm, 72 * mm, 90 * mm],
                )
                row.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, 0), meta["color"]),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BACKGROUND", (1, 0), (-1, 0), self.WHITE),
                            ("BOX", (0, 0), (-1, -1), 0.45, self.BORDER),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )

                story.append(row)
                story.append(Spacer(1, 1.7 * mm))

            story.append(Spacer(1, 2 * mm))

        story.append(
            self._terminology_alert(
                title="Ranking interpretation alert",
                text=(
                    "The ranking is comparative, not absolute. A scheme can rank highly "
                    "because it fits one objective particularly well while presenting "
                    "different characteristics under another objective."
                ),
                tone=self.BLUE,
                soft=self.PALE_BLUE,
            )
        )

        return story

    # ------------------------------------------------------------------
    # Methodology & disclosures
    # ------------------------------------------------------------------

    def _build_methodology(self, period):
        story = [
            PageBreak(),
            self._section_heading("07", "Methodology & Interpretation"),
            Paragraph(
                f"The report uses the supplied AdvisorKhoj Market Capture Ratio data "
                f"for the selected {period}-year review period. The comparative position "
                "of each scheme is established through defined ranking rules before "
                "interpretive commentary is applied.",
                self.styles["body"],
            ),
        ]

        methodology_rows = [
            [
                Paragraph("<b>Investor objective</b>", self.styles["small"]),
                Paragraph("<b>Comparative criterion</b>", self.styles["small"]),
                Paragraph("<b>Interpretation</b>", self.styles["small"]),
            ],
            [
                Paragraph("Downside Protection", self.styles["small"]),
                Paragraph("Lower Down-Market Capture", self.styles["small"]),
                Paragraph(
                    "Lower values indicate relatively lower participation "
                    "during benchmark down-market periods.",
                    self.styles["small"],
                ),
            ],
            [
                Paragraph("Balanced Participation", self.styles["small"]),
                Paragraph("Higher Capture Differential", self.styles["small"]),
                Paragraph(
                    "Capture Differential = Up-Market Capture minus Down-Market "
                    "Capture. This is an application-defined comparative heuristic.",
                    self.styles["small"],
                ),
            ],
            [
                Paragraph("Upside Participation", self.styles["small"]),
                Paragraph("Higher Up-Market Capture", self.styles["small"]),
                Paragraph(
                    "Higher values indicate greater historical participation "
                    "during benchmark up-market periods.",
                    self.styles["small"],
                ),
            ],
            [
                Paragraph("Capture Efficiency", self.styles["small"]),
                Paragraph("Higher Capture Ratio", self.styles["small"]),
                Paragraph(
                    "Uses the supplied source capture-ratio measure as provided "
                    "in the dataset.",
                    self.styles["small"],
                ),
            ],
            [
                Paragraph("Historical Return", self.styles["small"]),
                Paragraph("Higher Scheme Return", self.styles["small"]),
                Paragraph(
                    "Backward-looking historical performance measure for the "
                    "selected review period.",
                    self.styles["small"],
                ),
            ],
        ]

        methodology = LongTable(
            methodology_rows,
            colWidths=[46 * mm, 48 * mm, 78 * mm],
            repeatRows=1,
        )
        methodology.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), self.WHITE),
                    ("GRID", (0, 0), (-1, -1), 0.45, self.BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [self.WHITE, self.LIGHT_BG]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(methodology)
        story.append(Spacer(1, 6 * mm))

        story.append(Paragraph("Important Considerations", self.styles["subsection"]))

        notes = [
            "Historical Return is backward-looking and does not predict future performance.",
            "Capture Differential is calculated by the application as Up-Market Capture minus Down-Market Capture and is not an official source metric.",
            "Capture Ratio is used exactly as supplied by the source dataset.",
            "Rankings are comparative among the selected schemes and depend on the investor objective being assessed.",
            "The report is intended for informational and comparative purposes and does not constitute personalised investment advice.",
        ]

        for note in notes:
            story.append(
                Paragraph(
                    f"- {self._safe_text(note)}",
                    self.styles["body_compact"],
                )
            )

        story.append(Spacer(1, 4 * mm))

        story.append(
            self._terminology_alert(
                title="Language convention used throughout this report",
                text=(
                    "<b>Formal label</b> identifies the analytical metric. "
                    "<b>In simple terms</b> translates the same concept for non-specialist "
                    "readers. <b>Important</b> flags cases where the metric is objective-specific, "
                    "source-provided or application-defined."
                ),
                tone=self.NAVY,
                soft=self.PALE_BLUE,
            )
        )
        story.append(Spacer(1, 5 * mm))

        source_box = Table(
            [[
                Paragraph(
                    "<b>DATA SOURCE</b><br/>"
                    "AdvisorKhoj Market Capture Ratio",
                    self.styles["small"],
                ),
                Paragraph(
                    "<b>ANALYTICAL FRAMEWORK</b><br/>"
                    "Rules-based comparative ranking with AI-assisted interpretation",
                    self.styles["small"],
                ),
            ]],
            colWidths=[86 * mm, 86 * mm],
        )
        source_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.LIGHT_BG),
                    ("BOX", (0, 0), (-1, -1), 0.65, self.BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.45, self.BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(source_box)
        story.append(Spacer(1, 5 * mm))

        story.append(
            Paragraph(
                "This document is a comparative research output. It should be considered "
                "alongside scheme objectives, risk characteristics, costs, taxation, "
                "liquidity, portfolio context and the investor's own circumstances.",
                self.styles["tiny"],
            )
        )

        return story

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _section_heading(self, number, title):
        return KeepTogether(
            [
                Paragraph(f"SECTION {number}", self.styles["section_num"]),
                Paragraph(title, self.styles["section"]),
                *self._accent_rule(),
            ]
        )

    def _accent_rule(self):
        rule = Table([[""]], colWidths=[172 * mm], rowHeights=[1.2 * mm])
        rule.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.BLUE),
                    ("BOX", (0, 0), (-1, -1), 0, self.BLUE),
                ]
            )
        )
        return Spacer(1, 1.5 * mm), rule, Spacer(1, 3 * mm)

    def _terminology_alert(self, title, text, tone, soft=None):
        soft = soft or self.LIGHT_BG
        box = Table(
            [[
                Paragraph(
                    f"<b>{self._safe_text(title)}</b><br/>{text}",
                    self.styles["alert"],
                )
            ]],
            colWidths=[172 * mm],
        )
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), soft),
                    ("BOX", (0, 0), (-1, -1), 0.55, self.BORDER),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, tone),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return box

    def _validate_input(self, funds, rankings, analysis, period):
        if not isinstance(funds, list) or not funds:
            raise ValueError("funds must be a non-empty list.")

        if not isinstance(rankings, dict) or not rankings:
            raise ValueError("rankings must be a non-empty dictionary.")

        if not isinstance(analysis, dict):
            raise ValueError("analysis must be a dictionary.")

        if str(period).strip() not in {"1", "3", "5", "10"}:
            raise ValueError("period must be one of: 1, 3, 5, 10.")

        for fund in funds:
            required = {
                "scheme_name",
                "scheme_return",
                "up_capture",
                "down_capture",
                "capture_ratio",
            }
            missing = required - set(fund.keys())
            if missing:
                raise ValueError(
                    f"Fund '{fund.get('scheme_name', 'Unknown')}' "
                    f"is missing fields: {sorted(missing)}"
                )

    def _format_percent(self, value):
        if value is None:
            return "-"
        return f"{float(value):.2f}%"

    def _format_ratio(self, value):
        if value is None:
            return "-"
        return f"{float(value):.2f}"

    def _format_pp(self, value):
        if value is None:
            return "-"
        return f"{float(value):+.2f} pp"

    def _safe_text(self, value):
        if value is None:
            return ""
        return escape(str(value), quote=False)


def generate_report(
    funds,
    rankings,
    analysis,
    period,
    output_path="mutual_fund_analysis.pdf",
):
    generator = ReportGenerator(output_path)
    return generator.generate(
        funds=funds,
        rankings=rankings,
        analysis=analysis,
        period=period,
    )
