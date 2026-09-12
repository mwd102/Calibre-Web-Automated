"""Regression checks for caliBlur rules that used to leak into Pastel."""
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pastel_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.set_content('''<body class="book blur pastel allow-mobile-blur">
          <div class="navbar navbar-default navbar-static-top"><div class="container-fluid">
            <div class="navbar-header"><button class="navbar-toggle">
              <span class="sr-only">Menu</span><span class="icon-bar"></span>
              <span class="icon-bar"></span><span class="icon-bar"></span>
            </button></div>
          </div></div>
          <div class="blur-wrapper"><img alt="" src=""></div>
          <div id="bookDetailsModal" class="modal in" style="display:block">
            <div class="modal-dialog modal-lg"><div class="modal-content">
              <div class="modal-header"><button class="close">×</button><h4>Book details</h4></div>
              <div class="modal-body"><div class="container-fluid"><div class="discover">
                <div class="single book-detail-page"><div class="row book-detail-main">
                  <div class="book-detail-cover cover">Cover</div>
                  <div class="book-meta book-detail-meta">
                    <div class="book-action-bar"><div class="action-group">
                      <button class="action-icon-btn">Read</button><button class="action-icon-btn">Edit</button>
                    </div></div>
                    <h2 id="title">A long book title in a narrow window</h2>
                    <section class="book-detail-description">Description</section>
                    <div class="book-metadata"></div>
                  </div>
                </div></div>
              </div></div></div>
              <div class="modal-footer">Close</div>
            </div></div>
          </div>
        </body>''')
        for name in ("libs/bootstrap.min.css", "style.css", "upload.css", "caliBlur.css", "caliBlur_override.css", "pastel.css", "cwa.css"):
            page.add_style_tag(path=str(ROOT / "cps/static/css" / name))
        yield page
        browser.close()


def test_mobile_blur_setting_does_not_override_pastel(pastel_page):
    assert not pastel_page.locator('.blur-wrapper').is_visible()


def test_mobile_menu_bars_are_visible_and_separate(pastel_page):
    bars = pastel_page.locator('.icon-bar')
    positions = []
    for bar in bars.all():
        assert bar.evaluate('(e) => getComputedStyle(e).opacity') == '1'
        positions.append(bar.bounding_box()['y'])
    assert positions[0] < positions[1] < positions[2]


@pytest.mark.parametrize('width', [320, 390, 768, 1440])
def test_book_popup_has_one_scroll_area_and_reachable_controls(pastel_page, width):
    page = pastel_page
    page.set_viewport_size({'width': width, 'height': 844})
    page.locator('.book-metadata').evaluate('''e => {
        for(let i=0;i<60;i++) {
            const row=document.createElement('div'); row.className='meta-chip';
            row.textContent='Metadata '+i; e.append(row);
        }
    }''')
    content = page.locator('#bookDetailsModal .modal-content').bounding_box()
    assert content['x'] >= 0 and content['x'] + content['width'] <= width
    assert content['y'] >= 0 and content['y'] + content['height'] <= 844
    assert page.locator('.modal-header .close').is_visible()
    assert page.locator('.book-detail-meta').evaluate('(e) => getComputedStyle(e).overflowY') == 'visible'
    assert page.locator('.book-action-bar').evaluate('(e) => getComputedStyle(e).display') == 'flex'
    page.locator('.modal-body').evaluate('(e) => { e.scrollTop=e.scrollHeight; }')
    last = page.locator('.meta-chip').last.bounding_box()
    body = page.locator('.modal-body').bounding_box()
    assert body['y'] <= last['y'] and last['y'] + last['height'] <= body['y'] + body['height'] + 1
