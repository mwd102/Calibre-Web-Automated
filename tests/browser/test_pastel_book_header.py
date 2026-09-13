"""Real mobile browser engines must keep covers, headings and controls apart."""
from pathlib import Path
import re
import pytest

sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('engine', ['chromium', 'webkit'])
@pytest.mark.parametrize('width', [320, 390, 440])
@pytest.mark.parametrize('popup', [False, True])
@pytest.mark.parametrize('title_text', ['Protect and Defend', 'A remarkably long book title with a second subtitle'])
def test_iphone_book_header_does_not_overlap(engine, width, popup, title_text):
    with sync_playwright() as p:
        browser = getattr(p, engine).launch()
        context = browser.new_context(**{**p.devices['iPhone 13'], 'viewport': {'width': width, 'height': 844}})
        page = context.new_page()
        detail = '''<div class="single book-detail-page">
          <nav class="pastel-book-navigation"><a class="btn btn-default">Back to library</a></nav>
          <div class="row book-detail-main">
            <div class="col-sm-3 col-lg-3 col-xs-5 book-detail-cover cover">
              <img id="detailcover" width="300" height="480" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='480'%3E%3Crect width='300' height='480' fill='tan'/%3E%3C/svg%3E">
            </div>
            <div class="col-sm-9 col-lg-9 book-meta book-detail-meta">
              <div class="book-detail-heading"><h2 id="title">TITLE_TEXT</h2>
              <p class="author">An author with a long name</p>
              <p class="book-publication-date">Published 20 September 2025</p>
              <div id="detail-rating-block">★★★★★</div></div>
              <div class="book-detail-actions"><div class="book-action-bar"><div class="action-group">
                <button id="sendToEReaderBtn" class="btn action-icon-btn">Email</button><button class="btn action-icon-btn">Kobo</button>
                <button class="btn action-icon-btn">Read</button><div class="btn-group"><button class="btn action-icon-btn">Shelf</button></div>
              </div></div></div>
<p id="book_of">Book 8 of <a>Mitch Rapp</a></p>
              <section class="book-detail-description">A description that stays below the controls.</section>
            </div>
          </div></div>'''
        detail = detail.replace('TITLE_TEXT', title_text)
        if popup:
            detail = '<div id="bookDetailsModal" class="modal in" style="display:block"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-body">' + detail + '</div></div></div></div>'
        page.set_content('<meta name="viewport" content="width=device-width,initial-scale=1"><body class="book blur pastel allow-mobile-blur"><div class="container-fluid"><div class="row-fluid"><div class="col-sm-10">'+detail+'</div></div></div></body>')
        for name in ('libs/bootstrap.min.css', 'style.css', 'upload.css', 'caliBlur.css', 'caliBlur_override.css', 'pastel.css', 'cwa.css'):
            page.add_style_tag(path=str(ROOT / 'cps/static/css' / name))
        # Full pages also load Standard's inline detail styles after the stylesheets.
        if not popup:
            template = (ROOT / 'cps/themes/standard/templates/detail.html').read_text()
            page.add_style_tag(content=re.search(r'<style>(.*?)</style>', template, re.S).group(1))
        cover = page.locator('#detailcover').bounding_box()
        title = page.locator('#title').bounding_box()
        nav = page.locator('.pastel-book-navigation').bounding_box()
        actions = page.locator('.book-detail-actions').bounding_box()
        author = page.locator('.author').bounding_box()
        assert title['y'] + title['height'] + 7 <= author['y']
        for button in page.locator('.action-icon-btn').all():
            box = button.bounding_box()
            assert box['y'] >= cover['y'] + cover['height'] + 19
            assert box['height'] == 40
        group = page.locator('.book-action-bar .btn-group').bounding_box()
        assert group['height'] >= 40
        assert page.locator('#book_of').evaluate('(e)=>getComputedStyle(e).color') == 'rgb(102, 97, 115)'
        assert nav['y'] + nav['height'] <= cover['y']
        assert cover['x'] + cover['width'] <= title['x']
        assert cover['y'] + cover['height'] <= actions['y'] + 1
        assert title['y'] + title['height'] <= actions['y'] + 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        browser.close()
