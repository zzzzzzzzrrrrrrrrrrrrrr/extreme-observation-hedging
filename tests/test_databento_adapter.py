"""Offline adapter tests: all provider clients here are local test doubles."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from finance_data.config import DatabentoConfig
from finance_data.databento import DatabentoAdapter
from finance_data.errors import ConfigurationError, DataAccessError, UnsupportedOperationError


def fake_client(*, public_close: bool = True) -> SimpleNamespace:
    client = SimpleNamespace(
        metadata=SimpleNamespace(get_cost=Mock(return_value=0.42)),
        symbology=SimpleNamespace(resolve=Mock(return_value=object())),
        timeseries=SimpleNamespace(get_range=Mock(return_value=object())),
        batch=SimpleNamespace(
            submit_job=Mock(return_value=object()),
            download=Mock(return_value=object()),
        ),
    )
    if public_close:
        client.close = Mock()
    return client


class DatabentoAdapterTests(unittest.TestCase):
    def test_factory_is_lazy_and_owned_client_is_closed(self) -> None:
        native = fake_client()
        factory = Mock(return_value=native)
        adapter = DatabentoAdapter(client_factory=factory)
        factory.assert_not_called()
        with adapter as opened:
            self.assertIs(opened, adapter)
            self.assertIs(adapter.client, native)
            factory.assert_called_once_with()
            native.metadata.get_cost.assert_not_called()
            native.timeseries.get_range.assert_not_called()
            native.batch.submit_job.assert_not_called()
            native.batch.download.assert_not_called()
        native.close.assert_called_once_with()
        adapter.close()
        native.close.assert_called_once_with()

    def test_borrowed_client_is_not_closed(self) -> None:
        native = fake_client()
        with DatabentoAdapter(client=native) as adapter:
            self.assertIs(adapter.client, native)
        native.close.assert_not_called()

    def test_request_requires_explicit_open(self) -> None:
        factory = Mock(return_value=fake_client())
        adapter = DatabentoAdapter(client_factory=factory)
        with self.assertRaises(RuntimeError):
            adapter.get_cost(dataset="TEST.DATASET")
        factory.assert_not_called()

    def test_owned_client_without_public_close_is_supported(self) -> None:
        native = fake_client(public_close=False)
        with DatabentoAdapter(client_factory=lambda: native) as adapter:
            self.assertIs(adapter.client, native)

    def test_get_range_preserves_parameters_and_native_result(self) -> None:
        native = fake_client()
        kwargs = {
            "dataset": "TEST.DATASET",
            "schema": "ohlcv-1m",
            "symbols": ["TEST"],
            "start": "2025-01-02T00:00:00Z",
            "end": "2025-01-03T00:00:00Z",
            "limit": 7,
            "stype_in": "raw_symbol",
        }
        with DatabentoAdapter(client=native) as adapter:
            result = adapter.get_range(**kwargs)
        self.assertIs(result, native.timeseries.get_range.return_value)
        native.timeseries.get_range.assert_called_once_with(**kwargs)

    def test_cost_estimate_does_not_submit_or_download(self) -> None:
        native = fake_client()
        with DatabentoAdapter(client=native) as adapter:
            result = adapter.get_cost(dataset="TEST.DATASET", schema="trades", start="2025-01-02")
        self.assertEqual(result, 0.42)
        native.metadata.get_cost.assert_called_once_with(
            dataset="TEST.DATASET", schema="trades", start="2025-01-02"
        )
        native.timeseries.get_range.assert_not_called()
        native.batch.submit_job.assert_not_called()
        native.batch.download.assert_not_called()

    def test_batch_steps_are_separate_explicit_operations(self) -> None:
        native = fake_client()
        with DatabentoAdapter(client=native) as adapter:
            submitted = adapter.submit_job(
                dataset="TEST.DATASET", symbols=["TEST"], schema="trades", start="2025-01-02"
            )
            native.batch.download.assert_not_called()
            downloaded = adapter.download("job-id", output_dir="output")
        self.assertIs(submitted, native.batch.submit_job.return_value)
        self.assertIs(downloaded, native.batch.download.return_value)
        native.batch.submit_job.assert_called_once_with(
            dataset="TEST.DATASET", symbols=["TEST"], schema="trades", start="2025-01-02"
        )
        native.batch.download.assert_called_once_with(job_id="job-id", output_dir="output")

    def test_call_preserves_positional_arguments_and_symbology_result(self) -> None:
        native = fake_client()
        kwargs = {
            "symbols": ["TEST"],
            "stype_in": "raw_symbol",
            "stype_out": "instrument_id",
            "start_date": "2025-01-02",
        }
        with DatabentoAdapter(client=native) as adapter:
            result = adapter.call("symbology.resolve", "TEST.DATASET", **kwargs)
        self.assertIs(result, native.symbology.resolve.return_value)
        native.symbology.resolve.assert_called_once_with("TEST.DATASET", **kwargs)

    def test_invalid_operation_paths_are_rejected(self) -> None:
        native = fake_client()
        native.metadata.not_a_method = 1
        invalid = (
            "", "metadata", "metadata.", ".get_cost", "metadata..get_cost",
            "metadata.get_cost.__call__", "metadata._private", "_metadata.get_cost",
            "unknown.get_cost", "metadata.missing", "metadata.not_a_method", None,
        )
        with DatabentoAdapter(client=native) as adapter:
            for operation in invalid:
                with self.subTest(operation=operation), self.assertRaises(UnsupportedOperationError):
                    adapter.call(operation)
        native.metadata.get_cost.assert_not_called()

    def test_missing_key_fails_before_client_construction(self) -> None:
        adapter = DatabentoAdapter(DatabentoConfig(api_key=None))
        with patch("databento.Historical") as historical:
            with self.assertRaises(ConfigurationError):
                adapter.open()
        historical.assert_not_called()

    def test_default_sdk_client_is_created_only_on_open(self) -> None:
        native = fake_client()
        with patch("databento.Historical", return_value=native) as historical:
            adapter = DatabentoAdapter(DatabentoConfig(api_key="unit-test-key"))
            historical.assert_not_called()
            with adapter:
                historical.assert_called_once_with(key="unit-test-key")
        native.close.assert_called_once_with()

    def test_explicit_gateway_is_forwarded(self) -> None:
        native = fake_client()
        with patch("databento.Historical", return_value=native) as historical:
            with DatabentoAdapter(
                DatabentoConfig(api_key="unit-test-key", gateway="https://example.invalid")
            ):
                historical.assert_called_once_with(
                    key="unit-test-key", gateway="https://example.invalid"
                )

    def test_failure_closes_owned_client_and_retains_error_without_disclosing_message(self) -> None:
        native = fake_client()
        failure = RuntimeError("test private provider details")
        native.timeseries.get_range.side_effect = failure
        adapter = DatabentoAdapter(client_factory=lambda: native)
        with self.assertRaises(DataAccessError) as raised:
            with adapter:
                adapter.get_range(dataset="TEST.DATASET")
        self.assertIs(raised.exception.original_error, failure)
        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertNotIn(str(failure), str(raised.exception))
        native.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
