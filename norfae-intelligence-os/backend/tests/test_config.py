from pathlib import Path

from app.core.config import ENV_FILE, Settings, settings


def test_required_database_setting_is_loaded():
    assert Settings.model_fields["DATABASE_URL"].is_required()
    assert settings.DATABASE_URL


def test_env_file_path_is_absolute_and_independent_of_working_directory(
    monkeypatch,
):
    expected_path = Path(__file__).resolve().parents[1] / ".env"

    monkeypatch.chdir(Path(__file__).resolve().parents[1] / "app")

    assert ENV_FILE == expected_path
    assert ENV_FILE.is_absolute()
    assert Settings.model_config["env_file"] == expected_path
