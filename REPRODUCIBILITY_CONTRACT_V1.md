# REPRODUCIBILITY_CONTRACT_V1

## Guarantees

Level 1: the canonical daily entry point imports and `./daily --help` succeeds
in a clean checkout after bootstrap. No credentials, datasets or ledgers required.

Level 2: the default `tests/` suite is offline and uses temporary state and small
versioned fixtures. Production/archive tests are explicitly marked `archive` and
excluded by default. The unrelated R002 experimental suite is not part of the
canonical Level 2 guarantee (it accounted for eight tests in the old workspace total).

Levels 3 (current public research) and 4 (exact historical replay) are NOT certified
by this contract's Level 1/2 validation. They require separately restored market
and evidence archives. Never present missing history as completed research.

## Bootstrap (POSIX, CPython 3.12)

    ./bootstrap-research
    .venv-research/bin/python -m pip check
    ./daily --help
    PYTHONDONTWRITEBYTECODE=1 .venv-research/bin/python -m pytest -q

`requirements-research.lock` pins the complete research/test package set. Bootstrap
requires access to the package index (or an operator-provided verified wheelhouse).
`RESEARCH_BOOTSTRAP_PYTHON` selects CPython 3.12; `RESEARCH_VENV` selects installation
location. `RESEARCH_PYTHON` selects the interpreter used by `daily`. Existing gateway
installations are not a dependency of the research checkout. Package files and
virtual environments are never committed. Public production acquisition additionally
requires the external `kraken` OHLC CLI; it is NOT required for Levels 1 or 2.

## Prospective identity

`RESEARCH_SEMANTICS_V1` replaces whole-workspace hashing only for new observations.
It hashes canonical paper parameters, reviewed signal definitions and selected
signal logic (including module-local helper/constant closure), effective universe
and freshness rules, schema and the existing PARENT_SETUP_V2 event contract.
`config/reproducibility_contract_v1.json` declares the exact reviewed boundary.
Code AST verification ignores comments/formatting/docstrings and fails closed if
reviewed logic or definitions change without a manifest review. Editing the
manifest is a research-contract change, not an automatic optimization.

The source release owns these definitions; a runner's alternate data root does not
silently replace executable research semantics. Runtime environment overrides that
affect the declared universe/freshness rules are included as effective values.
Unrelated scripts/configs, reports, absolute checkout paths, clock time, databases,
MFE/MAE, BTC enrichment and other maturing outcomes are excluded from signal identity.
The measurement contract has its own digest and is recorded in the run manifest.
No prior signal IDs, configuration hashes, completed asset evidence or frozen
forward records are migrated, rewritten, relabelled or deleted. Existing historical
replay requires the original software/manifest; this release does not impersonate
an earlier signature. Future observations remain correlated across version changes.

## Source versus evidence

Git versions source, definitions, tests, fixtures and this bootstrap contract.
Market datasets, private portfolios, mutable databases, activation state, observation
journals, caches and logs remain external. Removing already tracked runtime files
from the index does not delete local bytes or rewrite Git history. Existing Git
history may still contain earlier state and is NOT a public-data sanitization proof.

Archive snapshots must identify schema, SHA-256, source, coverage/gaps, UTC candle
semantics, original available-as-of times and parent/correction lineage. Preserve
raw bytes for immutable evidence, especially the eight frozen forward outcomes.
Use SQLite backup/snapshot facilities; do not copy an actively changing database
without consistency controls. Version schema/migration code, not live database files.
No destructive migration or archival deletion is performed by this implementation.

To opt into archive integration checks, restore verified archives in an isolated
checkout under their canonical relative paths, then run:

    PYTHONDONTWRITEBYTECODE=1 .venv-research/bin/python -m pytest -q -m archive

Required evidence includes the V2 ledger and its asset/BTC hourly windows, tactical
history, paper database, frozen-forward database and original manifests. Missing
archives are failures, not a passing Level 2 result or a reason to fabricate history.
Archive execution remains offline. Complete logical replay additionally needs the
original pre-run state, code/runtime versions, cutoff, availability timeline and
public quote/universe snapshots. These archives are not bundled with this release.

## Safety

Trading remains DISABLED; strategy targets, stops, thresholds and risk rules remain
unchanged. Tests block live socket connections. Public production research must use
public/read-only endpoints. Credentials, secrets, tokens and private portfolio state
must never be supplied to the public bootstrap or committed as fixtures.
