# Browser regression tests

These tests require Playwright and its Chromium browser. Run them separately from
the normal unit suite:

```sh
python -m playwright install chromium
python -m pytest -q tests/browser
```

When Playwright is not installed, browser tests are skipped during collection so
the regular test suites remain usable.
