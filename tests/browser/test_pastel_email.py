"""Recipient selection sends only explicit choices, including from a book popup."""
from pathlib import Path
from urllib.parse import parse_qs

import pytest

sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('width', [390, 1440])
def test_select_one_recipient_without_sending_to_every_saved_address(nested, width):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 844})
        sent = []

        def send(route):
            sent.append(parse_qs(route.request.post_data))
            route.fulfill(content_type='application/json', body='[{"type":"success","message":"Queued"}]')

        page.route('http://pastel.test/send_selected/42', send)
        page.route('http://pastel.test/', lambda r: r.fulfill(body='<body class="pastel"><div class="navbar"></div></body>'))
        page.goto('http://pastel.test/')
        dialog = '''<div class="modal fade" id="emailSelectModal" data-book-id="42">
          <div class="modal-dialog"><div class="modal-content"><div class="modal-card">
            <div class="modal-header"><button class="close" data-dismiss="modal">×</button><h4>Email</h4></div>
            <div class="modal-body"><form id="emailSelectForm">
              <input name="csrf_token" value="test-token" type="hidden">
              <input id="selectAllEmails" type="checkbox"> All
              <label><input type="checkbox" name="selected_emails" value="one@example.test">One</label>
              <label><input type="checkbox" name="selected_emails" value="two@example.test">Two</label>
              <select name="format_selection"><option value="Epub" data-convert="0">EPUB</option></select>
            </form></div>
            <div class="modal-footer"><button id="sendSelectedBtn">Send</button></div>
          </div></div></div></div>'''
        trigger = '<button id="sendToEReaderBtn" data-toggle="modal" data-target="#emailSelectModal" data-book-id="42">Email</button>'
        content = trigger + dialog
        if nested:
            content = '<div id="bookDetailsModal" class="modal in" style="display:block"><div class="modal-dialog"><div class="modal-content">' + content + '</div></div></div>'
        page.locator('body').evaluate('(e, html) => e.insertAdjacentHTML("beforeend", html)', content)
        for name in ['libs/bootstrap.min.css', 'pastel.css']:
            page.add_style_tag(path=str(ROOT / 'cps/static/css' / name))
        for name in ['libs/jquery.min.js', 'libs/bootstrap.min.js']:
            page.add_script_tag(path=str(ROOT / 'cps/static/js' / name))
        page.add_script_tag(content='window.getPath = function(){return "";};')
        page.add_script_tag(path=str(ROOT / 'cps/static/js/email_selection.js'))
        page.locator('#sendToEReaderBtn').click()
        page.locator('#emailSelectModal').wait_for(state='visible')
        assert len(sent) == 0
        if nested:
            assert page.locator('body > #emailSelectModal').count() == 1
        page.locator('#sendSelectedBtn').click()
        assert len(sent) == 0
        page.locator('#modal-validation-message').wait_for(state='visible')
        page.locator('[value="two@example.test"]').check()
        page.locator('#sendSelectedBtn').click()
        page.wait_for_function('!document.querySelector("#emailSelectModal").classList.contains("in")')
        assert len(sent) == 1
        assert sent[0]['selected_emails'] == ['two@example.test']
        assert sent[0]['book_format'] == ['Epub']
        assert sent[0]['csrf_token'] == ['test-token']
        browser.close()
