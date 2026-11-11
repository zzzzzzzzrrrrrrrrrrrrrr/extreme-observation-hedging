# Data access

Install `finance_data` as described in the [README](../README.md).

The adapters manage configuration, connections, and provider calls. They do not
choose instruments, database tables, fields, frequencies, or date ranges.
Importing the package, loading settings, and constructing adapters do not log in
or request data. Open each provider explicitly when it is needed.

## Structure and scope

```text
src/finance_data/
├── config.py       # Connection settings and explicit .env loading
├── _base.py        # Connection lifecycle, ownership, and error handling
├── wrds.py         # PostgreSQL queries and chunked reads
├── lseg.py         # LSEG sessions and access/content requests
├── databento.py    # Databento Historical API
├── clients.py      # DataAccess: assemble the three adapters
└── errors.py
tests/              # Local tests without provider requests
```

All three adapters expose `open()`, `close()`, context management, `call()`, and
the native `client`. Request arguments and return values retain their provider
semantics: WRDS SQL, LSEG field requests, and Databento DBN are not forced into a
single query language or return type. The same adapter can serve different
research requests within its supported operations; SDK changes or new API types
may still require adapter changes.

Identifier mapping, time-zone alignment, price adjustments, cleaning, returns,
and models belong in research preparation and analysis code. The adapters add
no cache, pagination, retry policy, source substitution, or common time-boundary
convention. Such behavior needs an explicit design if introduced later.

## Team access

Sharing this adapter code does not require sharing a provider password. Use
individual access or the provider's supported team mechanism:

