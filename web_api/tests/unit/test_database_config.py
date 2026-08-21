import importlib


def test_database_provider_config_does_not_default_to_sa(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    monkeypatch.setenv("DB_PASSWORD", "")
    monkeypatch.setenv("CENTRAL_DB_USER", "")
    monkeypatch.setenv("CENTRAL_DB_PASSWORD", "")

    from database_provider import config

    config = importlib.reload(config)

    assert config.DB_USER == ""
    assert config.CENTRAL_DB_USER == ""


def test_app_database_config_does_not_default_to_sa(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    monkeypatch.setenv("DB_PASSWORD", "")
    monkeypatch.setenv("APP_DATABASE_URL", "")

    from app_database import config

    config = importlib.reload(config)

    assert config.db_user == ""


def test_target_query_timeout_defaults_to_five_minutes(monkeypatch):
    monkeypatch.delenv("QUERY_TIMEOUT_SECONDS", raising=False)

    from database_provider import config

    config = importlib.reload(config)

    assert config.QUERY_TIMEOUT_SECONDS == 300


def test_connect_args_for_mssql():
    from database_provider.config import get_connect_args

    assert get_connect_args("mssql", 120) == {"timeout": 120}


def test_connect_args_for_postgresql():
    from database_provider.config import get_connect_args

    assert get_connect_args("postgresql", 120) == {
        "command_timeout": 120,
        "server_settings": {
            "statement_timeout": "120000",
            "idle_in_transaction_session_timeout": "150000",
        },
    }


def test_mysql_uses_session_init_sql_for_query_timeout():
    from database_provider.config import SESSION_INIT_SQL, get_connect_args

    assert get_connect_args("mysql", 120) == {"connect_timeout": 15}
    assert SESSION_INIT_SQL["mysql"] == (
        "SET SESSION max_execution_time = {ms}"
    )


def test_unknown_database_has_no_driver_specific_connect_args():
    from database_provider.config import get_connect_args

    assert get_connect_args("unknown", 120) == {}
