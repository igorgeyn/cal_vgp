# Codex queue

Prompts waiting for Codex, oldest first. Paste each line into Codex as-is. Claude moves an
item to "Done" when its response is committed.

## Pending

1. **Explore renovation (execute, not review): E1 "Honest Explore" is unblocked** (D1-D3 approved; E0 done). Start after the P0.4 release merges
   `Read docs/plans/explore_renovation_plan_20261112.md on branch phase0-election-status and follow it. Do the next chunk whose blocking decisions in §2 are marked answered, and only that chunk. If none is unblocked, stop and say which decisions are pending. Never push, publish or write to R2.`

## Done

- P0.1 review: `b2ab1fba`
- P0.1 re-review: `4fcf12b6`
- Layout review (decision 3): `0b6e78f2`
- Bot-challenge ruling (P0.3): `da4e2f37`
- County census review (P1.1): `e008d60f`
- Site fixes review (P0.2, P0.2b, R7), by a Claude reviewer agent (Codex at usage limit): `482c8f15`
- CEDA column check review (P1b.1), by a Claude reviewer agent (Codex at usage limit): `2afae842`
- CEDA reconciliation review (P1b.1b), by a Claude reviewer agent (Codex at usage limit): see the commit adding `p1b_1b_reconciliation_review_response.md`
