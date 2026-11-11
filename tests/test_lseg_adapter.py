import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from finance_data import ConfigurationError, DataAccessError, LSEGAdapter, LSEGConfig
from finance_data.errors import UnsupportedOperationError


class FakeSession:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class FakeSDK:
    def __init__(self, previous=None):
        self.current = previous
        self.created = FakeSession()
        self.open_session = Mock(side_effect=self._open)
        self.get_data = Mock(side_effect=self._request)
        self.get_history = Mock(side_effect=self._request)
        self.news = SimpleNamespace(get_headlines=Mock(return_value=object()))
        self.session = SimpleNamespace(get_default=self._default, set_default=self._set)

    def _default(self):
        if self.current is None:
            raise AttributeError("No default session")
        return self.current

    def _set(self, value):
        # The real SDK closes its current session when clearing the default.
        if value is None and self.current is not None:
            self.current.close()
        self.current = value

    def _request(self, **kwargs):
        if self.current is None or self.current.closed:
            raise RuntimeError("Session is not opened")
        return self.current, kwargs

    def _open(self, **kwargs):
        self.current = self.created
        return self.created


class LSEGTests(unittest.TestCase):
    def test_construction_is_lazy_and_requests_require_open(self):
        sdk = FakeSDK()
        adapter = LSEGAdapter(sdk=sdk)
        sdk.open_session.assert_not_called()
        with self.assertRaises(RuntimeError):
            adapter.get_data(universe=object(), fields=object())
        sdk.get_data.assert_not_called()

    def test_configuration_and_original_default_are_preserved(self):
        previous = FakeSession()
        sdk = FakeSDK(previous)
        config = LSEGConfig(session_name="desktop.workspace", app_key="not-a-real-key",
                            config_name="existing-config.json")
        with LSEGAdapter(config, sdk=sdk) as adapter:
            sdk.open_session.assert_called_once_with(name="desktop.workspace", app_key="not-a-real-key",
                                                    config_name="existing-config.json")
            self.assertIs(sdk.current, previous)
            params = {"universe": object(), "fields": object(), "parameters": {"custom": object()}}
            session, received = adapter.get_data(**params)
            self.assertIs(session, sdk.created)
            self.assertIs(received["parameters"], params["parameters"])
            self.assertIs(sdk.current, previous)
        self.assertEqual(sdk.created.closed, 1)
        self.assertEqual(previous.closed, 0)
        self.assertIs(sdk.current, previous)

    def test_no_prior_default_keeps_owned_session_open_for_repeated_requests(self):
        sdk = FakeSDK()
        with LSEGAdapter(sdk=sdk) as adapter:
            self.assertIs(sdk.current, sdk.created)
            self.assertEqual(sdk.created.closed, 0)
            for request in (adapter.get_history, adapter.get_data):
                session, _ = request(universe=object())
                self.assertIs(session, sdk.created)
                self.assertIs(sdk.current, sdk.created)
                self.assertEqual(sdk.created.closed, 0)
        self.assertIsNone(sdk.current)
        self.assertEqual(sdk.created.closed, 1)

    def test_request_with_no_prior_default_does_not_close_borrowed_session(self):
        borrowed = FakeSession()
        sdk = FakeSDK()
        with LSEGAdapter(client=borrowed, sdk=sdk) as adapter:
            self.assertIsNone(sdk.current)
            for request in (adapter.get_history, adapter.get_data):
                session, _ = request(universe=object())
                self.assertIs(session, borrowed)
                self.assertEqual(borrowed.closed, 0)
        self.assertIs(sdk.current, borrowed)
        self.assertEqual(borrowed.closed, 0)

    def test_failed_request_restores_default_and_sanitizes_message(self):
        previous = FakeSession()
        sdk = FakeSDK(previous)
        original = ValueError("private credential material")
        sdk.get_data.side_effect = original
        with LSEGAdapter(sdk=sdk) as adapter:
            with self.assertRaises(DataAccessError) as failure:
                adapter.get_data(universe=object(), fields=object())
            self.assertIs(failure.exception.original_error, original)
            self.assertNotIn("private credential", str(failure.exception))
            self.assertIs(sdk.current, previous)

    def test_failed_open_cleans_partial_session_and_restores_default(self):
        previous = FakeSession()
        sdk = FakeSDK(previous)

        def fail(**kwargs):
            sdk.current = sdk.created
            raise RuntimeError("connection failed")

        sdk.open_session.side_effect = fail
        adapter = LSEGAdapter(sdk=sdk)
        with self.assertRaises(DataAccessError):
            adapter.open()
        self.assertFalse(adapter.is_open)
        self.assertEqual(sdk.created.closed, 1)
        self.assertIs(sdk.current, previous)

    def test_failed_open_with_no_default_closes_and_clears_partial_session(self):
        sdk = FakeSDK()

        def fail(**kwargs):
            sdk.current = sdk.created
            raise RuntimeError("connection failed")

        sdk.open_session.side_effect = fail
        adapter = LSEGAdapter(sdk=sdk)
        with self.assertRaises(DataAccessError):
            adapter.open()
        self.assertFalse(adapter.is_open)
        self.assertEqual(sdk.created.closed, 1)
        self.assertIsNone(sdk.current)

    def test_borrowed_session_and_reentrant_context(self):
        borrowed = FakeSession()
        sdk = FakeSDK()
        adapter = LSEGAdapter(client=borrowed, sdk=sdk)
        with adapter:
            with adapter:
                self.assertIs(adapter.session, borrowed)
            self.assertTrue(adapter.is_open)
        sdk.open_session.assert_not_called()
        self.assertEqual(borrowed.closed, 0)
        self.assertFalse(adapter.is_open)

    def test_interrupted_open_cleans_partial_session(self):
        previous = FakeSession()
        sdk = FakeSDK(previous)

        def interrupted(**kwargs):
            sdk.current = sdk.created
            raise KeyboardInterrupt

        sdk.open_session.side_effect = interrupted
        adapter = LSEGAdapter(sdk=sdk)
        with self.assertRaises(KeyboardInterrupt):
            adapter.open()
        self.assertEqual(sdk.created.closed, 1)
        self.assertIs(sdk.current, previous)
        self.assertFalse(adapter.is_open)

    def test_factory_client_is_owned(self):
        created = FakeSession()
        factory = Mock(return_value=created)
        with LSEGAdapter(client_factory=factory):
            factory.assert_called_once_with()
        self.assertEqual(created.closed, 1)

    def test_existing_sdk_default_is_not_closed_if_reused(self):
        previous = FakeSession()
        sdk = FakeSDK(previous)
        sdk.created = previous
        with LSEGAdapter(sdk=sdk):
            pass
        self.assertEqual(previous.closed, 0)

    def test_definition_gets_explicit_session_and_native_response(self):
        session = FakeSession()
        result = object()
        definition = SimpleNamespace(get_data=Mock(return_value=result))
        with LSEGAdapter(client=session) as adapter:
            with patch("finance_data.lseg.importlib.import_module") as load:
                self.assertIs(adapter.request(definition), result)
                load.assert_not_called()
            definition.get_data.assert_called_once_with(session=session)
            with self.assertRaises(ValueError):
                adapter.request(definition, session=object())

    def test_invalid_operations_do_not_reach_sdk(self):
        sdk = FakeSDK()
        with LSEGAdapter(sdk=sdk) as adapter:
            for name in ("open_session", "close_session", "session.set_default", "__dict__",
                         "news._private", "open_pricing_stream", "get_history.__call__"):
                with self.subTest(operation=name), self.assertRaises(UnsupportedOperationError):
                    adapter.call(name)
            with self.assertRaises(UnsupportedOperationError):
                adapter.request(object())
            self.assertIs(adapter.call("news.get_headlines"), sdk.news.get_headlines.return_value)


if __name__ == "__main__":
    unittest.main()
