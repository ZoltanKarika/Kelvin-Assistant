# v1.0 Offline Release Package

This document defines the v1.0 release package that can be reviewed before it is
moved to an offline Kelvin environment.

Use it together with `docs/installation.md`, `docs/api-contract.md`,
`docs/backup-restore.md`, `docs/operational-runbooks.md`, and
`docs/licensing.md`.

---

## 1. Version and Source Baseline

The v1.0 release version is `1.0.0`.

Release metadata to verify:

- `pyproject.toml` has `version = "1.0.0"`.
- `backend/src/kelvin_assistant/version.py` has `APP_VERSION = "1.0.0"`.
- `/version` returns `1.0.0` after deployment.
- `uv.lock` is committed and unchanged during packaging.
- The release branch or tag is recorded in the package manifest.

---

## 2. Required Source Artifacts

Include these repository files in the source package:

- `backend/`
- `docs/`
- `infrastructure/n8n/`
- `scripts/`
- `tests/`
- `.env.example`
- `api-tokens.example.json`
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `LICENSE`
- `NOTICE`
- `THIRD_PARTY_NOTICES.md`

Exclude local runtime and secret-bearing files:

- `.env`
- `api-tokens.json`
- database dumps unless they are an explicitly encrypted backup artifact
- n8n encryption keys
- SMTP passwords
- raw bearer tokens
- user documents and private knowledge imports
- generated `.pytest-*`, `.mypy_cache`, `.ruff_cache`, and virtualenv folders

---

## 3. License Inventory

Before approving an offline bundle:

1. Review `LICENSE` and `NOTICE`.
2. Review `THIRD_PARTY_NOTICES.md` against the direct dependencies in
   `pyproject.toml` and resolved versions in `uv.lock`.
3. Generate a complete transitive SBOM for the exact wheel bundle if the package
   will be redistributed outside the local lab.
4. Include upstream license texts and notices required by that SBOM.
5. Record model license terms separately from the Python package inventory.

Current direct runtime dependency inventory:

| Component | Resolved version | License note |
|---|---:|---|
| FastAPI | 0.138.1 | MIT |
| Pydantic Settings | 2.14.2 | MIT |
| psycopg | 3.3.4 | LGPL-3.0-only with exceptions |
| psycopg-binary | 3.3.4 | LGPL-3.0-only with exceptions |
| Uvicorn | 0.49.0 | BSD-3-Clause |
| HTTPX2 | 2.5.0 | BSD-3-Clause |

Development tools are listed in `THIRD_PARTY_NOTICES.md`.

---

## 4. Offline Dependency Bundle

Prepare the Python dependency bundle in an internet-connected staging
environment that matches the target Python major/minor version.

Recommended artifact layout:

```text
release/
  kelvin-assistant-1.0.0/
  wheels/
  models/
  manifests/
    source-files.sha256
    wheels.sha256
    models.sha256
    package-notes.md
```

Build or download wheel artifacts:

```powershell
uv sync --locked --all-groups
uv build
uv export --locked --all-groups --format requirements-txt --output-file requirements.lock.txt
python -m pip download --requirement requirements.lock.txt --dest release/wheels
```

If a command is unavailable in the installed `uv` version, use the equivalent
locked `uv pip compile` or `pip download` workflow and record the exact command
in `release/manifests/package-notes.md`.

Create checksums:

```powershell
Get-ChildItem release -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\manifests\\' } |
  Get-FileHash -Algorithm SHA256 |
  Sort-Object Path |
  ForEach-Object { "$($_.Hash.ToLowerInvariant())  $($_.Path)" } |
  Set-Content release/manifests/source-files.sha256
```

On Linux:

```bash
find release -type f ! -path '*/manifests/*' -print0 \
  | sort -z \
  | xargs -0 sha256sum > release/manifests/source-files.sha256
```

---

## 5. Required Local Model Assets

The source repository does not include model weights. For v1.0 verification,
record the model assets used by the target environment:

- chat/planner model from `KELVIN_OLLAMA_MODEL`
- embedding model from `KELVIN_OLLAMA_EMBEDDING_MODEL`
- any optional model used by n8n workflows

For each model asset, record:

- model name and tag
- provider or source URL used in the staging environment
- license or terms link
- local file or Ollama artifact identifier
- SHA-256 checksum where available
- date downloaded
- operator who approved the model for offline use

Do not package model assets unless their terms allow the intended transfer and
use.

---

## 6. Offline Verification Procedure

After moving the package into the offline environment:

1. Verify every checksum manifest.
2. Install Python dependencies from the local wheel folder only.
3. Confirm `uv.lock` and `pyproject.toml` match the release package.
4. Configure `.env` from `.env.example`.
5. Configure hashed API tokens from `api-tokens.example.json`.
6. Start the service.
7. Verify `/health`, `/status`, `/ready`, `/ready/database`, and `/version`.
8. Verify `/version` returns `1.0.0`.
9. Open `/ui`, `/ui/runs`, `/ui/approvals`, `/ui/audit`, `/ui/settings`, and
   `/ui/n8n`.
10. Run the backup and restore verification from `docs/backup-restore.md`.
11. Run the operational evidence checklist from `docs/operational-runbooks.md`.

Step 9 of the v1.0 plan records the final end-to-end verification evidence.

---

## 7. Post-v1.0 Follow-up Candidates

- Produce a full generated SBOM artifact in CI.
- Promote or retire the containerization test path.
- Standardize operator-facing language across all docs.
- Remove remaining upstream deprecation warnings from the final test output.
- Add an explicit offline model mirror process if model redistribution is
  approved.
- Add a signed release manifest after the package format stabilizes.
