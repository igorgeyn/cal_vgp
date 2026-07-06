# Cloudflare R2 setup for the registrar pipeline

> One-time walkthrough for provisioning the R2 bucket + credentials
> that the registrar pipeline writes raw artifacts to. ~15 minutes.
> Design context: [`docs/plans/registrar_pipeline_infra.md`](../plans/registrar_pipeline_infra.md).
>
> Until this is done, the pipeline (local + CI) falls back to
> `LocalArtifactStore` automatically — nothing is blocked except
> durable cloud storage itself.

## 1. Create the Cloudflare account (if needed)

1. Sign up at <https://dash.cloudflare.com/sign-up> (free plan).
2. R2 requires a payment card on file, but the free tier covers
   this project comfortably: 10 GB storage, 1M class-A (write) and
   10M class-B (read) operations per month. Weekly scrapes of 5
   counties are a rounding error against that. **No egress fees**
   (the reason we chose R2 over S3).

## 2. Create the bucket

1. Dashboard → **R2 Object Storage** → **Create bucket**.
2. Name: `cal-vgp-registrar-raw` (exactly — the workflow hardcodes it).
3. Location: **Automatic** (or Western North America hint if offered).
4. Leave everything else default. **Do not** enable public access —
   the bucket stays private; registrar PDFs can carry candidate
   statements and signer details, so no public object URLs, ever.

## 3. Create the API token

1. R2 overview page → **Manage R2 API Tokens** → **Create API token**.
2. Name: `cal-vgp-registrar-pipeline`.
3. Permissions: **Object Read & Write**, scoped to **only** the
   `cal-vgp-registrar-raw` bucket (not account-wide).
4. TTL: no expiry (or set a yearly reminder if you prefer rotation).
5. Create, then copy the three values shown **once**:
   - **Access Key ID**
   - **Secret Access Key**
   - The S3 endpoint, shaped like
     `https://<account_id>.r2.cloudflarestorage.com`

## 4. Add GitHub repo secrets

Repo → **Settings → Secrets and variables → Actions → New repository
secret**, three times:

| Secret name | Value |
|---|---|
| `R2_ACCESS_KEY_ID` | Access Key ID from step 3 |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key from step 3 |
| `R2_ENDPOINT_URL` | the `https://<account_id>.r2.cloudflarestorage.com` endpoint |

`R2_BUCKET` and `R2_ENV` are not secrets — the workflow sets them
inline (`.github/workflows/registrar_pipeline.yml`).

## 5. Local dev (optional)

To write to R2 from your machine instead of the local store, set the
same four env vars in your shell (PowerShell):

```powershell
$env:R2_ACCESS_KEY_ID = "..."
$env:R2_SECRET_ACCESS_KEY = "..."
$env:R2_ENDPOINT_URL = "https://<account_id>.r2.cloudflarestorage.com"
$env:R2_BUCKET = "cal-vgp-registrar-raw"
```

Unset them to fall back to `LocalArtifactStore`
(`scraper/data/registrar_raw/`). Day-to-day dev should stay local;
R2 is for CI/prod.

## 6. Verify

Once the secrets exist **and** `R2ArtifactStore` is implemented
(Phase 0.5 deliverable #5 — `make_store()` currently raises
`NotImplementedError` when the R2 vars are set, by design):

1. GitHub → Actions → **registrar-pipeline** → **Run workflow**.
2. Green run; download the `run-manifest` artifact and check
   `totals.counties_failed == 0`.
3. Cloudflare dashboard → the bucket should show objects under
   `prod/noop/2026-01-01/<snapshot_id>/` (manifest.json, page.html,
   analysis.pdf).

## Ground rules (from the plan doc)

- **One bucket**, prefix-per-env: `prod/` for cron + manual runs,
  `dev/` for push-triggered test runs.
- **Snapshots are immutable.** Re-scrapes create new `snapshot_id`
  folders; nothing overwrites in place.
- **Retention:** keep everything; R2 is cheap and the audit value is
  high. Revisit a cold-archive policy in Phase 3+.
- **Never** put the token values anywhere but GH secrets + your
  local shell env. Not in code, not in docs, not in commit messages.
