#!/usr/bin/env python3
"""Structural checks for the KSA Tax Invoice print format.

These catch the footer bugs that produced a huge white gap and a
microscopic letterhead strip at the bottom of the PDF:

1. id="footer-html" is extracted by frappe/utils/pdf.py and passed to
   wkhtmltopdf as --footer-html, which pins the letterhead into the
   page-bottom margin instead of placing it under the bank details.
2. Any html/body { margin/padding !important } rule is copied into that
   extracted footer document and crushes the letterhead into ~7.5mm.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

FORMAT_PATH = Path(__file__).with_name("ksa_tax_invoice.html")


class KsaTaxInvoiceFooterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = FORMAT_PATH.read_text(encoding="utf-8")

    def test_print_format_file_exists(self) -> None:
        self.assertTrue(FORMAT_PATH.is_file(), f"missing {FORMAT_PATH}")

    def test_header_still_uses_header_html_for_repeating_letterhead(self) -> None:
        self.assertIn('id="header-html"', self.html)

    def test_footer_is_not_extracted_as_footer_html(self) -> None:
        self.assertIsNone(
            re.search(r"<(div|table|section)\b[^>]*\bid=['\"]footer-html['\"]", self.html),
            "id=footer-html on a real element is extracted by pdf.py and pins the footer",
        )

    def test_letterhead_footer_sits_after_bank_details(self) -> None:
        bank_at = self.html.find('class="bank-details"')
        footer_match = re.search(r"<div\b[^>]*class=['\"][^'\"]*letter-head-footer", self.html)
        self.assertNotEqual(bank_at, -1, "bank details table missing")
        self.assertIsNotNone(footer_match, "letter-head-footer element missing")
        self.assertLess(
            bank_at,
            footer_match.start(),
            "letterhead footer must come after the bank details, not above them",
        )

    def test_letterhead_footer_renders_the_frappe_footer_variable(self) -> None:
        # Must still print the Letter Head footer HTML from Frappe.
        footer_block = self.html[self.html.find("letter-head-footer") :]
        self.assertIn("{{ footer }}", footer_block)

    def test_no_html_body_important_box_model_that_leaks_into_header_footer(self) -> None:
        """Frappe copies every <style> tag into pdf_header_footer.html.

        A `html, body { margin/padding: … !important }` rule then overrides
        Frappe's footer body padding and squashes the letterhead.
        """
        leaked = re.search(
            r"(html|body)\s*,[^{]*\{[^}]*\b(margin|padding)\s*:[^}]*!important",
            self.html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNone(
            leaked,
            f"html/body !important box-model rule would leak into header/footer HTML: {leaked.group(0) if leaked else ''}",
        )

    def test_style_blocks_do_not_contain_html_comments(self) -> None:
        html = re.sub(r"<!--.*?-->", "", self.html, flags=re.DOTALL)
        for style in re.findall(r"<style\b[^>]*>(.*?)</style>", html, flags=re.DOTALL | re.IGNORECASE):
            self.assertNotIn("<!--", style)
            self.assertNotIn("-->", style)

    def test_print_format_bottom_margin_is_not_a_footer_slot(self) -> None:
        """margin-bottom is scraped into wkhtmltopdf --margin-bottom.

        A large value is only needed when #footer-html occupies that slot.
        With an in-flow footer it should stay a small page inset.
        """
        match = re.search(
            r"\.print-format\s*\{[^}]*margin-bottom:\s*([0-9.]+)mm",
            self.html,
        )
        self.assertIsNotNone(match, ".print-format { margin-bottom: Nmm } is required for pdf.py")
        value = float(match.group(1))
        self.assertLessEqual(value, 6.0, "bottom margin is reserving a footer strip again")


if __name__ == "__main__":
    unittest.main()