| Provider | Team arrangement |
|---|---|
| WRDS | Each eligible researcher uses an individual account. Before sharing a data snapshot, verify access to the specific dataset and the applicable coauthor terms. See [account types](https://wrds-www.wharton.upenn.edu/pages/about/wrds-account-types/) and [coauthor guidance](https://wrds-www.wharton.upenn.edu/pages/about/navigating-co-authorship-across-institutions-a-guide-to-data-sharing-and-compliance/). |
| LSEG Workspace | Use individually licensed Workspace access. Do not turn one user's desktop session into a team server. Central platform access requires the appropriate arrangement; see the [Data Library documentation](https://developers.lseg.com/en/api-catalog/lseg-data-platform/lseg-data-library-for-python/documentation). |
| Databento | Use [Team invitations](https://databento.com/docs/portal/team), appropriate roles, and spending limits instead of circulating the owner's credentials. Follow the [API-key guidance](https://databento.com/docs/portal/api-keys) for application keys. |

Team membership does not by itself establish permission to redistribute every
dataset. A restricted storage folder provides access control, not a new data
license. This project keeps market-data files outside GitHub regardless of
whether a particular dataset permits wider distribution.

## Configure once, open providers as needed

After installing the project, configure access in a script or notebook:

```python
from finance_data import DataAccess, Settings

settings = Settings.from_env()
access = DataAccess(settings)
```

This prepares objects in memory; it does not connect, request a quote, or
download data. Without `env_file`, `Settings.from_env()` reads only the process
environment. To read a private file, pass its path as `env_file`; the file must
exist. Process values override file values; loading does not interpolate
`${...}`, modify `os.environ`, or save
credentials. Missing credentials for one provider do not prevent using another.
However, settings for all three providers are parsed, so an invalid numeric
setting, such as a malformed WRDS port, raises an error during configuration.

| Provider | Settings |
|---|---|
| WRDS | `WRDS_USERNAME`, `WRDS_PASSWORD`; an explicit username can also use an existing PostgreSQL passfile |
| WRDS optional | `WRDS_HOST`, `WRDS_PORT`, `WRDS_DATABASE`, `WRDS_CONNECT_TIMEOUT`, `WRDS_STATEMENT_TIMEOUT_MS`, `WRDS_SSLMODE`, `WRDS_PASSFILE` / `PGPASSFILE` |
| LSEG optional | `LSEG_SESSION_NAME`, `LSEG_APP_KEY`, `LSEG_CONFIG_FILE`; omitted values use the SDK configuration and default session |
| Databento | `DATABENTO_API_KEY`; optional `DATABENTO_GATEWAY` |

Alternatively, construct `WRDSConfig`, `LSEGConfig`, or `DatabentoConfig` and
pass it to the corresponding adapter. Sensitive fields are excluded from the
configuration object's `repr`, but the object still holds real credentials.
Do not serialize it into reports or shared logs.

## WRDS

The following functions illustrate the interface. Research code supplies the
SQL and parameters; defining a function does not issue a query.

```python
def read_wrds(sql, params=None, **options):
    with access.wrds as source:
        return source.query(sql, params=params, **options)
```

SQL strings use psycopg2 parameter syntax: `%s` or `%(name)s`. SQLAlchemy
`text()` statements use `:name`. Pass values separately through `params` rather
than inserting them into SQL strings. Additional options go to
`pandas.read_sql_query`; use pandas names such as `parse_dates`, not WRDS SDK
names such as `date_cols`. The result is a DataFrame.

`source.call("query", sql, params=params, **options)` is equivalent to
`source.query(...)`. For chunks, use `iter_query` rather than passing `chunksize`
to `query`. SQL executes when iteration begins, and the connection must remain
open throughout iteration. `contextlib.closing` also closes the iterator when
the consumer stops early:

```python
from contextlib import closing

def process_wrds_chunks(sql, params, consume, chunksize):
    with access.wrds as source:
        with closing(source.iter_query(sql, params=params, chunksize=chunksize)) as chunks:
            for frame in chunks:
                consume(frame)
```

Chunk size limits rows per DataFrame, not total rows, and does not guarantee that
the database driver avoids buffering the full result. Connections created by
the adapter default to read-only access, SSL `require`, AUTOCOMMIT, and a
45-second connection timeout. A statement timeout is applied when configured.
Borrowed connections retain the caller's transaction policy; the caller also
handles rollback after a failed transaction.

The adapter connects through SQLAlchemy and psycopg2. It does not invoke
`wrds.Connection.connect()`, prompt for credentials after failure, or create or
modify a PostgreSQL authentication file.

## LSEG

```python
def read_lseg_history(request):
    with access.lseg as source:
        return source.get_history(**request)

def read_lseg_fields(request):
    with access.lseg as source:
        return source.get_data(**request)

def read_lseg_content(definition):
    with access.lseg as source:
        return source.request(definition)
```

`request` is a caller-supplied argument dictionary. A content/delivery
`definition` must support `get_data(session=...)`; the adapter supplies its
session and preserves the native response and metadata. Synchronous access-layer
methods under `news`, `discovery`, `dates_and_calendars`, and `tradefeedr` can be
called through public paths, for example
`source.call("news.get_headlines", **request)`. Unsupported methods raise an
error rather than falling back to another field or endpoint.

The access layer uses the SDK's process-wide default session. The adapter
serializes these calls and restores an existing default afterward. When there
was no previous default, its session remains the default until the adapter
closes an owned session. In LSEG Data Library 2.1.1, `set_default(None)` closes the
current session, so it cannot safely restore an empty default between requests.
A borrowed session is not closed; if it becomes the first default, it remains
the default after adapter exit and stays under the caller's control.

The lock cannot protect unrelated code that directly changes the SDK default
concurrently. Avoid combining those access patterns. SDK `config_name` and
`app_key` arguments can also change process-wide configuration, which the adapter
does not restore in full.

The wrapper supports synchronous requests. Streaming subscriptions and async
APIs need their own lifecycle and are not wrapped. Desktop sessions require a
logged-in Workspace and a reachable desktop API. Platform sessions use their
own SDK configuration and entitlements. The package does not launch Workspace
or alter host networking.

## Databento

```python
def estimate_databento_cost(request):
    with access.databento as source:
        return source.get_cost(**request)

def read_databento_range(request):
    with access.databento as source:
        return source.get_range(**request)
```

`get_range` returns the SDK's `DBNStore` without converting it to a DataFrame.
`call()` forwards public methods and their arguments under `metadata`,
`symbology`, `timeseries`, and `batch`, for example
`source.call("symbology.resolve", **request)`.

Cost estimation, `submit_job(**request)`, and `download(job_id, **options)` are
separate explicit operations. A quote does not trigger a download; submission
does not poll or download; downloading an existing job does not submit a new
one. The adapter imposes no dataset, date, row-count, or spending limit. The
caller must establish the request scope and acceptable cost before requesting
data. SDK defaults and retries still apply.

This adapter uses the Historical SDK. A Live client would need a separate
adapter and lifecycle.

## Resources and errors

- Enter `with adapter:` or call `open()` before using a provider. Repeated
  `close()` calls are safe.
- The adapter closes connections that it or `client_factory` creates. LSEG
  also avoids taking ownership when its SDK returns the existing default session.
- A native connection supplied as `client=...` is borrowed and is not closed.
- `DataAccess.close()` attempts cleanup for all three adapters.
  `with DataAccess(...)` provides cleanup without opening every provider.
- Direct use of `client` bypasses operation dispatch and error wrapping.
- Databento 0.87.0's Historical client has no public `close()` method.
  The adapter releases its reference rather than using private SDK cleanup
  methods; an injected client with a public `close()` is closed normally.
- `ConfigurationError` and `UnsupportedOperationError` identify configuration
  or interface-use problems. Provider exceptions are wrapped in `DataAccessError`
  with a default message that omits SQL, request parameters, and credentials.
  `original_error` is available for explicit debugging and must not be copied
  unexamined into shared logs.

## Verification

Run the test command in the [README](../README.md) using the selected project
environment.

These standard-library `unittest` tests use substitute clients; pytest is not
required. They check configuration, lifecycle, and dispatch, not real login,
data entitlements, returned records, or extraction at scale.

For a live check, record the date, provider, request bounds, estimated cost when
applicable, and observed response. A successful request establishes access only
to that request's data under that account and setup. It does not establish
broader coverage or extraction performance. Keep these observations with the
relevant task or experiment rather than treating them as an API guarantee.
