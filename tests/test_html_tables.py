from __future__ import annotations

import unittest

from canirunai.collectors.html_tables import parse_html_tables


class HtmlTableParserTest(unittest.TestCase):
    def test_merges_multi_row_headers_and_keeps_row_header_cells(self) -> None:
        html = """
        <table class="wikitable">
          <tr>
            <th rowspan="2">Processor family</th>
            <th rowspan="2">Model</th>
            <th colspan="2">Clock rate (GHz)</th>
          </tr>
          <tr>
            <th>Base</th>
            <th>Turbo</th>
          </tr>
          <tr>
            <th>Core i7</th>
            <td>14700K</td>
            <td>3.4</td>
            <td>5.6</td>
          </tr>
        </table>
        """

        tables = parse_html_tables(html)

        self.assertEqual(len(tables), 1)
        self.assertEqual(
            tables[0].headers,
            [
                "Processor family",
                "Model",
                "Clock rate (GHz) / Base",
                "Clock rate (GHz) / Turbo",
            ],
        )
        self.assertEqual(tables[0].rows[0]["Processor family"], "Core i7")
        self.assertEqual(tables[0].rows[0]["Model"], "14700K")

    def test_ignores_style_and_script_text_inside_tables(self) -> None:
        html = """
        <table class="wikitable">
          <tr>
            <th>Model<style>.mw-parser-output .tooltip{display:none}</style></th>
            <th>Launch<script>console.log("ignored")</script></th>
          </tr>
          <tr>
            <td><style>.mw-parser-output .plainlist{margin:0}</style>Radeon 890M</td>
            <td><script>ignored()</script>2024</td>
          </tr>
        </table>
        """

        tables = parse_html_tables(html)

        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].headers, ["Model", "Launch"])
        self.assertEqual(tables[0].rows[0]["Model"], "Radeon 890M")
        self.assertEqual(tables[0].rows[0]["Launch"], "2024")
