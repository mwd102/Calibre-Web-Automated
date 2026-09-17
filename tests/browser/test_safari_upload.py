"""Safari keeps a normal form submission and prevents accidental repeats."""

from pathlib import Path

import pytest


sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
ROOT = Path(__file__).resolve().parents[2]


def test_safari_upload_shows_pending_state_and_blocks_repeat():
    with sync_playwright() as playwright:
        browser = playwright.webkit.launch()
        page = browser.new_page()
        page.set_content(
            '<form id="form-upload" method="post" action="/upload">'
            '<span class="btn-file">Upload</span></form>'
        )
        page.add_script_tag(path=ROOT / "cps/static/js/libs/jquery.min.js")
        page.add_script_tag(path=ROOT / "cps/static/js/uploadprogress.js")

        result = page.evaluate("""() => {
            const form = window.jQuery('#form-upload');
            form.uploadprogress({modalTitle: 'Uploading...'});
            const first = window.jQuery.Event('submit');
            form.triggerHandler(first);
            const second = window.jQuery.Event('submit');
            form.triggerHandler(second);
            const result = {
                firstPrevented: first.isDefaultPrevented(),
                secondPrevented: second.isDefaultPrevented(),
                pending: form.data('uploadPending'),
                status: form.find('[role="status"]').text(),
                statusCount: form.find('[role="status"]').length
            };
            const restored = window.jQuery.Event('pageshow');
            restored.originalEvent = {persisted: true};
            window.jQuery(window).triggerHandler(restored);
            result.restoredPending = Boolean(form.data('uploadPending'));
            result.restoredStatusCount = form.find('[role="status"]').length;
            return result;
        }""")
        browser.close()

    assert result == {
        "firstPrevented": False,
        "secondPrevented": True,
        "pending": True,
        "status": "Uploading...",
        "statusCount": 1,
        "restoredPending": False,
        "restoredStatusCount": 0,
    }
