"""Explicit, read-only configuration. Loading it never changes os.environ."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
from pathlib import Path

from .errors import ConfigurationError


def _values(env_file=None, environ=None):
    values = {}
    if env_file is not None:
        path = Path(env_file).expanduser()
        if not path.is_file():
            raise ConfigurationError("The explicitly selected environment file does not exist.")
        from dotenv import dotenv_values

        values.update(dotenv_values(path, interpolate=False))
    values.update(os.environ if environ is None else environ)
    return values


def _integer(values, key, default, *, minimum=1):
    raw = values.get(key)
    if raw in (None, ""):
        return default
    try:
        result = int(raw)
        if result < minimum:
            raise ValueError
        return result
    except (TypeError, ValueError):
        raise ConfigurationError(f"{key} must be an integer >= {minimum}.") from None


@dataclass(frozen=True)
class WRDSConfig:
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    host: str = "wrds-pgdata.wharton.upenn.edu"
    port: int = 9737
    database: str = "wrds"
    connect_timeout: int = 45
    statement_timeout_ms: int | None = None
    sslmode: str = "require"
    passfile: str | None = field(default=None, repr=False)

    def __post_init__(self):
        for name, minimum, maximum in (("port", 1, 65535),
                                       ("connect_timeout", 1, None),
                                       ("statement_timeout_ms", 0, None)):
            value = getattr(self, name)
            if name == "statement_timeout_ms" and value is None:
                continue
            if (isinstance(value, bool) or not isinstance(value, int)
                    or value < minimum or (maximum is not None and value > maximum)):
                raise ConfigurationError(f"WRDS {name} is outside its valid integer range.")

    @classmethod
    def from_env(cls, env_file=None, *, environ: Mapping[str, str] | None = None):
        values = _values(env_file, environ)
        return cls(
            username=values.get("WRDS_USERNAME") or None,
            password=values.get("WRDS_PASSWORD") or None,
            host=values.get("WRDS_HOST") or cls.host,
            port=_integer(values, "WRDS_PORT", cls.port),
            database=values.get("WRDS_DATABASE") or cls.database,
            connect_timeout=_integer(values, "WRDS_CONNECT_TIMEOUT", cls.connect_timeout),
            statement_timeout_ms=_integer(values, "WRDS_STATEMENT_TIMEOUT_MS", None, minimum=0),
            sslmode=values.get("WRDS_SSLMODE") or cls.sslmode,
            passfile=values.get("WRDS_PASSFILE") or values.get("PGPASSFILE") or None,
        )


@dataclass(frozen=True)
class LSEGConfig:
    # None honours the SDK's configuration, including sessions.default.
    session_name: str | None = None
    app_key: str | None = field(default=None, repr=False)
    config_name: str | None = None

    @classmethod
    def from_env(cls, env_file=None, *, environ: Mapping[str, str] | None = None):
        values = _values(env_file, environ)
        return cls(
            session_name=values.get("LSEG_SESSION_NAME") or None,
            app_key=values.get("LSEG_APP_KEY") or None,
            config_name=values.get("LSEG_CONFIG_FILE") or None,
        )


@dataclass(frozen=True)
class DatabentoConfig:
    api_key: str | None = field(default=None, repr=False)
    gateway: str | None = None

    @classmethod
    def from_env(cls, env_file=None, *, environ: Mapping[str, str] | None = None):
        values = _values(env_file, environ)
        return cls(
            api_key=values.get("DATABENTO_API_KEY") or None,
            gateway=values.get("DATABENTO_GATEWAY") or None,
        )


@dataclass(frozen=True)
class Settings:
    wrds: WRDSConfig = field(default_factory=WRDSConfig)
    lseg: LSEGConfig = field(default_factory=LSEGConfig)
    databento: DatabentoConfig = field(default_factory=DatabentoConfig)

    @classmethod
    def from_env(cls, env_file=None, *, environ: Mapping[str, str] | None = None):
        values = _values(env_file, environ)
        return cls(
            wrds=WRDSConfig.from_env(environ=values),
            lseg=LSEGConfig.from_env(environ=values),
            databento=DatabentoConfig.from_env(environ=values),
        )
