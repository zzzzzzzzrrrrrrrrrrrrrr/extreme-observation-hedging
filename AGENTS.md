# Repository instructions

This project studies **When Should Extreme Observations Change a Hedge?**
Preserve the research question; candidate models may evolve.

Use [README.md](README.md) for setup, [CONTRIBUTING.md](CONTRIBUTING.md) for
collaboration, and [data access](docs/data-access.md) for provider behavior.
Keep each topic in its designated document rather than repeating it here.

## Working conventions

- Write project prose, comments, and reports in English. Preserve provider
  identifiers and bibliographic titles.
- Use the contributor's selected environment and the Python compatibility
  declared in `pyproject.toml`. Do not replace an environment or change
  dependencies as an incidental part of another task.
- Keep machine paths, operating-system preferences, account configuration,
  and development status out of shared instructions.
- Preserve other contributors' edits and follow the review process in
  `CONTRIBUTING.md`.

## Code boundaries

- `src/finance_data/` handles configuration, connections, and provider requests.
  Instrument selection, cleaning, return definitions, and models belong in
  `src/hedging/`.
- Notebooks organize experiments and explain results using reusable modules.
  Keep one executable source per report; rendered files belong in ignored
  `reports/`.
- Use the existing path helpers and `pathlib`. Do not hard-code a contributor's
  home directory, modify `sys.path`, or depend on files outside the checkout
  except explicitly configured private inputs.
- Imports must not connect, download, submit jobs, or write research outputs.
  Add abstractions when actual implementations need them.
- When an interface changes, update its callers, documentation, and relevant
  tests together.

## Research integrity

- Explain changes to the universe, sample dates, adjustments, missing-data
  policy, extreme-observation definition, hedge timing, or evaluation criteria.
- Use only information available at the decision time. Separate estimation and
  tuning from final evaluation; report unfavorable and null results as well.
- Account for time dependence and shared market shocks when estimating
  uncertainty. Do not alter the test sample to obtain a preferred result.
- Preserve raw inputs. Identify the data version, parameters, seed when used,
  and code revision for reported experiments; do not overwrite their inputs.
- Generate reported numbers and figures from code and keep interpretations
  beside the supporting evidence. Read the relevant paper before relying on it.

## Data and verification

- Keep credentials out of outputs and logs. Do not commit raw licensed records,
  including records embedded in notebooks or reports. Use authorized access and
  explicit request bounds; paid operations require an agreed cost limit.
- Do not share open provider clients or concurrently write the same output.
  Follow the lifecycle and concurrency limits in the data-access documentation.
- Run checks appropriate to the change. Local interface tests establish local
  behavior; claims about live access require an actual request and its scope.
- For changed research results, execute the source from a clean kernel, render
  the report, and inspect it. Documentation-only edits need no market download.

## Review priorities

Flag information leakage, silent changes to research definitions, overwritten
inputs, unsupported results, credential exposure, and unexpected paid requests.
Prefer concrete corrections over speculative frameworks or formatting changes.
