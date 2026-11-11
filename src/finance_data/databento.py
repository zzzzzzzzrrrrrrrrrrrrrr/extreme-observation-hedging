"""Historical Databento access without query or data-format policy."""

from __future__ import annotations

from typing import Any

from ._base import ManagedAdapter
from .config import DatabentoConfig
from .errors import ConfigurationError, UnsupportedOperationError


class DatabentoAdapter(ManagedAdapter):
    """Manage a Historical client and preserve its native operations and results.

    Opening the adapter constructs a client; it does not request metadata,
    estimate costs, submit a job, or download data. Those actions are explicit
    calls. The native client remains available through ``client`` while open.
    """

    provider = "databento"
    _NAMESPACES = frozenset({"metadata", "symbology", "timeseries", "batch"})

    def __init__(
        self,
        config: DatabentoConfig | None = None,
        *,
        client: Any = None,
        client_factory: Any = None,
    ) -> None:
        super().__init__(client=client, client_factory=client_factory)
        self.config = config if config is not None else DatabentoConfig.from_env()

    def _create_client(self) -> Any:
        if not self.config.api_key:
            raise ConfigurationError("Databento requires DATABENTO_API_KEY or an explicit api_key.")

        import databento

        kwargs: dict[str, Any] = {"key": self.config.api_key}
        if self.config.gateway is not None:
            kwargs["gateway"] = self.config.gateway
        return databento.Historical(**kwargs)

    def _close_client(self, client: Any) -> None:
        # Historical currently has no public close method. Do not depend on its
        # private HTTP internals; injected factories may provide a public close.
        close = getattr(client, "close", None)
        if callable(close):
            close()

    def call(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        """Call one public method such as ``metadata.get_cost`` unchanged.

        Supported namespaces are ``metadata``, ``symbology``, ``timeseries``,
        and ``batch``. Advanced SDK functionality is also available on
        ``client``. No pagination, polling, retry, or conversion is added here.
        """
        if not isinstance(operation, str):
            raise UnsupportedOperationError("A Databento operation must be a namespace.method string.")
        parts = operation.split(".")
        if (
            len(parts) != 2
            or parts[0] not in self._NAMESPACES
            or not parts[1].isidentifier()
            or parts[1].startswith("_")
        ):
            raise UnsupportedOperationError("Use one public Databento namespace.method operation.")

        client = self.client
        try:
            namespace = getattr(client, parts[0])
            method = getattr(namespace, parts[1])
        except AttributeError:
            raise UnsupportedOperationError("The Databento client does not support this operation.") from None
        if not callable(method):
            raise UnsupportedOperationError("The requested Databento attribute is not callable.")
        return self._invoke(operation, method, *args, **kwargs)

    def get_range(self, **kwargs: Any) -> Any:
        """Explicitly request a time range and return the SDK's DBNStore."""
        return self.call("timeseries.get_range", **kwargs)

    def get_cost(self, **kwargs: Any) -> Any:
        """Explicitly request a cost estimate without submitting a data request."""
        return self.call("metadata.get_cost", **kwargs)

    def submit_job(self, **kwargs: Any) -> Any:
        """Explicitly submit a batch job; do not poll or download it."""
        return self.call("batch.submit_job", **kwargs)

    def download(self, job_id: str, **kwargs: Any) -> Any:
        """Explicitly download an existing batch job without submitting one."""
        return self.call("batch.download", job_id=job_id, **kwargs)
