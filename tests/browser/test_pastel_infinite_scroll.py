"""Exercise Pastel's bundled scrolling plugin against paginated responses."""
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("curated", [False, True])
@pytest.mark.parametrize("fail_last", [False, True])
def test_pastel_appends_once_and_keeps_recovery_navigation(fail_last, curated):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        requests = []

        def respond(route):
            from urllib.parse import urlparse, parse_qs
            url = urlparse(route.request.url)
            if url.path.startswith('/static/'):
                asset = ROOT / 'cps' / url.path.lstrip('/')
                route.fulfill(path=str(asset))
                return
            number = int(parse_qs(url.query).get('page', ['1'])[0])
            requests.append(number)
            if number == 3 and fail_last:
                route.fulfill(status=503, body='Unavailable')
                return
            cards = ''.join(f'<div class="book" data-id="{number}-{i}" style="height:250px;width:200px">Book</div>' for i in range(4))
            next_link = f'<a class="next" href="/?page={number + 1}">Next</a>' if number < 3 else ''
            html = f'''<body class="pastel">
              <div class="col-sm-10" style="height:300px;width:220px;overflow:auto">
                <div class="caliblur-index load-more"><div class="row">{cards}</div></div>
                <div class="pagination">{next_link}</div>
              </div>
              <style>.pastel-infinite-active {{display:none}}</style>
              <script src="/static/js/libs/jquery.min.js"></script>
              <script src="/static/js/libs/plugins.js"></script>
              <script>$('.load-more > .row').isotope({{itemSelector:'.book',layoutMode:'fitRows'}});</script>
              <script src="/static/js/pastel.js"></script>
            </body>'''
            if curated:
                html = html.replace('class="book"', 'class="curated-card"').replace('class="row"', 'class="curated-grid"').replace('class="pagination"', 'class="curated-pagination"')
            route.fulfill(content_type='text/html', body=html)

        page.route('http://pastel.test/**', respond)
        card_selector = '.curated-card' if curated else '.book'
        pagination_selector = '.curated-pagination' if curated else '.pagination'
        page.goto('http://pastel.test/')
        assert not page.locator(pagination_selector).is_visible()
        pane = page.locator('.col-sm-10')
        pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
        page.wait_for_function("s => document.querySelectorAll(s).length === 8", arg=card_selector)
        page.wait_for_timeout(500)
        pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
        if fail_last:
            page.wait_for_function("s => !document.querySelector(s).classList.contains('pastel-infinite-active')", arg=pagination_selector)
            assert page.locator(pagination_selector + ' .next').get_attribute('href') == '/?page=3'
            assert page.locator(card_selector).count() == 8
        else:
            page.wait_for_function("s => document.querySelectorAll(s).length === 12", arg=card_selector)
            pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
            page.wait_for_timeout(600)
            assert not page.locator(pagination_selector).is_visible()
            assert page.locator('.next').count() == 0
        ids = page.locator(card_selector).evaluate_all('(es) => es.map(e => e.dataset.id)')
        assert len(ids) == len(set(ids))
        assert requests == [1, 2, 3]
        assert page.url == 'http://pastel.test/'
        browser.close()
