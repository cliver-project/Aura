from aura.config import Settings, clear_settings_cache


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.gitea_url == "http://localhost:3000"
    assert settings.gitea_user == "aura"
    assert settings.max_concurrent_runs == 3
    assert settings.default_locale == "en"
    assert settings.auto_pipeline is True


def test_sync_database_url_switches_driver_and_preserves_password() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://aura:s%40cret@127.0.0.1:5433/aura",
    )
    assert settings.sync_database_url.startswith("postgresql+psycopg://aura:s%40cret@127.0.0.1:5433/aura")


def test_sync_database_url_accepts_plain_postgresql_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://aura:secret@db.local:5432/aura",
    )
    assert settings.sync_database_url.startswith("postgresql+psycopg://aura:secret@db.local:5432/aura")


def test_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("AURA_GITEA_URL", "http://gitea.test:3001")
    monkeypatch.setenv("AURA_MAX_CONCURRENT_RUNS", "7")
    monkeypatch.setenv("AURA_AUTO_PIPELINE", "false")
    clear_settings_cache()
    settings = Settings(_env_file=None)
    assert settings.gitea_url == "http://gitea.test:3001"
    assert settings.max_concurrent_runs == 7
    assert settings.auto_pipeline is False
