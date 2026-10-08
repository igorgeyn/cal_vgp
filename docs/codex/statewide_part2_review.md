# Claude review prompt: complete statewide/county release and recovery

Review the current CalBallot Part 1 corrections plus Part 2 release preparation.
Work read-only. Do not run scrapers, load production, publish, modify fixtures,
weaken checks, or upload anything. Be skeptical of both the implementation and
my reports. A prior model's conclusion is evidence to examine, not authority.

Start with:

1. `docs/plans/statewide_part2_20261003.md`
2. `docs/plans/statewide_part2_evidence_20261003.json`
3. `docs/plans/statewide_part2_recovery_20261003.md`
4. `docs/plans/statewide_corrections_20261003.md` and the pinned review/approval
5. `docs/plans/six_part_delivery_plan_20260913.md`, Part 2

The candidate and detailed evidence are in
`scraper/data/statewide_recon/20261003_part2/`; final public files are in
`capsule/candidate-final/site/`. The production files remain unchanged. There
are unrelated dirty/untracked files; distinguish this batch from other work.

Trace the implementation and actual output. Concentrate on:

- Correct statewide identities, preserved IDs and historical data, the 14
  reviewed November propositions, and the searchable withdrawn ACA 13.
- Same accepted data across main HTML/JSON, every detail page and sitemap.
  Exact page membership, county document roles/grouping, safe URLs, capture
  wording, mobile layout, keyboard focus and stable explorer routes.
- Strict build behavior: a failed required enrichment must stop publication;
  legitimate absent context must not be treated as failure. Verify the real
  finance/model inputs were used and providers were not silently substituted.
- The September 28 county replay/no-change decision, October statewide check,
  and distinction between a bounded live PDF health probe and complete current
  PDF content verification. No new capture should be implied.
- Recovery completeness: baseline plus candidate, identity/scope/document
  state, finance joins, local model, exact source versions and environment.
  Follow the archive hash, file manifest, restore/rebuild report and private R2
  upload/download receipt. Assess what remains laptop-dependent. Do not expose
  credentials or request public access to the private bucket.
- Production cutover: writer exclusion, preconditions, SQLite sidecars, matching
  DB/site rollback, explicit staging and served-site checks. These are pending
  gates; an offline restore does not prove a live deployment is safe by itself.

For each finding, give severity, exact file/line or artifact, a concrete failure
scenario, supporting evidence, and the smallest sufficient correction. Identify
which findings truly block this release. Do not turn unrelated historical
cleanup or card redesign into an October 5 blocker without a reader-impact case.
If you disagree with a prior criticism or with the release premise, explain why.

End with READY FOR PUBLICATION REVIEW, READY WITH CONDITIONS, or NOT READY.
Recommend the next 3-5 actions in order, accounting for approximately 10 Igor
hours/week plus substantial agent time. Say explicitly which assertions you
independently verified, which rely on recorded evidence, and what remains
untested. Do not infer that a release has already been approved or published.
