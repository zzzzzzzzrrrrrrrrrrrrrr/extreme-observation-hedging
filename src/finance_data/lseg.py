"""LSEG sessions and requests, without a dependency on any particular dataset."""

from contextlib import contextmanager
import importlib
from threading import RLock

from ._base import ManagedAdapter
from .config import LSEGConfig
from .errors import UnsupportedOperationError


# LSEG access-layer functions use a process-wide default session. Calls made
# through these adapters are serialized while selecting the required session.
_DEFAULT_SESSION_LOCK = RLock()


class LSEGAdapter(ManagedAdapter):
    provider = "lseg"

    def __init__(self, config=None, *, client=None, client_factory=None, sdk=None):
        super().__init__(client=client, client_factory=client_factory)
        self.config = config if config is not None else LSEGConfig.from_env()
        self._sdk = sdk
        self._created_session_is_owned = True

    def _get_sdk(self):
        if self._sdk is None:
            self._sdk = importlib.import_module("lseg.data")
        return self._sdk

    @staticmethod
    def _default(sdk):
        try:
            return sdk.session.get_default()
        except AttributeError:
            return None

    def _create_client(self):
        sdk = self._get_sdk()
        kwargs = {}
        for key, value in (("name", self.config.session_name),
                           ("app_key", self.config.app_key),
                           ("config_name", self.config.config_name)):
            if value is not None:
                kwargs[key] = value
        with _DEFAULT_SESSION_LOCK:
            previous = self._default(sdk)
            try:
                session = sdk.open_session(**kwargs)
                # Do not take ownership if the SDK returns an existing session.
                self._created_session_is_owned = session is not previous
                return session
            except BaseException:
                failed_session = self._default(sdk)
                if failed_session is not None and failed_session is not previous:
                    try:
                        if previous is None:
                            # Public set_default(None) closes and clears the
                            # current session; it is not a harmless detach.
                            sdk.session.set_default(None)
                        else:
                            failed_session.close()
                    except Exception:
                        pass  # Preserve the original open failure.
                raise
            finally:
                # Clearing a default also closes it in the LSEG SDK. With no
                # prior default, retain our new session until adapter.close().
                if previous is not None:
                    sdk.session.set_default(previous)

    def _close_client(self, client):
        if not self._created_session_is_owned:
            return
        with _DEFAULT_SESSION_LOCK:
            if self._sdk is not None and self._default(self._sdk) is client:
                # The public SDK operation both closes and clears its default.
                self._sdk.session.set_default(None)
            else:
                client.close()

    @property
    def session(self):
        return self.client

    @contextmanager
    def _using_default(self):
        session = self.session  # Require explicit open before touching SDK state.
        sdk = self._get_sdk()
        with _DEFAULT_SESSION_LOCK:
            previous = self._default(sdk)
            sdk.session.set_default(session)
            try:
                yield sdk
            finally:
                if previous is not None:
                    sdk.session.set_default(previous)
                # Otherwise keep this session as default. Clearing it would
                # close it, including when it belongs to the caller.

    def call(self, operation, *args, **kwargs):
        """Call a synchronous access-layer method using this adapter's session.

        Supports get_data/get_history and public methods under news, discovery,
        dates_and_calendars, and tradefeedr. Content-layer Definitions use
        request() so their session is passed explicitly. Streaming and async
        APIs require their own lifecycle and are not dispatched here.
        """
        if not isinstance(operation, str):
            raise UnsupportedOperationError("LSEG operation must be a public method path.")
        parts = operation.split(".")
        if (not parts or any(not p.isidentifier() or p.startswith("_") for p in parts)
                or parts[0] not in {"get_data", "get_history", "news", "discovery",
                                    "dates_and_calendars", "tradefeedr"}
                or any("stream" in p or p.endswith("_async") for p in parts)):
            raise UnsupportedOperationError("Unsupported LSEG synchronous operation.")
        with self._using_default() as sdk:
            function = sdk
            try:
                for part in parts:
                    function = getattr(function, part)
            except AttributeError:
                raise UnsupportedOperationError("LSEG operation is unavailable in this SDK.") from None
            if not callable(function):
                raise UnsupportedOperationError("LSEG operation is not callable.")
            return self._invoke(operation, function, *args, **kwargs)

    def get_data(self, *args, **kwargs):
        return self.call("get_data", *args, **kwargs)

    def get_history(self, *args, **kwargs):
        return self.call("get_history", *args, **kwargs)

    def request(self, definition, **kwargs):
        """Execute any SDK content/delivery Definition accepting get_data(session=...)."""
        session = self.session
        if "session" in kwargs:
            raise ValueError("The adapter supplies the session; omit the session argument.")
        get_data = getattr(definition, "get_data", None)
        if not callable(get_data):
            raise UnsupportedOperationError("Pass a Definition with a get_data method.")
        return self._invoke("definition.get_data", get_data, session=session, **kwargs)
