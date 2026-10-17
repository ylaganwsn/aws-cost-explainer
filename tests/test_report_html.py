from cost_explainer.compare import compare
from cost_explainer.report_html import money, render_html, signed

TABLE = {
    "labels": ["Oct 1-4", "Oct 5-11"],
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
    assert "Oct 1-4" in out and "Month total" in out and "$50.00" in out


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
    assert "No significant changes" in html(result=empty)