# CalBallot private recovery bundle

This is a prepared release candidate, not evidence of publication. Keep this
archive in the existing private registrar R2 bucket under `recovery/`. Do not
serve this directory or archive from GitHub Pages.

Verified October 3, 2026, 23:16 Pacific: private bucket
`cal-vgp-registrar-raw`, object
`recovery/20261003-part2/f0e016922367350b466bbe1ec2f8cd6c29edff06c5f432e1e28c40151df322c9/calballot-recovery.zip`.
Size: 907,462,456 bytes. Expected SHA-256:
`f0e016922367350b466bbe1ec2f8cd6c29edff06c5f432e1e28c40151df322c9`.
An independent download matched this digest after the local restore/rebuild.

## Contents and ownership

- `workspace/`: frozen source, reviewed statewide input and source evidence,
  corrected measures database, both finance databases, embeddings/metadata,
  Insights, local all-MiniLM-L6-v2 model, static assets, and input hash manifest.
- `baseline/`: consistent backup of the pre-release measures database and an
  exact copy of the currently published local site files, plus their manifest.
  The baseline intentionally preserves the existing missing San Mateo pages.
- `candidate-final/`: complete corrected site and database, build log and hashes.
- `county-archives/`: all 15 existing production snapshots through September 28,
  including source pages, PDFs, and original manifests, indexed by SHA-256 so
  repeated artifacts are stored once. They preserve the
  parser's identity lineage; these are private evidence, not public PDF copies.
- `evidence/`: county comparison, current statewide check, document link health,
  preservation and browser reports, tests, and preparation helpers.
- `environment.json`: Python/package versions and the local model revision.
  Credentials are deliberately absent. The workspace `.env` is comments only.

Registrar identity, alias, scope and document state are in the measures
database, not an unrecorded external registry. Finance crosswalks are in the
finance databases. Preserve these files together: integer IDs are join keys.
Full CAL-ACCESS ingestion dumps are unnecessary for restoring this accepted
state; rebuilding the finance ingestion from raw downloads is outside this test.

## Restore and rebuild

Obtain the archive and its expected SHA-256 from the versioned Part 2 evidence
and private R2 receipt. Use a fresh destination on a machine with Python 3.13:

```powershell
python scraper/scripts/recovery_bundle.py restore --archive <downloaded.zip> --destination <new-directory> --sha256 <expected-sha256>
python <new-directory>/workspace/scraper/scripts/build_release_bundle.py --output <another-new-directory>
python <new-directory>/workspace/scraper/scripts/verify_release_bundle.py --site-dir <another-new-directory>/site --report <report.json>
```

The restore utility checks the ZIP digest, exact inventory, every file's size
and digest, and refuses existing destinations. The real build uses the bundled
model with Hugging Face offline mode and disables dotenv/provider credentials.
All finance and enrichment paths resolve inside the restored workspace.

The rehearsal uses the laptop's installed Python packages, recorded in
`environment.json`. A fresh OS/package installation is **not** tested. Install
`workspace/scraper/requirements-release.txt` if necessary and compare versions.
External browser libraries, fonts, county links, optional AI chat and R2 access
remain external services; an offline build does not guarantee their availability.

The archived candidate can be restored byte for byte. Rebuilding regenerates
129 legacy null `last_seen_at` export timestamps; SQLite source rows are not
redated. Sitemap `lastmod` follows build day. These are the expected differences
on a later-day rebuild, not permission to ignore other content differences.

To recreate the county source store for a later parser replay, run the bundled
helper against a new destination (no credentials or county requests required):

```powershell
python <new-directory>/materialize_recovery_sources.py --source <new-directory>/county-archives --destination <new-source-store>
```

The helper verifies each unique blob before reconstructing the original
snapshot paths and manifests. No filesystem links or external cache is needed.

The R2 `verification/` sidecars record checks performed **after** the archive
was sealed. Use their final replay report and checker. A dated preparation
script under the archive's `evidence/` used a tuple/list comparison in its first
attempt and is retained as historical evidence; it is not a restore entry point.

## Rollback and release discipline

Do not run any restore command over production. First restore into a new
directory and validate it. Production cutover requires a reviewed release and
an explicit maintenance window with all database/site writers stopped. A hash
check by itself does not exclude a writer that starts after the check.

Before cutover, compare production against the baseline hashes, verify the
candidate manifest, inspect actual SQLite journal/WAL/SHM state, close all
handles, and make a new consistent baseline backup. Never delete sidecars to
make a check pass. If the production inputs drifted, stop and reconcile them.

Publish the entire accepted page bundle as one Git revision, including the
explorer pair, all detail pages, sitemap, use page and static assets. Keep the
scraper mirror pair synchronized. Stage explicit paths and inspect the staged
inventory; this workspace contains unrelated untracked data. Prevent an
unintended registrar capture when pushing the release.

For rollback, preserve the failed state for diagnosis, restore the baseline DB
with its matching public site under the same writer exclusion, and publish a
revert commit rather than rewriting shared Git history. Verify served hashes,
representative pages, #m routes and Finance. No production cutover, rollback or
publication is performed by these recovery scripts.

R2 account access and replacement credentials must be recovered separately
through the user's Cloudflare account/password manager. No public URLs, new
bucket, ACL changes, lifecycle changes, or deletion of older objects are needed.
