"""Exercise the deployment guard before any startup/scheduled writer runs."""
import ast
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('value', ['true', 'TRUE', '1', 'yes', 'on'])
@pytest.mark.parametrize('entrypoint', ['register_startup_tasks', 'register_scheduled_tasks'])
def test_external_automation_does_not_start_scheduler(monkeypatch, value, entrypoint):
    monkeypatch.setenv('CWA_DISABLE_AUTOMATION', value)
    tree = ast.parse((ROOT / 'cps/schedule.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == entrypoint)
    scheduler = Mock(side_effect=AssertionError('background scheduler must not start'))
    scope = {'os': os, 'BackgroundScheduler': scheduler}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<schedule>', 'exec'), scope)
    scope[entrypoint]()
    scheduler.assert_not_called()


def test_default_still_registers_scheduler(monkeypatch):
    monkeypatch.delenv('CWA_DISABLE_AUTOMATION', raising=False)
    tree = ast.parse((ROOT / 'cps/schedule.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'register_startup_tasks')
    scheduler = Mock(return_value=None)
    scope = {'os': os, 'BackgroundScheduler': scheduler}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<schedule>', 'exec'), scope)
    scope['register_startup_tasks']()
    scheduler.assert_called_once()
