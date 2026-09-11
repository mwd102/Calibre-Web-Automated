"""Authorization tests for shelf ordering."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class _Blueprint:
    def __init__(self, *args, **kwargs):
        pass

    def route(self, *args, **kwargs):
        return lambda function: function


class _Column:
    def __eq__(self, other):
        return self, other

    def asc(self):
        return self


class _Query:
    def __init__(self, *, first_value=None, all_value=None):
        self.first_value = first_value
        self.all_value = all_value

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def add_columns(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.all_value or []


class _Logger:
    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


class _OperationalError(Exception):
    pass


class _InvalidRequestError(Exception):
    pass


@pytest.fixture
def shelf_module(monkeypatch):
    """Load cps.shelf with the minimal dependencies needed by order_shelf."""
    def install(name, **attributes):
        module = ModuleType(name)
        for key, value in attributes.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    cps = install("cps")
    cps.__path__ = [str(Path(__file__).resolve().parents[2] / "cps")]

    flask = install(
        "flask",
        Blueprint=_Blueprint,
        abort=lambda code: (_ for _ in ()).throw(RuntimeError(code)),
        flash=lambda *args, **kwargs: None,
        redirect=lambda *args, **kwargs: "redirected",
        request=SimpleNamespace(),
        url_for=lambda *args, **kwargs: "url",
        jsonify=lambda *args, **kwargs: "json",
    )
    install("flask_babel", gettext=lambda value, **kwargs: value)

    sqlalchemy_exc = install(
        "sqlalchemy.exc",
        InvalidRequestError=_InvalidRequestError,
        OperationalError=_OperationalError,
    )
    sqlalchemy = install("sqlalchemy")
    sqlalchemy.__path__ = []
    sqlalchemy_sql = install("sqlalchemy.sql")
    sqlalchemy_sql.__path__ = []
    install("sqlalchemy.sql.expression", func=SimpleNamespace(), true=lambda: True)
    sqlalchemy.exc = sqlalchemy_exc
    sqlalchemy.sql = sqlalchemy_sql

    logger = install("cps.logger", create=lambda: _Logger())
    config = install("cps.config")
    calibre_db = install("cps.calibre_db")
    db = install("cps.db")
    ub = install("cps.ub")
    render_template = install(
        "cps.render_template",
        render_title_template=lambda *args, **kwargs: "rendered",
    )
    usermanagement = install(
        "cps.usermanagement",
        login_required_if_no_ano=lambda function: function,
        user_login_required=lambda function: function,
    )
    cw_login = install("cps.cw_login", current_user=SimpleNamespace())
    services = install("cps.services", hardcover=SimpleNamespace())

    for module in (calibre_db, config, db, logger, render_template, services,
                   ub, usermanagement, cw_login):
        setattr(cps, module.__name__.split(".")[-1], module)

    module_name = "cps.shelf"
    module_path = Path(__file__).resolve().parents[2] / "cps" / "shelf.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "cps"
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    module.request = flask.request
    return module, ub, db, calibre_db


def _configure_shelf(module, ub, db, calibre_db, *, can_edit, method, form=None):
    class ShelfModel:
        id = _Column()

    class BookShelfModel:
        shelf = _Column()
        order = _Column()
        book_id = _Column()

    class BooksModel:
        id = _Column()

    shelf = SimpleNamespace(id=7, name="Public shelf", is_public=True, user_id=99)
    books = [SimpleNamespace(book_id=1, order=1), SimpleNamespace(book_id=2, order=2)]
    shelf_query = _Query(first_value=shelf)
    book_shelf_query = _Query(all_value=books)

    class Session:
        def __init__(self):
            self.queries = []
            self.commit_calls = 0

        def query(self, model):
            self.queries.append(model)
            if model is ShelfModel:
                return shelf_query
            if model is BookShelfModel:
                return book_shelf_query
            raise AssertionError(f"unexpected model: {model}")

        def commit(self):
            self.commit_calls += 1

    class CalibreSession:
        def query(self, model):
            assert model is BooksModel
            return _Query(all_value=[])

    ub.Shelf = ShelfModel
    ub.BookShelf = BookShelfModel
    ub.session = Session()
    db.Books = BooksModel
    calibre_db.session = CalibreSession()
    calibre_db.common_filters = lambda: SimpleNamespace(label=lambda value: value)
    module.current_user = SimpleNamespace(
        id=1,
        role_edit_shelfs=lambda: can_edit,
    )
    module.request.method = method
    module.request.form = SimpleNamespace(to_dict=lambda: form or {})
    return shelf, books, ub.session


@pytest.mark.parametrize("can_edit", [False, True])
def test_order_shelf_viewer_cannot_mutate_but_editor_can(
    shelf_module, can_edit
):
    module, ub, db, calibre_db = shelf_module
    _, books, session = _configure_shelf(
        module,
        ub,
        db,
        calibre_db,
        can_edit=can_edit,
        method="POST",
        form={"1": "2", "2": "1"},
    )

    assert module.order_shelf(7) == "rendered"

    if can_edit:
        assert session.commit_calls == 1
        assert [book.order for book in books] == ["2", "1"]
        assert ub.BookShelf in session.queries
    else:
        assert session.commit_calls == 0
        assert [book.order for book in books] == [1, 2]
        assert ub.BookShelf not in session.queries


def test_order_shelf_view_remains_available_to_viewer(shelf_module):
    module, ub, db, calibre_db = shelf_module
    _configure_shelf(module, ub, db, calibre_db, can_edit=False, method="GET")

    assert module.order_shelf(7) == "rendered"
