import unittest
from unittest.mock import Mock

from src.filing_analysis import (
    answer_question,
    build_summary,
    extract_growth_drivers,
    extract_metric_value,
    extract_metrics,
    extract_risk_factors,
    extract_sections,
    infer_company_name,
)


class FilingAnalysisTests(unittest.TestCase):
    def test_infers_company_from_uppercase_heading(self):
        markdown = "## MICROSOFT CORPORATION\n\nAnnual report."

        self.assertEqual(infer_company_name(markdown), "MICROSOFT CORPORATION")

    def test_uses_fallback_when_company_name_is_missing(self):
        self.assertEqual(infer_company_name("Annual report", "sample-filing"), "sample-filing")

    def test_extracts_company_year_and_financial_statement_metrics(self):
        markdown = """## MICROSOFT CORPORATION
For the Fiscal Year Ended June 30, 2026

| Metric | 2026 | 2025 |
| --- | ---: | ---: |
| Revenue | $331,839 | $281,724 |
| Operating income | 155,237 | 128,528 |
| Net income | 133,749 | 101,832 |
| Total assets | $758,376 | $619,003 |
| Total liabilities | 315,989 | 275,524 |
| Cash and cash equivalents | $20,935 | $30,242 |
"""

        metrics = extract_metrics(markdown)

        self.assertEqual(metrics["company_name"], "MICROSOFT CORPORATION")
        self.assertEqual(metrics["fiscal_year"], 2026)
        self.assertEqual(metrics["total_revenue"], 331839.0)
        self.assertEqual(metrics["operating_income"], 155237.0)
        self.assertEqual(metrics["net_income"], 133749.0)
        self.assertEqual(metrics["total_assets"], 758376.0)
        self.assertEqual(metrics["total_liabilities"], 315989.0)
        self.assertEqual(metrics["cash_and_equivalents"], 20935.0)

    def test_extracts_parenthetical_table_value_as_negative(self):
        markdown = "| Net income | (1,250) |"

        self.assertEqual(extract_metric_value(markdown, ("net income",)), -1250.0)

    def test_table_metric_is_not_confused_by_narrative_mention(self):
        markdown = """Revenue increased due to cloud growth.
| Revenue | $331,839 | $281,724 |
"""

        self.assertEqual(extract_metric_value(markdown, ("revenue",)), 331839.0)

    def test_extracts_markdown_sections_and_unheaded_text(self):
        markdown = "## Business\nThe company sells products.\n\n### Risks\nCompetition is a risk."

        self.assertEqual(
            extract_sections(markdown),
            [
                ("Business", "The company sells products."),
                ("Risks", "Competition is a risk."),
            ],
        )
        self.assertEqual(extract_sections("Plain filing text"), [("Filing", "Plain filing text")])

    def test_growth_and_risk_extraction_returns_matching_source_sentences(self):
        markdown = (
            "Revenue growth was driven by strong cloud demand and new subscriptions. "
            "The company faces regulatory uncertainty and intense competition."
        )

        self.assertEqual(
            extract_growth_drivers(markdown),
            ["Revenue growth was driven by strong cloud demand and new subscriptions."],
        )
        self.assertEqual(
            extract_risk_factors(markdown),
            ["The company faces regulatory uncertainty and intense competition."],
        )

    def test_summary_uses_preferred_section_and_company_name(self):
        body = "The company delivered results through continued revenue growth and product expansion. " * 2
        summary = build_summary(
            f"## Risk Factors\nUnrelated section.\n\n## Management Discussion\n{body}",
            "Example Corp",
        )

        self.assertTrue(summary.startswith("Example Corp filing overview:"))
        self.assertIn("continued revenue growth", summary)

    def test_question_fallback_returns_relevant_excerpt(self):
        markdown = (
            "## Business\nThe company sells cloud products to enterprise customers.\n\n"
            "## Risk Factors\nThe company faces regulatory uncertainty and competition."
        )

        answer = answer_question("What regulatory risks are discussed?", markdown)

        self.assertIn("relevant filing excerpts", answer)
        self.assertIn("Risk Factors", answer)
        self.assertIn("regulatory uncertainty", answer)

    def test_question_uses_configured_client_with_ranked_filing_context(self):
        markdown = (
            "## Business\nThe company sells cloud products to enterprise customers.\n\n"
            "## Risk Factors\nThe company faces regulatory uncertainty and competition."
        )
        client = Mock()
        client.chat.completions.create.return_value.choices = [
            Mock(message=Mock(content="The filing identifies regulatory uncertainty."))
        ]

        answer = answer_question("What regulatory risks are discussed?", markdown, client)

        self.assertEqual(answer, "The filing identifies regulatory uncertainty.")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-4o-mini")
        self.assertIn("Risk Factors", request["messages"][1]["content"])

    def test_empty_filing_returns_clear_answer(self):
        self.assertEqual(
            answer_question("What is the revenue?", " \n"),
            "No filing content was extracted from the uploaded file.",
        )


if __name__ == "__main__":
    unittest.main()
