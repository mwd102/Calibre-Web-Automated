import sqlite3
from pathlib import Path


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


def test_container_init_does_not_overwrite_existing_theme_preferences():
    init = (REPO_ROOT / "root/etc/s6-overlay/s6-rc.d/cwa-init/run").read_text(encoding="utf-8")

    assert 'cur.execute("UPDATE settings SET config_theme = 1 WHERE config_theme IS NULL")' in init
    assert 'cur.execute("UPDATE user SET theme = 1 WHERE theme IS NULL")' in init
    assert "theme IS NULL OR theme != 1" not in init
