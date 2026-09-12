from pathlib import Path

import pytest


sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_provider_identifier_payload_is_stored_as_input_text_not_markup():
    jquery = (REPO_ROOT / "cps/static/js/libs/jquery.min.js").read_text(encoding="utf-8")
    get_meta = (REPO_ROOT / "cps/static/js/get_meta.js").read_text(encoding="utf-8")
    # Expose the production function without copying its implementation into the test.
    get_meta = get_meta.replace(
        "function addIdentifier(name, value) {",
        "window.testAddIdentifier = function (name, value) {",
        1,
    )
    malicious_name = '\"><img id="type-xss" src=x onerror="window.xssExecuted=true">'
    malicious_value = '\"><img id="value-xss" src=x onerror="window.xssExecuted=true">'

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            '<script type="text/template" id="template-book-result"></script>'
            '<table id="identifier-table"><tbody></tbody></table>'
        )
        page.add_script_tag(content=jquery)
        page.evaluate(
            """
            window.xssExecuted = false;
            window.i18nMsg = {};
            window._ = function (value) { return value; };
            window._.template = function () { return function () { return ''; }; };
            """
        )
        page.add_script_tag(content=get_meta)
        page.wait_for_function("typeof window.testAddIdentifier === 'function'")
        page.evaluate(
            "([name, value]) => window.testAddIdentifier(name, value)",
            [malicious_name, malicious_value],
        )

        assert page.locator("#identifier-table img").count() == 0
        assert page.locator("input.identifier-type").input_value() == malicious_name
        assert page.locator("input.identifier-val").input_value() == malicious_value
        assert page.evaluate("window.xssExecuted") is False
        browser.close()
