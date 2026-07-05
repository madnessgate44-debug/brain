"""Configuration management."""

from typing import Optional, List
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseSettings):
    """System configuration."""
    instance_id: str = Field(default="brain-instance-001")
    deployment_name: str = Field(default="development")
    environment: str = Field(default="development")


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    sqlite_path: str = Field(default="./workspace/db/brain.db")
    busy_timeout: int = Field(default=30, gt=0)
    journal_mode: str = Field(default="WAL")
    foreign_keys: bool = Field(default=True)
    
    @field_validator("sqlite_path")
    @classmethod
    def validate_sqlite_path(cls, v: str) -> str:
        """Validate and normalize SQLite path."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)


class WorkspaceConfig(BaseSettings):
    """Workspace configuration."""
    root: str = Field(default="./workspace")
    config_dir: str = Field(default="config")
    db_dir: str = Field(default="db")
    missions_dir: str = Field(default="missions")
    logs_dir: str = Field(default="logs")
    tmp_dir: str = Field(default="tmp")
    
    @field_validator("root")
    @classmethod
    def validate_root(cls, v: str) -> str:
        """Validate and normalize workspace root."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default="./workspace/logs/brain.log")
    structured: bool = Field(default=False)
    
    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v: Optional[str]) -> Optional[str]:
        """Validate and create log file directory."""
        if v:
            path = Path(v)
            path.parent.mkdir(parents=True, exist_ok=True)
        return v


class RecoveryConfig(BaseSettings):
    """Recovery configuration."""
    auto_recover: bool = Field(default=True)
    recoverable_phases: List[str] = Field(default=["EXECUTE", "VALIDATE", "REPAIR", "WAITING_FOR_APPROVAL"])
    orphan_detection_grace_period_seconds: int = Field(default=300, gt=0)


class ConcurrencyConfig(BaseSettings):
    """Concurrency configuration."""
    max_active_missions: int = Field(default=10, gt=0)
    heartbeat_interval_seconds: int = Field(default=30, gt=0)


class MissionDefaultsConfig(BaseSettings):
    """Mission defaults configuration."""
    priority: str = Field(default="MEDIUM")
    risk_level: str = Field(default="LOW")
    max_loop_iterations: int = Field(default=10, gt=0)


class Config(BaseSettings):
    """Root configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    
    system: SystemConfig = Field(default_factory=SystemConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    mission_defaults: MissionDefaultsConfig = Field(default_factory=MissionDefaultsConfig)
    
    @field_validator("recovery")
    @classmethod
    def validate_recoverable_phases(cls, v: RecoveryConfig) -> RecoveryConfig:
        """Validate recoverable phases."""
        valid_phases = {"INTAKE", "PLAN", "EXECUTE", "WAITING_FOR_APPROVAL", 
                        "VALIDATE", "REPAIR", "COMPLETE", "FAILED", "CANCELLED"}
        invalid_phases = set(v.recoverable_phases) - valid_phases
        if invalid_phases:
            raise ValueError(f"Invalid recoverable phases: {invalid_phases}")
        return v


def load_config() -> Config:
    """Load configuration from environment and defaults."""
    return Config()