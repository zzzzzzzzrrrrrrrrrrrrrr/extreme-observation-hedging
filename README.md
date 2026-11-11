# When Should Extreme Observations Change a Hedge?

This project studies when an extreme stock return should change a stock–SPY
hedge, and the losses from reacting too much or too little.

## Layout and current implementation

```text
src/finance_data/   Provider configuration, connections, and requests
src/hedging/        Research code; currently path utilities
tests/             Interface and path checks
docs/data-access.md Provider usage and limitations
data/              Local inputs and prepared data; ignored by Git
```

Provider adapters and path utilities are implemented. Research data preparation,
hedge models, simulation, and evaluation remain to be implemented. Add those
modules as the work proceeds. This directory is the repository root: its
contents, including `src/` and this README, appear directly on GitHub. Add
`notebooks/` for research experiments and `reports/` for local rendered output
when needed. Personal submissions and their sources stay outside the checkout.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the team workflow and
[AGENTS.md](AGENTS.md) for coding-agent instructions.

## Installation

The shared default interpreter version is Python 3.12.14, recorded in
`.python-version`. Select and activate the intended environment; its location
is a contributor's choice. Confirm its executable and version before installing.
From the repository root:

```bash
python -c "import sys; print(sys.executable); print(sys.version)"
uv pip install --python python --editable '.[research,report]'
python -B -m unittest discover -s tests -v
```

These commands use uv's pip interface with an explicitly selected interpreter.
An absolute executable path can replace `python` after `--python`.
`pyproject.toml` permits Python 3.12.x; `.python-version` supplies the default
version request for tools that read it. The file does not select an environment
directory or override an explicitly chosen interpreter.
`uv run` and `uv sync` use a separate project-environment workflow and are not
substitutes for these commands.

`pyproject.toml` declares project dependencies and Python compatibility.
`requirements.txt` is an optional pinned snapshot of a validated Python 3.12.14
Linux environment, including additional workspace tools. To use that snapshot
instead, replace the installation command with:

```bash
uv pip install --python python -r requirements.txt
uv pip install --python python --no-deps --editable .
```

If the selected environment already contains the required dependencies, only
the second command is needed to register the checkout. Editable installation
makes `finance_data` and `hedging` importable without notebook path edits.
Select the same interpreter as the notebook kernel. Windows and macOS have not
been tested end to end.

## Data and credentials

Use `hedging.paths.project_root()` and `hedging.paths.data_root()` to locate
the checkout and data. An absolute `HEDGE_DATA_DIR` process variable can select
an external data directory. These helpers do not create directories or download
anything.

`.env.example` lists settings without credentials. Load process settings with
`Settings.from_env()`, or pass an explicit private file to
`Settings.from_env(env_file=...)`. No credential file is discovered implicitly.
See [data access](docs/data-access.md) for examples and provider limitations.

Keep raw inputs and prepared tables separately under `data/` or the configured
external directory. Data and credentials are excluded from the public
repository. A clone needs its own authorized inputs and access configuration.

## Research reports

Keep shared analysis sources in `notebooks/` and generate reports from those
sources with Quarto, installed separately. Set `QUARTO_PYTHON` if needed to
select the same interpreter as the notebook kernel. Choose fonts available on
the rendering machine. See [Quarto's notebook workflow](https://quarto.org/docs/computations/python.html#workflow).

Rendered outputs in `reports/` are ignored by Git. Keep individual submissions
and private working files outside the checkout or in a local exclude list;
shared ignore rules describe file categories used by the team.
