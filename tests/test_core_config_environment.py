"""Configuration and enum-identity regression tests."""

from brain.core import MissionPhase as CoreMissionPhase
from brain.core.config import Config
from brain.domain.enums import MissionPhase


def test_core_exports_the_canonical_domain_enum():
    assert CoreMissionPhase is MissionPhase


def test_nested_database_environment_variable_is_loaded(monkeypatch, tmp_path):
    database_path = tmp_path / "db" / "brain.db"
    monkeypatch.setenv("DATABASE__SQLITE_PATH", str(database_path))

    config = Config(_env_file=None)

    assert config.database.sqlite_path == str(database_path)
    assert database_path.parent.is_dir()
    assert config.recovery.recoverable_phases == ["EXECUTE", "VALIDATE", "REPAIR", "WAITING_FOR_APPROVAL"]
