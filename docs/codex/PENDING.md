# Codex queue

Prompts waiting for Codex, oldest first. Paste each line into Codex as-is. Claude moves an
item to "Done" when its response is committed.

## Pending

1. **Layout review (decision 3)**
   `Read docs/codex/layout_direction_a_review_prompt.md on branch phase0-election-status and follow it. Review only; commit only the response file it names.`
2. **Bot-challenge rule (P0.3)**
   `Read docs/codex/bot_challenge_rule_question.md on branch phase0-election-status and follow it. Review only; append your ruling to that file and commit only that file.`
3. **County census review (P1.1)**
   `Read docs/codex/p1_1_census_review_prompt.md on branch phase0-election-status and follow it. Review only; commit only the response file it names.`
4. **CEDA column check review (P1b.1)**
   `Read docs/codex/p1b_1_ceda_review_prompt.md on branch phase0-election-status and follow it. Review only; commit only the response file it names.`

## Done

- P0.1 review: `b2ab1fba`
- P0.1 re-review: `4fcf12b6`
