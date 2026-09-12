import os
import sqlite3
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_container_init_preserves_explicitly_cleared_binary_helpers():
    init = (REPO_ROOT / "root/etc/s6-overlay/s6-rc.d/cwa-init/run").read_text(encoding="utf-8")

    assert "APP_DB_CREATED=0" in init
    assert "config_kepubifypath is NULL or ($APP_DB_CREATED = 1 and config_kepubifypath = '')" in init
    assert "update settings set config_kepubifypath='/usr/bin/kepubify'," not in init

    sql = init.split("sqlite3 /config/app.db <<EOS", 1)[1].split("EOS", 1)[0]
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE settings "
        "(config_kepubifypath TEXT, config_converterpath TEXT, config_binariesdir TEXT)"
    )
    connection.execute("INSERT INTO settings VALUES ('', '/custom/converter', NULL)")
    connection.executescript(sql.replace("$APP_DB_CREATED", "0"))

    assert connection.execute("SELECT * FROM settings").fetchone() == (
        "",
        "/custom/converter",
        "/usr/bin",
    )

    connection.execute("DELETE FROM settings")
    connection.execute("INSERT INTO settings VALUES ('', '', '')")
    connection.executescript(sql.replace("$APP_DB_CREATED", "1"))
    assert connection.execute("SELECT * FROM settings").fetchone() == (
        "/usr/bin/kepubify",
        "/usr/bin/ebook-convert",
        "/usr/bin",
    )


def _theme_migration_source():
    init = (REPO_ROOT / "root/etc/s6-overlay/s6-rc.d/cwa-init/run").read_text(encoding="utf-8")
    marker = 'APP_DB_CREATED="$APP_DB_CREATED" python3 - <<\'PY\'\n'
    return init.split(marker, 1)[1].split("\nPY\n", 1)[0]


def _run_theme_migration(db_path, fresh=False):
    real_connect = sqlite3.connect

    def connect_test_database(_configured_path):
        return real_connect(db_path)

    with mock.patch.object(sqlite3, "connect", connect_test_database), mock.patch.dict(
        os.environ, {"APP_DB_CREATED": "1" if fresh else "0"}
    ):
        exec(compile(_theme_migration_source(), "cwa-init-theme-migration", "exec"), {})


def _create_theme_database(db_path, config_theme, user_theme):
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE settings (config_theme INTEGER)")
    connection.execute('CREATE TABLE "user" (theme INTEGER)')
    connection.execute("INSERT INTO settings VALUES (?)", (config_theme,))
    connection.execute('INSERT INTO "user" VALUES (?)', (user_theme,))
    connection.commit()
    connection.close()


def _read_themes(db_path):
    connection = sqlite3.connect(db_path)
    result = (
        connection.execute("SELECT config_theme FROM settings").fetchone()[0],
        connection.execute('SELECT theme FROM "user"').fetchone()[0],
    )
    connection.close()
    return result


def test_container_init_preserves_existing_standard_theme_on_repeated_start(tmp_path):
    db_path = tmp_path / "existing.db"
    _create_theme_database(db_path, config_theme=0, user_theme=0)

    _run_theme_migration(db_path)
    _run_theme_migration(db_path)

    assert _read_themes(db_path) == (0, 0)


def test_container_init_fills_null_themes_without_changing_them_again(tmp_path):
    db_path = tmp_path / "legacy-null.db"
    _create_theme_database(db_path, config_theme=None, user_theme=None)

    _run_theme_migration(db_path)
    assert _read_themes(db_path) == (1, 1)

    _run_theme_migration(db_path)
    assert _read_themes(db_path) == (1, 1)
