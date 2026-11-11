"""Reusable provider interfaces. Importing this package performs no network I/O."""

from .clients import DataAccess
from .config import DatabentoConfig, LSEGConfig, Settings, WRDSConfig
from .databento import DatabentoAdapter
from .errors import ConfigurationError, DataAccessError, UnsupportedOperationError
from .lseg import LSEGAdapter
from .wrds import WRDSAdapter

__all__ = [
    "DataAccess", "Settings", "WRDSConfig", "LSEGConfig", "DatabentoConfig",
    "WRDSAdapter", "LSEGAdapter", "DatabentoAdapter", "ConfigurationError",
    "DataAccessError", "UnsupportedOperationError",
]
