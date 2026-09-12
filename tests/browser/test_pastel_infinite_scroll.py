"""Exercise Pastel's bundled scrolling plugin against paginated responses."""
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fail_last", [False, True])
def test_pastel_appends_once_and_keeps_recovery_navigation(fail_last):
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
            route.fulfill(content_type='text/html', body=f'''<body class="pastel">
              <div class="col-sm-10" style="height:300px;width:220px;overflow:auto">
                <div class="caliblur-index load-more"><div class="row">{cards}</div></div>
                <div class="pagination">{next_link}</div>
              </div>
              <style>.pastel-infinite-active {{display:none}}</style>
              <script src="/static/js/libs/jquery.min.js"></script>
              <script src="/static/js/libs/plugins.js"></script>
              <script>$('.load-more > .row').isotope({{itemSelector:'.book',layoutMode:'fitRows'}});</script>
              <script src="/static/js/pastel.js"></script>
            </body>''')

        page.route('http://pastel.test/**', respond)
        page.goto('http://pastel.test/')
        assert not page.locator('.pagination').is_visible()
        pane = page.locator('.col-sm-10')
        pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
        page.wait_for_function("document.querySelectorAll('.book').length === 8")
        page.wait_for_timeout(500)
        pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
        if fail_last:
            page.wait_for_function("!document.querySelector('.pagination').classList.contains('pastel-infinite-active')")
            assert page.locator('.pagination .next').get_attribute('href') == '/?page=3'
            assert page.locator('.book').count() == 8
        else:
            page.wait_for_function("document.querySelectorAll('.book').length === 12")
            pane.evaluate('(e) => e.scrollTop = e.scrollHeight')
            page.wait_for_timeout(600)
            assert not page.locator('.pagination').is_visible()
            assert page.locator('.next').count() == 0
        ids = page.locator('.book').evaluate_all('(es) => es.map(e => e.dataset.id)')
        assert len(ids) == len(set(ids))
        assert requests == [1, 2, 3]
        assert page.url == 'http://pastel.test/'
        browser.close()
