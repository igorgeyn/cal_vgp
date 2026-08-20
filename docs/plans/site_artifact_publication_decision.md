# Decision memo: generated site artifact publication

> Decision date: 2026-08-16  
> Decision: **Option 2 — keep generating the local mirror, but stop tracking it.**

## Recommendation

Track and publish only the deployed root pair, `index.html` and
`measures-data.json`. Continue generating the byte-identical local pair under
`scraper/`, but gitignore both `scraper/index.html` and
`scraper/measures-data.json` and remove the existing mirror HTML from the Git
index. Do not regenerate any site artifact as part of this policy change.

Option 2 is the smallest safe change while the registrar pipeline is still being
built. It prevents a redundant ~41 MB pair from entering every publication commit,
preserves the existing `make website` / `make website-preview` workflow, and does not
change the live GitHub Pages source. Option 4 is directionally better for a mature,
automated publishing pipeline, but it should be a separately gated deployment
migration—not an incidental response to the next regeneration.

## Evidence and corrected size diagnosis

The working tree artifacts are approximately 6.0 MB root HTML, 34.9 MB root JSON,
and 40.9 MB legacy mirror HTML. Git history has 111 commits that touch at least one
of the three site artifact paths, so continuing to commit a second identical pair is
pure duplication.

The reported 1.6 GB `.git` size is real locally but is not the current remote-history
size. `git count-objects -vH` reports 1.46 GiB of loose objects and only 92.28 MiB of
packs. Almost all of the loose size is one 1,509,515,057-byte
`data/cal-access-data-download-041326.zip` blob retained by a local
`refs/codex/turn-diffs/...` capture of an untracked file. It is not tracked on `main`,
and local `main` exactly matches `origin/main`. A fresh clone will not receive that
Codex-only ref. This is a local capture-cleanup issue, not evidence that the remote
repository has already crossed 1 GB.

The generated files are also below GitHub's current regular-Git thresholds: GitHub
warns above 50 MiB and blocks above 100 MiB. GitHub recommends repositories remain
ideally below 1 GB and strongly below 5 GB; Pages recommends a source repository and
published site below 1 GB, with a 10-minute deployment timeout. The current ~41 MB
site is comfortably inside those limits. Sources:

- <https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github>
- <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>

This means option 2 is sufficient now. It does not mean committing generated data
forever is free: root JSON will still create recurring history, clone, checkout, and
review cost as publication becomes more frequent.

## Contract and documentation changes

The dual-write rule survives as a **generation invariant**, not a publication rule:

- root HTML and JSON are the tracked deployment pair;
- scraper HTML and JSON are ignored local-preview outputs;
- one generator call must still produce byte-identical pairs; and
- the contract test remains valuable because Git tracking has no bearing on whether
  the two generated previews agree.

`CLAUDE.md` and `LESSONS_LEARNED.md` are reworded accordingly. The Makefile continues
to advertise the mirror but identifies it as untracked. No generator or contract-test
change is required.

The manual weekly workflow has a separate latent publication bug: after generating
the split site, it checks and stages root `index.html` and the database but omits root
`measures-data.json`. That could deploy a new shell with stale data. Option 2 updates
both the change gate and explicit `git add` list to include the root JSON. The ignored
mirror is never staged.

## First regeneration

The policy/index change should be reviewed and committed separately from generated
content. On the later first regeneration:

1. generate from the approved database through the normal command;
2. expect tracked diffs only in root `index.html`, root `measures-data.json`, and any
   separately generated tracked analysis payloads;
3. expect `scraper/index.html` and `scraper/measures-data.json` to exist locally but
   not appear in `git status`;
4. review the root JSON as a large release artifact because it is six weeks stale;
5. verify HTML/JSON counts and hashes, serve the root over HTTP, and commit the
   reviewed root pair explicitly.

The staged removal of `scraper/index.html` in this policy change is not evidence of a
site-content change; its bytes remain on disk in the implementing clone. No site
artifact is regenerated or committed here.

## Rejected options

### Option 1 — commit the mirror

Rejected. It stores and reviews a second byte-identical ~41 MB bundle with no
programmatic consumer. The contract test supplies the consistency guarantee without
requiring Git to retain both copies.

### Option 3 — remove the mirror

Rejected for now. It is cleaner than option 2 in the abstract, but the local preview
path is established and cheap once ignored. Removing it would create documentation
and habit churn during the county-scraper arc without reducing Git history beyond
option 2.

### Option 4 — build and deploy only from CI

Deferred, not rejected. GitHub officially supports uploading a Pages artifact and
deploying it with `actions/upload-pages-artifact` and `actions/deploy-pages`; standard
GitHub-hosted runners are free for public repositories. This is the appropriate
long-term model once publication is automated:

- <https://github.com/actions/upload-pages-artifact>
- <https://github.com/actions/deploy-pages>
- <https://docs.github.com/en/billing/concepts/product-billing/github-actions>

It is not a zero-risk toggle here. A CI build must define the complete publish set
(generated pair, `CNAME`, favicon/static assets, blog and other root-served files),
pin the exact database/input revision, preserve a reviewable manifest of input and
output hashes, configure Pages permissions/environment protection, and prove custom
domain behavior before switching Pages away from branch publication.

Revisit option 4 when any of these occurs: the weekly workflow is enabled for
automatic deployment, the root JSON approaches GitHub's 50 MiB warning threshold,
reachable packed repository history approaches 500 MiB, or the five-county launch
work is complete. Pilot it first as a manual non-deploying build artifact; compare it
byte-for-byte with an approved local build; then perform a separately approved Pages
source switch with branch publication retained as rollback.

## Exact implementation and existing-clone impact

1. Add `/scraper/index.html` and `/scraper/measures-data.json` to root `.gitignore`.
2. Run `git rm --cached -- scraper/index.html`; do not delete the working-tree file.
3. Reword the hard rule and lesson; update Makefile output descriptions.
4. Add root `measures-data.json` to the weekly workflow's diff gate and explicit
   staging list.
5. Run the 182 registrar/site-contract tests and verify all three existing artifact
   hashes are unchanged.

When the eventual policy commit is pulled, Git will remove the formerly tracked
`scraper/index.html` from existing clean clones. That is the one visible break. Run
`make website` (or `make website-preview`, which depends on it) to recreate the
ignored mirror. New clones likewise have no mirror until generation. A locally
modified tracked mirror may cause the pull to stop for conflict resolution; preserve
or discard that local generated file, pull, then regenerate.

## Rollback

Before the policy commit, restore the index with
`git restore --staged scraper/index.html` and remove the two ignore lines. After the
policy commit, revert that commit; this restores the prior tracked mirror. If rollback
happens after a later regeneration, explicitly force-add the regenerated split-format
mirror pair instead of restoring the obsolete embedded-data HTML.

## History cleanup

Do not rewrite published history for site artifacts now. It is disruptive to every
clone and open branch, while packed reachable history is currently modest. Also do
not use a history rewrite to fix the local 1.6 GB spike: that blob is attached to a
local Codex capture ref, not `main`. Diagnose/remove the capture ref and run ordinary
Git maintenance—or simply use a fresh clone—as a separate, explicitly approved local
cleanup. Reassess a coordinated `git filter-repo` migration only if reachable remote
history later becomes materially large and collaborators can all reclone.
