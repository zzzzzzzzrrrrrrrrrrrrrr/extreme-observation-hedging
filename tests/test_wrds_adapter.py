"""WRDS adapter contract checks; all provider calls are replaced by fakes."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from finance_data.config import WRDSConfig
from finance_data.errors import ConfigurationError, DataAccessError, UnsupportedOperationError
from finance_data.wrds import WRDSAdapter


class ChunkIterator:
    def __init__(self, chunks=(), error=None):
        self._chunks = iter(chunks)
        self.error = error
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.error is not None:
            raise self.error
        return next(self._chunks)

    def close(self):
        self.closed = True


class WRDSAdapterTests(unittest.TestCase):
    def test_no_connection_or_query_on_construction(self):
        with patch("finance_data.wrds.create_engine") as engine, patch(
            "finance_data.wrds.pd.read_sql_query"
        ) as read:
            WRDSAdapter(WRDSConfig(username="example", password="unused"))
            engine.assert_not_called()
            read.assert_not_called()

    def test_query_passes_sql_params_and_options_unchanged(self):
        client = Mock()
        statement = text("SELECT * FROM example WHERE identifier = :identifier")
        params = {"identifier": 7}
        expected = pd.DataFrame({"identifier": [7]})
        with WRDSAdapter(client=client) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query", return_value=expected
        ) as read:
            result = adapter.query(statement, params=params, parse_dates=["date"])
            self.assertIs(result, expected)
            read.assert_called_once_with(
                statement, client, params=params, parse_dates=["date"]
            )
        client.close.assert_not_called()

    def test_raw_driver_params_pass_through_and_call_dispatches(self):
        client = Mock()
        params = (7,)
        with WRDSAdapter(client=client) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query"
        ) as read:
            adapter.call("query", "SELECT %s", params=params)
            read.assert_called_once_with("SELECT %s", client, params=params)
            with self.assertRaises(UnsupportedOperationError):
                adapter.call("load_library_list")

    def test_requires_open_and_query_rejects_chunksize(self):
        adapter = WRDSAdapter(client_factory=Mock())
        with self.assertRaises(RuntimeError):
            adapter.query("SELECT 1")
        with self.assertRaises(ValueError):
            adapter.query("SELECT 1", chunksize=None)

    def test_chunk_query_is_lazy_and_closes_after_exhaustion(self):
        frame = pd.DataFrame({"x": [1]})
        iterator = ChunkIterator([frame])
        client = Mock()
        with WRDSAdapter(client=client) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query", return_value=iterator
        ) as read:
            chunks = adapter.iter_query("SELECT %s", params=(1,), chunksize=2)
            read.assert_not_called()
            result = list(chunks)
            self.assertIs(result[0], frame)
            self.assertTrue(iterator.closed)
            read.assert_called_once_with(
                "SELECT %s", client, params=(1,), chunksize=2
            )
        client.close.assert_not_called()

    def test_chunk_iterator_closes_when_consumer_stops_early(self):
        iterator = ChunkIterator([pd.DataFrame({"x": [1]})] * 2)
        with WRDSAdapter(client=Mock()) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query", return_value=iterator
        ):
            chunks = adapter.iter_query("SELECT 1")
            next(chunks)
            chunks.close()
            self.assertTrue(iterator.closed)

    def test_chunk_fetch_failure_closes_iterator(self):
        iterator = ChunkIterator(error=OSError("fake provider failure"))
        with WRDSAdapter(client=Mock()) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query", return_value=iterator
        ):
            with self.assertRaises(DataAccessError):
                next(adapter.iter_query("SELECT 1"))
            self.assertTrue(iterator.closed)

    def test_invalid_chunk_sizes_are_rejected_before_query(self):
        with WRDSAdapter(client=Mock()) as adapter, patch(
            "finance_data.wrds.pd.read_sql_query"
        ) as read:
            for value in (0, -1, True, 1.5, "2"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    adapter.iter_query("SELECT 1", chunksize=value)
            read.assert_not_called()

    def test_owned_connection_is_read_only_bounded_and_noninteractive(self):
        config = WRDSConfig(
            username="example",
            password="p@ss:/word",
            connect_timeout=12,
            statement_timeout_ms=3000,
            passfile=Path("/tmp/example.pgpass"),
        )
        engine = Mock()
        client = engine.connect.return_value
        with patch("finance_data.wrds.create_engine", return_value=engine) as create, patch(
            "builtins.input", side_effect=AssertionError("Must never prompt")
        ), patch("getpass.getpass", side_effect=AssertionError("Must never prompt")), patch(
            "finance_data.wrds.pd.read_sql_query"
        ) as read:
            with WRDSAdapter(config) as adapter:
                self.assertIs(adapter.client, client)
                read.assert_not_called()
            url = create.call_args.args[0]
            self.assertEqual(url.username, config.username)
            self.assertEqual(url.password, config.password)
            self.assertEqual(url.host, config.host)
            self.assertEqual(url.drivername, "postgresql+psycopg2")
            self.assertIs(create.call_args.kwargs["poolclass"], NullPool)
            self.assertTrue(create.call_args.kwargs["hide_parameters"])
            self.assertEqual(create.call_args.kwargs["isolation_level"], "AUTOCOMMIT")
            self.assertEqual(
                create.call_args.kwargs["connect_args"],
                {
                    "connect_timeout": 12,
                    "sslmode": "require",
                    "options": "-c default_transaction_read_only=on -c statement_timeout=3000",
                    "passfile": "/tmp/example.pgpass",
                },
            )
            client.close.assert_called_once_with()
            engine.dispose.assert_called_once_with()

    def test_failed_open_disposes_engine_without_prompt(self):
        engine = Mock()
        engine.connect.side_effect = OSError("fake connection failure")
        with patch("finance_data.wrds.create_engine", return_value=engine), patch(
            "builtins.input", side_effect=AssertionError("Must never prompt")
        ), patch("getpass.getpass", side_effect=AssertionError("Must never prompt")):
            with self.assertRaises(DataAccessError):
                WRDSAdapter(WRDSConfig(username="example", password="unused")).open()
            engine.dispose.assert_called_once_with()

    def test_missing_username_is_rejected_without_connecting(self):
        with patch("finance_data.wrds.create_engine") as create:
            with self.assertRaises(ConfigurationError):
                WRDSAdapter(WRDSConfig(username=None)).open()
            create.assert_not_called()

    def test_password_optional_with_explicit_pgpass_and_username(self):
        engine = Mock()
        with patch("finance_data.wrds.create_engine", return_value=engine) as create:
            with WRDSAdapter(
                WRDSConfig(username="example", password=None, passfile="/tmp/example.pgpass")
            ):
                self.assertIsNone(create.call_args.args[0].password)

    def test_factory_owned_connection_is_closed(self):
        client = Mock()
        factory = Mock(return_value=client)
        with WRDSAdapter(client_factory=factory) as adapter:
            self.assertIs(adapter.client, client)
            factory.assert_called_once_with()
        client.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
