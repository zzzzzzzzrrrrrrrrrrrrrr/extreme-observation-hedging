"""Compose the providers without opening any connection."""

from .config import Settings
from .databento import DatabentoAdapter
from .lseg import LSEGAdapter
from .wrds import WRDSAdapter


class DataAccess:
    def __init__(self, settings=None, *, wrds=None, lseg=None, databento=None):
        self.settings = settings if settings is not None else Settings.from_env()
        self.wrds = wrds if wrds is not None else WRDSAdapter(self.settings.wrds)
        self.lseg = lseg if lseg is not None else LSEGAdapter(self.settings.lseg)
        self.databento = databento if databento is not None else DatabentoAdapter(self.settings.databento)

    def close(self):
        errors = []
        for adapter in (self.wrds, self.lseg, self.databento):
            try:
                adapter.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("One or more data connections could not be closed.", errors)

    def __enter__(self):
        # Each provider is opened explicitly, so unavailable providers do not
        # block use of the others.
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except Exception as error:
            if exc is None:
                raise
            exc.add_note(f"Resource cleanup also failed: {error}")
        return False
