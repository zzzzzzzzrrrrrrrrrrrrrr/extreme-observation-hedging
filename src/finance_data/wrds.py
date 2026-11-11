"""Noninteractive, read-only SQL access to WRDS.

SQL strings use psycopg2 parameters (``%s`` or ``%(name)s``).  SQLAlchemy
``text()`` statements instead use named parameters such as ``:name``.  Parameters
are passed through unchanged; this adapter does not construct research queries.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any

import pandas as pd
from sqlalchemy import URL, create_engine
from sqlalchemy.pool import NullPool

from ._base import ManagedAdapter
from .config import WRDSConfig
from .errors import ConfigurationError, UnsupportedOperationError


class WRDSAdapter(ManagedAdapter):
    """Manage a WRDS SQL connection without interactive credential prompts.

    A supplied ``client`` is a borrowed SQLAlchemy connection.  A
    ``client_factory`` must return a ready connection, which the adapter closes.
    Without either, the adapter creates its own connection and engine.  Use an
    explicit ``open()``/``close()`` pair or a context manager before querying.
    """

    provider = "wrds"

    def __init__(
        self,
        config: WRDSConfig | None = None,
        *,
        client: Any = None,
        client_factory: Any = None,
    ) -> None:
        self.config = config
        self._engine = None
        super().__init__(client=client, client_factory=client_factory)

    def _create_client(self) -> Any:
        config = self.config if self.config is not None else WRDSConfig.from_env()
        if not config.username or not config.username.strip():
            raise ConfigurationError("WRDS requires an explicit username.")

        # A missing password is allowed for an explicitly configured pgpass file.
        # SQLAlchemy/psycopg2 raise on authentication failure; neither prompts.
        connect_args = {
            "connect_timeout": config.connect_timeout,
            "sslmode": config.sslmode,
            "options": "-c default_transaction_read_only=on",
        }
        if config.statement_timeout_ms is not None:
            connect_args["options"] += (
                f" -c statement_timeout={config.statement_timeout_ms}"
            )
        if config.passfile is not None:
            connect_args["passfile"] = str(config.passfile)

        url = URL.create(
            "postgresql+psycopg2",
            username=config.username,
            password=config.password,
            host=config.host,
            port=config.port,
            database=config.database,
        )
        engine = create_engine(
            url,
            poolclass=NullPool,
            hide_parameters=True,
            isolation_level="AUTOCOMMIT",
            connect_args=connect_args,
        )
        try:
            connection = engine.connect()
        except BaseException:
            # Release a partially initialized pool without obscuring the cause.
            try:
                engine.dispose()
            except Exception:
                pass
            raise
        self._engine = engine
        return connection

    def _close_client(self, client: Any) -> None:
        try:
            client.close()
        finally:
            engine, self._engine = self._engine, None
            if engine is not None:
                engine.dispose()

    def query(self, sql: Any, *, params: Any = None, **kwargs: Any) -> pd.DataFrame:
        """Read an explicit SQL query into a DataFrame.

        Additional arguments are forwarded to ``pandas.read_sql_query``.  Use
        :meth:`iter_query` for chunks instead of passing ``chunksize`` here.
        """
        if "chunksize" in kwargs:
            raise ValueError("Use iter_query() for chunked queries.")
        return self._invoke(
            "query", pd.read_sql_query, sql, self.client, params=params, **kwargs
        )

    def iter_query(
        self,
        sql: Any,
        *,
        params: Any = None,
        chunksize: int = 100_000,
        **kwargs: Any,
    ) -> Iterator[pd.DataFrame]:
        """Yield query chunks, issuing SQL only when iteration begins.

        Keep the adapter open while iterating.  Exhaust the iterator or call its
        ``close()`` method when stopping early (``contextlib.closing`` is useful).
        This closes the pandas iterator; the adapter manages the connection.
        """
        if isinstance(chunksize, bool) or not isinstance(chunksize, int) or chunksize <= 0:
            raise ValueError("chunksize must be a positive integer.")
        # Validate lifecycle immediately without making a data request.
        self.client

        def chunks() -> Iterator[pd.DataFrame]:
            iterator = None
            try:
                iterator = iter(
                    self._invoke(
                        "iter_query",
                        pd.read_sql_query,
                        sql,
                        self.client,
                        params=params,
                        chunksize=chunksize,
                        **kwargs,
                    )
                )
                sentinel = object()
                while True:
                    chunk = self._invoke("iter_query", next, iterator, sentinel)
                    if chunk is sentinel:
                        return
                    yield chunk
            finally:
                close = getattr(iterator, "close", None)
                if close is not None:
                    if sys.exc_info()[0] is not None:
                        # Do not replace a fetch failure or GeneratorExit with a
                        # secondary cleanup error.
                        try:
                            self._invoke("iter_query.close", close)
                        except Exception:
                            pass
                    else:
                        self._invoke("iter_query.close", close)

        return chunks()

    def call(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        """Dispatch supported SQL operations without inventing default SQL."""
        if operation == "query":
            return self.query(*args, **kwargs)
        if operation == "iter_query":
            return self.iter_query(*args, **kwargs)
        raise UnsupportedOperationError(
            "WRDS supports 'query' and 'iter_query'; use client for native access."
        )
