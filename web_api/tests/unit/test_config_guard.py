import pytest

from common.config_guard import verify_startup_config


def _set_valid_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
    monkeypatch.setenv(
        "QUERY_ENCRYPTION_KEY",
        "CS8EY9zwmjvdAelb-8wdVdyyVDP-y7rkXeZ-ATMRZk4=",
    )
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CENTRAL_DB_USER", "test-central-user")
    monkeypatch.setenv("CENTRAL_DB_PASSWORD", "test-central-password")


def test_bos_secret_key_acilmayi_engeller(monkeypatch):
    _set_valid_config(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(SystemExit):
        verify_startup_config()


def test_bilinen_varsayilan_reddedilir(monkeypatch):
    _set_valid_config(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "your-secret-key-here-change-in-production")

    with pytest.raises(SystemExit):
        verify_startup_config()


def test_kisa_secret_key_reddedilir(monkeypatch):
    _set_valid_config(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "kisa")

    with pytest.raises(SystemExit):
        verify_startup_config()


def test_gecersiz_fernet_key_reddedilir(monkeypatch):
    _set_valid_config(monkeypatch)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", "not-a-fernet-key")

    with pytest.raises(SystemExit):
        verify_startup_config()


def test_gecerli_config_kabul_edilir(monkeypatch):
    _set_valid_config(monkeypatch)

    verify_startup_config()


def test_yuksek_yetkili_merkezi_hesap_uyarisi_loglanir(monkeypatch, caplog):
    _set_valid_config(monkeypatch)
    monkeypatch.setenv("CENTRAL_DB_USER", "sa")

    with caplog.at_level("WARNING", logger="web_api.config_guard"):
        verify_startup_config()

    assert "yüksek yetkili bir hesapla çalışıyorsunuz" in caplog.text


def test_sifreleme_anahtari_yokken_fallback_kullanilmaz(monkeypatch):
    from app_database.models import EncryptedText

    monkeypatch.delenv("QUERY_ENCRYPTION_KEY", raising=False)
    EncryptedText._fernet = None
    try:
        with pytest.raises(RuntimeError, match="QUERY_ENCRYPTION_KEY"):
            EncryptedText().process_bind_param("sensitive", None)
    finally:
        EncryptedText._fernet = None


@pytest.mark.asyncio
async def test_lifespan_config_guard_veritabani_baslatmadan_once_calisir(monkeypatch):
    import app as app_module

    monkeypatch.delenv("SECRET_KEY", raising=False)

    class UnexpectedDatabaseConstruction:
        def __init__(self):
            raise AssertionError("AppDatabase config guard'dan önce başlatıldı")

    monkeypatch.setattr(app_module, "AppDatabase", UnexpectedDatabaseConstruction)

    with pytest.raises(SystemExit):
        async with app_module.lifespan(app_module.app):
            pass
