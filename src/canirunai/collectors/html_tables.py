from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass(slots=True)
class HtmlCell:
    text: str
    is_header: bool
    rowspan: int = 1
    colspan: int = 1


@dataclass(slots=True)
class ParsedTable:
    class_name: str
    caption: str
    headers: list[str]
    rows: list[dict[str, str]]


@dataclass(slots=True)
class _PendingSpan:
    text: str
    is_header: bool
    remaining_rows: int


@dataclass(slots=True)
class _RawTable:
    class_name: str
    caption_parts: list[str] = field(default_factory=list)
    rows: list[list[HtmlCell]] = field(default_factory=list)


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._tables: list[ParsedTable] = []
        self._table_depth = 0
        self._current_table: _RawTable | None = None
        self._current_row: list[HtmlCell] | None = None
        self._in_caption = False
        self._current_cell: tuple[bool, int, int] | None = None
        self._text_parts: list[str] = []
        self._ignored_tag_depth = 0

    @property
    def tables(self) -> list[ParsedTable]:
        return self._tables

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = _RawTable(class_name=attrs_dict.get("class") or "")
            return
        if self._table_depth != 1 or self._current_table is None:
            return
        if tag in {"style", "script"}:
            self._ignored_tag_depth += 1
            return
        if tag == "caption":
            self._in_caption = True
            self._text_parts = []
            return
        if tag == "tr":
            self._current_row = []
            return
        if tag in {"th", "td"} and self._current_row is not None:
            self._current_cell = (
                tag == "th",
                _parse_span(attrs_dict.get("rowspan")),
                _parse_span(attrs_dict.get("colspan")),
            )
            self._text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._table_depth == 1 and self._current_table is not None:
                self._tables.append(_finalize_table(self._current_table))
                self._current_table = None
            self._table_depth = max(0, self._table_depth - 1)
            return
        if self._table_depth != 1 or self._current_table is None:
            return
        if tag in {"style", "script"} and self._ignored_tag_depth > 0:
            self._ignored_tag_depth -= 1
            return
        if tag == "caption" and self._in_caption:
            text = _clean_text(" ".join(self._text_parts))
            if text:
                self._current_table.caption_parts.append(text)
            self._in_caption = False
            return
        if tag in {"th", "td"} and self._current_cell is not None and self._current_row is not None:
            is_header, rowspan, colspan = self._current_cell
            self._current_row.append(
                HtmlCell(
                    text=_clean_text(" ".join(self._text_parts)),
                    is_header=is_header,
                    rowspan=rowspan,
                    colspan=colspan,
                )
            )
            self._current_cell = None
            return
        if tag == "tr" and self._current_row is not None:
            if any(cell.text for cell in self._current_row):
                self._current_table.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._table_depth < 1:
            return
        if self._ignored_tag_depth > 0:
            return
        if self._in_caption or self._current_cell is not None:
            self._text_parts.append(data)


def parse_html_tables(document: str) -> list[ParsedTable]:
    parser = _HtmlTableParser()
    parser.feed(document)
    return parser.tables


def _finalize_table(raw_table: _RawTable) -> ParsedTable:
    normalized_rows = _normalize_rows(raw_table.rows)
    if not normalized_rows:
        return ParsedTable(class_name=raw_table.class_name, caption=" ".join(raw_table.caption_parts), headers=[], rows=[])

    header_rows: list[list[HtmlCell]] = []
    data_rows: list[list[HtmlCell]] = []
    encountered_data = False
    for row in normalized_rows:
        meaningful_cells = [cell for cell in row if cell.text]
        is_header_row = bool(meaningful_cells) and all(cell.is_header for cell in meaningful_cells)
        if not encountered_data and is_header_row:
            header_rows.append(row)
        else:
            encountered_data = True
            data_rows.append(row)

    if not header_rows:
        header_rows = [normalized_rows[0]]
        data_rows = normalized_rows[1:]

    width = max((len(row) for row in normalized_rows), default=0)
    headers = _merge_headers(header_rows, width)
    rows = _build_row_dicts(data_rows, headers)
    return ParsedTable(
        class_name=raw_table.class_name,
        caption=" ".join(part for part in raw_table.caption_parts if part),
        headers=headers,
        rows=rows,
    )


def _normalize_rows(raw_rows: list[list[HtmlCell]]) -> list[list[HtmlCell]]:
    normalized: list[list[HtmlCell]] = []
    spans: dict[int, _PendingSpan] = {}

    for raw_row in raw_rows:
        row: list[HtmlCell] = []
        column_index = 0

        def flush_spans() -> None:
            nonlocal column_index
            while column_index in spans:
                span = spans[column_index]
                row.append(HtmlCell(text=span.text, is_header=span.is_header))
                span.remaining_rows -= 1
                if span.remaining_rows <= 0:
                    del spans[column_index]
                column_index += 1

        flush_spans()
        for cell in raw_row:
            flush_spans()
            for _ in range(max(cell.colspan, 1)):
                row.append(HtmlCell(text=cell.text, is_header=cell.is_header))
                if cell.rowspan > 1:
                    spans[column_index] = _PendingSpan(
                        text=cell.text,
                        is_header=cell.is_header,
                        remaining_rows=cell.rowspan - 1,
                    )
                column_index += 1
        flush_spans()
        normalized.append(row)

    return normalized


def _merge_headers(header_rows: list[list[HtmlCell]], width: int) -> list[str]:
    headers: list[str] = []
    for column_index in range(width):
        parts: list[str] = []
        for row in header_rows:
            if column_index >= len(row):
                continue
            text = _clean_header_text(row[column_index].text)
            if text and (not parts or parts[-1] != text):
                parts.append(text)
        headers.append(" / ".join(parts) if parts else f"column_{column_index + 1}")
    return headers


def _build_row_dicts(data_rows: list[list[HtmlCell]], headers: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in data_rows:
        entry: dict[str, str] = {}
        for column_index, header in enumerate(headers):
            if column_index >= len(row):
                continue
            value = _clean_text(row[column_index].text)
            if value:
                entry[header] = value
        if entry:
            rows.append(entry)
    return rows


def _parse_span(value: str | None) -> int:
    if not value:
        return 1
    match = re.search(r"\d+", value)
    if match is None:
        return 1
    return max(int(match.group()), 1)


def _clean_text(value: str) -> str:
    cleaned = html.unescape(value)
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _clean_header_text(value: str) -> str:
    cleaned = _clean_text(value)
    cleaned = re.sub(r"\[\s*[^\]]+\s*\]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" /")
