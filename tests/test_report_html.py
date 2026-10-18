from cost_explainer.compare import compare
from cost_explainer.report_html import money, render_html, signed

TABLE = {
    "labels": ["Oct 1-4 (4 days)", "Oct 5-11"],
    "rows": [{"service": "EC2", "weeks": [10.0, 40.0], "total": 50.0}],
    "week_totals": [10.0, 40.0],
    "total": 50.0,
    "month": "October 2026",
    "through": "2026-10-11",
}
RESULT = compare({"EC2": 10.0, "Tax": 5.0}, {"EC2": 40.0, "S3": 8.0})


def html(**kw):
    args = {
        "account": "123456789012",
        "month_table": TABLE,
        "result": RESULT,
        "week_label": "Oct 5-11",
        **kw,
    }
    return render_html(**args)


def test_money_and_signed():
    assert money(1234.5) == "$1,234.50"
    assert signed(3) == "+$3.00"
    assert signed(-3) == "-$3.00"


def test_header_has_account_and_month():
    out = html()
    assert "AWS account: 123456789012" in out
    assert "October 2026" in out
    assert "through 2026-10-11" in out


def test_month_table_shows_weeks_and_total():
    out = html()
    assert "Oct 1-4<br>" in out and "Month total" in out and "$50.00" in out


def test_movers_show_new_and_gone():
    out = html()
    assert "(new)" in out
    assert "(no longer billed)" in out


def test_explanation_included_and_escaped():
    out = html(explanation="Costs rose <b>a lot</b>.\n\nSecond paragraph.")
    assert "What this means" in out
    assert "&lt;b&gt;" in out
    assert out.count("<p>") >= 2


def test_no_explanation_section_without_text():
    assert "What this means" not in html()


def test_account_name_shown():
    assert "Prod (123456789012)" in html(account_name="Prod")


def test_empty_movers_message():
    empty = compare({"EC2": 10.0}, {"EC2": 10.0})
    assert "no service changed by both more than $1.00 and 20%" in html(result=empty)


def test_partial_week_header_puts_day_count_on_second_line():
    out = html()
    assert "white-space:nowrap" in out
    assert 'Oct 1-4<br><span style="font-size:11px;' in out
    assert ">(4 days)</span>" in out
    assert ">Oct 5-11</th>" in out  # full week stays on one line


def test_tax_only_change_shows_steady_message_not_table():
    tax_only = compare({"EC2": 10.0, "Tax": 1.0}, {"EC2": 10.0, "Tax": 41.0})
    out = html(result=tax_only)
    assert "Usage was steady" in out
    assert "Previous week" in out  # the summary table
    assert out.count("<table") == 2  # summary + month table, no movers table


def test_summary_comes_first_with_usage_and_total():
    out = html()
    assert "Usage (excluding tax)" in out and "Total (including tax)" in out
    assert out.index("Usage (excluding tax)") < out.index("Month to date")
    assert "+$38.00 (+380.0%)" in out  # usage $10 -> $48; Tax left out
