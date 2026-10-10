"""Regression tests for documented flat environment configuration."""

from brain.core.config import load_config


def test_documented_flat_environment_variables_are_loaded(monkeypatch, tmp_path):
    database_path = tmp_path / "persistent" / "brain.db"
    workspace_root = tmp_path / "workspace"

    monkeypatch.setenv("INSTANCE_ID", "audit-instance")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DATABASE_BUSY_TIMEOUT", "47")
    monkeypatch.setenv("WORKSPACE_ROOT", str(workspace_root))
    monkeypatch.setenv("WORKSPACE_MISSIONS_DIR", "missions-custom")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_STRUCTURED", "true")
    monkeypatch.setenv("RECOVERY_AUTO_RECOVER", "false")
    monkeypatch.setenv(
        "RECOVERY_RECOVERABLE_PHASES",
        "EXECUTE,VALIDATE,WAITING_FOR_APPROVAL",
    )
    monkeypatch.setenv("CONCURRENCY_MAX_ACTIVE_MISSIONS", "3")
    monkeypatch.setenv("MISSION_DEFAULTS_PRIORITY", "HIGH")

    config = load_config()

    assert config.system.instance_id == "audit-instance"
    assert config.database.sqlite_path == str(database_path)
    assert config.database.busy_timeout == 47
    assert config.workspace.root == str(workspace_root)
    assert config.workspace.missions_dir == "missions-custom"
    assert config.logging.log_level == "DEBUG"
    assert config.logging.structured is True
    assert config.recovery.auto_recover is False
    assert config.recovery.recoverable_phases == [
        "EXECUTE",
        "VALIDATE",
        "WAITING_FOR_APPROVAL",
    ]
    assert config.concurrency.max_active_missions == 3
    assert config.mission_defaults.priority == "HIGH"
