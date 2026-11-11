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
