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
