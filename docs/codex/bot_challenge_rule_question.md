# Codex question: should a bot challenge hide a manually confirmed results link?

**Type:** a short design ruling. Change no code.
**Branch:** `phase0-election-status` at or after `f122cf05`.
**Context:** your P0.1 review (R3) established a rule: the newest check decides whether a
results link shows, and if a success and a failure have the same time, the failure wins.
See `_public_results_link` in `scraper/src/website/election_status.py`.

## The problem

- The SOS results page (`https://electionresults.sos.ca.gov/returns/ballot-measures`) gets an
  Incapsula bot challenge every time our script checks it. The page returns HTTP 200 with a
  challenge body. `check_official_results_links.py` records this as
  `ok: false, reason: "bot_challenge"`.
- On November 11 Igor opened the page in a normal browser, saw the November 3, 2026
  returns, and recorded a `manual_check`. See `scraper/src/website/data/official_results_links.json`
  and commit `f122cf05`.
- P0.3 plans to rerun the checker to record how fresh each link is. That run will write a
  newer `bot_challenge` failure, and the statewide link will disappear until someone checks
  it by hand again.

## Proposal

Treat `reason == "bot_challenge"` as **inconclusive**: it says nothing about the page, only
about our script. An inconclusive check is recorded, but it doesn't take part in "newest
check decides". The link shows if the newest *conclusive* check succeeded.

Real failures still hide the link: a status other than 200, missing expected text, an
exception or a redirect elsewhere.

Possible additions:
- A manual success older than N days, with only inconclusive checks since, could stop
  counting. Is a freshness limit needed?
- The release evidence could list links whose newest conclusive check is manual.

## Questions

1. Is the proposal sound, or does it reopen a risk R3 closed?
2. Should a manual check expire? If so, after how long, and does it matter after
   certification (state deadline December 11)?
3. Are any other reasons inconclusive, such as a timeout or a 429?
4. What should tests pin?

## Please return

Append your ruling to this file under a "Ruling" heading, and commit only this file.
Keep it short.

## Ruling

**November 12, 2026 — approve with conditions.** A positively identified bot challenge
is inconclusive about the underlying results page. It must not count as success or
refresh the successful-check date. No challenge bypass is needed or authorized.

1. **Preserve R3's guarantees.** Select the newest *conclusive* check, comparing
   timezone-aware instants; a conclusive failure wins a tie. No conclusive success means
   no link. Retain the latest conclusive automated observation separately from the latest
   attempt, or retain check history. Merely filtering out `last_check.reason ==
   "bot_challenge"` is unsafe: the checker overwrites `last_check`
   (`check_official_results_links.py:72`). A manual success, then a real automated failure,
   then a challenge could otherwise resurrect the disqualified manual success. Bind
   evidence to the reviewed URL, election and expected content; changes require fresh
   verification rather than inheriting an old success.

   Limit this exception to a recognized challenge response with **HTTP 200 at the
   reviewed destination**. Status and destination failures take precedence. The current
   code needs adjustment before adopting this rule: challenge detection precedes the
   status test (`:55`), and redirects are followed without checking the final destination.
   Offline probes with HTTP fully mocked reproduced a 403 classified as `bot_challenge`
   and an unrelated destination accepted when it contained the expected text. Require
   an exact reviewed destination or explicitly reviewed redirect allowance; an arbitrary
   same-host destination is not enough. Missing expected text in an ordinary page remains
   a failure; only the positively identified challenge body gets the exception.

2. **No automatic N-day expiry for this navigation link.** Its check establishes that
   the page served this election, not that CalBallot's vote totals are fresh. An arbitrary
   expiry would recreate the disappearance without new evidence of a broken link.
   Export the actual successful conclusive timestamp, never the challenge's timestamp.
   Release evidence should show the last attempt/reason, last conclusive result, whether
   it was manual, and its age. Seek a new human check for the certification release and
   any election/archive destination change. Certification does not itself invalidate a
   link or refresh its evidence; result-observation freshness remains a separate rule.

3. **No other inconclusive reasons in this change.** Timeouts, exceptions, 429s, other
   non-200 responses and unapproved redirects continue to suppress the link when newest.
   They do not prove permanent breakage, but they are not the narrowly established
   script-only challenge case. Unknown reasons remain failures. Report “inconclusive”
   separately from “passed” in checker/release output; a challenge must not produce an
   “all links freshly verified” claim.

4. **Pin these tests, offline:** newer challenge preserves an older manual or automated
   success and its timestamp; challenge-only evidence exposes no link; success → real
   failure → challenge stays hidden across save/reload; later conclusive success restores
   the link; equal-instant failure wins across differing offsets; malformed evidence is
   rejected even when marked inconclusive; 403/429 challenge bodies and unapproved
   redirects cannot receive the exception; ordinary missing-text responses/timeouts remain
   failures; changed URL/election/expected content cannot reuse old evidence. Cover both
   public renderers and release reporting, including an old manual success remaining
   visibly old after repeated challenges.

Reviewed `_public_results_link`, the checker, the stored SOS manual check and the R3
review. Only the two mocked checker probes above were run; no live requests, code changes
or link-manifest updates were made.
