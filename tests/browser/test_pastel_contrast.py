"""Pastel must override inherited dark-theme list and settings colors."""
from pathlib import Path
import re
import pytest

sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
ROOT = Path(__file__).resolve().parents[2]


def contrast(fg, bg):
    def luminance(color):
        values = [float(v) / 255 for v in re.findall(r'[\d.]+', color)[:3]]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))
    a, b = sorted((luminance(fg), luminance(bg)))
    return (b + .05) / (a + .05)


@pytest.mark.parametrize('engine', ['webkit', 'chromium'])
@pytest.mark.parametrize('width', [390, 1440])
def test_pastel_lists_and_settings_contrast(engine, width):
    with sync_playwright() as p:
        browser = getattr(p, engine).launch()
        page = browser.new_page(viewport={'width': width, 'height': 900})
        page.set_content('''<meta name="viewport" content="width=device-width,initial-scale=1">
        <body class="pastel blur catlist"><div class="container-fluid"><div class="row-fluid"><div class="col-sm-10">
        <div class="alert alert-info"><button class="close"><span>×</span></button></div><span class="pastel-brand-name">Calibre-Web</span><div class="container"><div class="col-xs-12"><div class="row" id="Categories_row">
        <div class="col-xs-2"><span class="badge">12</span></div>
        <div class="col-xs-10"><a id="list_0" href="#category">Fiction</a></div></div></div></div>
        <div class="settings-container"><div style="background: #202c34a3"><label>Sync shelves</label></div>
        <div class="settings-disclaimer">Profile notice</div></div>
        <form id="magic-shelf-form"><div class="form-group" style="background: #21252b"><label>Sync to Kobo</label></div>
        <small class="form-text text-muted">Help text</small><div class="icon-option">★</div></form>
        </div></div></div></body>''')
        # Measure settled colors, not transitions triggered by injecting CSS files.
        page.add_style_tag(content='*, *::before, *::after { transition: none !important; animation: none !important; }')
        for name in ('libs/bootstrap.min.css', 'style.css', 'caliBlur.css', 'caliBlur_override.css', 'pastel.css', 'cwa.css'):
            page.add_style_tag(path=str(ROOT / 'cps/static/css' / name))
        template = (ROOT / 'cps/templates/magic_shelf_edit.html').read_text()
        page.add_style_tag(content=re.search(r'<style>(.*?)</style>', template, re.S).group(1))
        for selector in ('#list_0', '.settings-disclaimer', '.form-text', '.pastel-brand-name', '.close span'):
            color = page.locator(selector).evaluate('(e)=>getComputedStyle(e).color')
            assert contrast(color, 'rgb(250,244,237)') >= 4.5
        for selector in ('.badge', '.icon-option'):
            colors = page.locator(selector).evaluate('(e)=>{let s=getComputedStyle(e);return [s.color,s.backgroundColor]}')
            assert contrast(*colors) >= 4.5
        for selector in ('.settings-container label', '#magic-shelf-form label'):
            colors = page.locator(selector).evaluate('(e)=>[getComputedStyle(e).color,getComputedStyle(e.parentElement).backgroundColor]')
            assert contrast(*colors) >= 4.5
        assert page.locator('.close').evaluate('(e)=>getComputedStyle(e).opacity') == '1'
        arrow = page.locator('#Categories_row > .col-xs-10').evaluate('(e)=>getComputedStyle(e,"::after").color')
        assert contrast(arrow, 'rgb(250,244,237)') >= 3
        browser.close()
