"""Render the report as an HTML email (inline styles, because email clients ignore <style>)."""

from __future__ import annotations

from html import escape
from typing import Any

TH = "padding:6px 10px;text-align:right;border-bottom:2px solid #ccc;background:#f4f4f4;"
TD = "padding:6px 10px;text-align:right;border-bottom:1px solid #e5e5e5;"


def money(value: float) -> str:
    return f"${value:,.2f}"


def signed(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def _row(cells: list[str], bold: bool = False) -> str:
    weight = "font-weight:bold;" if bold else ""
    tds = [f'<td style="{TD}text-align:left;{weight}">{escape(cells[0])}</td>']
    tds += [f'<td style="{TD}{weight}">{escape(c)}</td>' for c in cells[1:]]
    return "<tr>" + "".join(tds) + "</tr>"


def _table(headers: list[str], rows: list[str]) -> str:
    head = f'<th style="{TH}text-align:left;">{escape(headers[0])}</th>'
    head += "".join(f'<th style="{TH}">{escape(h)}</th>' for h in headers[1:])
    return (
        '<table style="border-collapse:collapse;width:100%;font-size:14px;">'
        f"<tr>{head}</tr>{''.join(rows)}</table>"
    )


def month_table_html(table: dict[str, Any]) -> str:
    headers = ["Service", *table["labels"], "Month total"]
    rows = [
        _row([r["service"], *[money(w) for w in r["weeks"]], money(r["total"])])
        for r in table["rows"]
    ]
    rows.append(
        _row(["Total", *[money(w) for w in table["week_totals"]], money(table["total"])], bold=True)
    )
    return _table(headers, rows)


def movers_html(result: dict[str, Any]) -> str:
    rows = []
    for c in result["top_movers"]:
        if c.is_new:
            note = " (new)"
        elif c.is_gone:
            note = " (no longer billed)"
        else:
            note = f" ({c.pct:+.0f}%)" if c.pct is not None else ""
        rows.append(_row([c.service, money(c.previous), money(c.current), signed(c.delta) + note]))
    if not rows:
        return "<p>No significant changes this week.</p>"
    return _table(["Service", "Previous week", "This week", "Change"], rows)


def _paragraphs(text: str) -> str:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{escape(p)}</p>" for p in parts)


def _heading(text: str) -> str:
    return f'<h3 style="margin:24px 0 8px;">{escape(text)}</h3>'


def render_html(
    *,
    account: str,
    month_table: dict[str, Any],
    result: dict[str, Any],
    week_label: str,
    explanation: str | None = None,
    account_name: str | None = None,
) -> str:
    who = f"{account_name} ({account})" if account_name else account
    parts = [
        '<div style="font-family:Arial,sans-serif;max-width:720px;color:#222;">',
        f'<h2 style="margin:0 0 4px;">AWS Cost Report: {escape(month_table["month"])}</h2>',
        f'<div style="color:#555;">AWS account: {escape(who)}</div>',
        _heading(f"Month to date, through {month_table['through']}"),
        month_table_html(month_table),
        _heading(f"What changed this week ({week_label})"),
        movers_html(result),
    ]
    if explanation:
        parts += [_heading("What this means"), _paragraphs(explanation)]
    parts.append("</div>")
    return "".join(parts)
