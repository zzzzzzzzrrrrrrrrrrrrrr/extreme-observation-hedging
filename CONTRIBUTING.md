# Contributing

## Plan and review

- Open an Issue before a substantial change. Describe its purpose, proposed
  scope, and completion criteria; assign an owner and discuss overlapping work.
  Small corrections can go directly to a PR.
- Use a task branch and a focused PR linked to the Issue when applicable.
  Explain the resulting behavior and how it was checked. Get one teammate's
  approval before merging; address review comments and obtain a new review
  after substantive changes.
- Explain changes to the data sample, statistical methods, or evaluation
  assumptions so reviewers can assess their effect on results.

## Shared documents

- Keep setup in [README.md](README.md), provider usage in
  [docs/data-access.md](docs/data-access.md), and collaboration rules here.
  Update affected documentation in the same PR as the code.
- Change relevant paragraphs without reformatting unrelated text. Coordinate
  before editing overlapping sections or the same notebook; one person should
  integrate concurrent changes to a shared report source.
- Resolve conflicts in the source and check the combined meaning. Regenerate
  affected results and PDFs rather than merging generated output by hand.

## Validation and data

- Follow the setup and test commands in the README. Check behavior affected by
  the change; report separately any live provider requests and their limits.
- Keep data and credentials outside GitHub, including branches and PRs. Use
  authorized access and preserve the input version used for reported results.
- Execute changed analyses from a clean kernel and inspect rendered reports.
  Documentation-only changes do not require a data download or model rerun.
