-- finance_statewide_v3.db schema
--
-- Built per docs/plans/finance-extract-scope-expansion.md (Codex rounds 1+2+3).
-- Centerpiece is finance_flow_v3 (transaction-level fact table).
-- Derived materialized tables: finance_*_by_type. Aggregate VIEWS: finance_*_total.
--
-- Quarantined rows live in finance_flow_v3 alongside accepted rows;
-- attribution columns are nullable for that reason.
--
-- This file is idempotent w.r.t. tables (CREATE TABLE IF NOT EXISTS)
-- but views + indexes are dropped and recreated so definitions can
-- iterate during development. init_db.py drives execution.

------------------------------------------------------------
-- 1. Fact table: finance_flow_v3
------------------------------------------------------------

CREATE TABLE IF NOT EXISTS finance_flow_v3 (
    flow_id              INTEGER PRIMARY KEY,

    -- Attribution result (NULL for quarantined / unattributed rows)
    finance_campaign_id  TEXT,
    measure_db_id        INTEGER,
    stance               TEXT,                 -- 'support' | 'oppose'
    receipt_type         TEXT,                 -- 'monetary_contribution'
                                               -- 'loan'
                                               -- 'in_kind'
                                               -- 'independent_expenditure'
    amount               REAL,
    txn_date             TEXT,                 -- ISO date YYYY-MM-DD
    week_start           TEXT,                 -- Monday ISO YYYY-MM-DD

    -- Source provenance (always populated)
    source_table         TEXT NOT NULL,        -- 'RCPT_CD' | 'LOAN_CD' | 'S496_CD' | ...
    source_form_type     TEXT NOT NULL,        -- 'A' | 'C' | 'B1' | 'F465P3' | ...
    filing_id            TEXT NOT NULL,
    amend_id             INTEGER NOT NULL,
    source_line_item     TEXT,                 -- LINE_ITEM column from source row
    source_tran_id       TEXT,                 -- TRAN_ID column from source row
    source_bakref_tid    TEXT,                 -- BAKREF_TID (cross-schedule reference)
    source_memo_refno    TEXT,                 -- MEMO_REFNO (informational reference)
    source_xref_schnm    TEXT,                 -- XREF_SCHNM (cross-schedule xref)
    amount_field_used    TEXT,                 -- 'AMOUNT' | 'LOAN_AMT1' | etc.

    -- Cover-sheet lineage (populated via FILING_ID join to
    -- CVR_CAMPAIGN_DISCLOSURE_CD; preserved even after successful
    -- attribution so debugging stays cheap given the sparsity of
    -- direct row-level ballot fields)
    cover_form_type      TEXT,                 -- F460 / F461 / F465 / F496 / etc
    cover_filer_id       TEXT,
    cover_filer_name     TEXT,
    cover_committee_id   TEXT,
    cover_bal_num        TEXT,
    cover_bal_name       TEXT,
    cover_bal_juris      TEXT,
    cover_sup_opp_cd     TEXT,
    cover_elect_date     TEXT,
    cover_from_date      TEXT,
    cover_thru_date      TEXT,
    attribution_method   TEXT,                 -- 'row_fields' | 'cover_sheet'
                                               -- | 'crosswalk' | 'inferred' | 'failed'

    -- Donor / payee identity
    committee_id         TEXT,                 -- filer of the line-item
    committee_name       TEXT,
    donor_name_raw       TEXT,
    donor_name_canon     TEXT,
    reported_filer       TEXT,                 -- IE rows: filing committee
    payee_name           TEXT,                 -- IE rows: vendor receiving the spend
    attribution_source   TEXT,                 -- 'funding_source' | 'filer'
                                               -- | 'inferred' | 'unknown'
    donor_type           TEXT,
    donor_sector         TEXT,

    -- Memo + dedupe keys
    memo_code            TEXT,                 -- present + truthy = excluded as memo
    source_fingerprint   TEXT,                 -- pre-attribution row identity
                                               -- (source_table, source_form_type,
                                               --  filing_id, source_line_item,
                                               --  source_tran_id)
    dedupe_key           TEXT,                 -- post-attribution cross-source dedupe key
                                               -- (receipt_type, finance_campaign_id,
                                               --  stance, donor_name_canon,
                                               --  payee_name, txn_date, amount,
                                               --  committee_id)

    -- Lifecycle
    quarantine_reason    TEXT                  -- NULL = accepted
);

------------------------------------------------------------
-- 2. Indexes on finance_flow_v3
--    Partial indexes WHERE quarantine_reason IS NULL keep hot-path
--    indexes ~3x smaller given typical 30-70% quarantine rates.
------------------------------------------------------------

DROP INDEX IF EXISTS idx_flow_source_row;
CREATE INDEX idx_flow_source_row
    ON finance_flow_v3 (source_table, filing_id, amend_id, source_line_item);

DROP INDEX IF EXISTS idx_flow_source_form;
CREATE INDEX idx_flow_source_form
    ON finance_flow_v3 (source_table, source_form_type);

DROP INDEX IF EXISTS idx_flow_accepted_campaign_stance_type;
CREATE INDEX idx_flow_accepted_campaign_stance_type
    ON finance_flow_v3 (finance_campaign_id, stance, receipt_type)
    WHERE quarantine_reason IS NULL;

DROP INDEX IF EXISTS idx_flow_accepted_measure_stance;
CREATE INDEX idx_flow_accepted_measure_stance
    ON finance_flow_v3 (measure_db_id, stance)
    WHERE quarantine_reason IS NULL;

DROP INDEX IF EXISTS idx_flow_accepted_type_date;
CREATE INDEX idx_flow_accepted_type_date
    ON finance_flow_v3 (receipt_type, txn_date)
    WHERE quarantine_reason IS NULL;

DROP INDEX IF EXISTS idx_flow_dedupe;
CREATE INDEX idx_flow_dedupe
    ON finance_flow_v3 (dedupe_key)
    WHERE quarantine_reason IS NULL;

DROP INDEX IF EXISTS idx_flow_quarantine;
CREATE INDEX idx_flow_quarantine
    ON finance_flow_v3 (quarantine_reason, source_table, source_form_type);

------------------------------------------------------------
-- 3. Derived materialized tables: by-type summaries
--    Populated by the rebuild script (later phase) from finance_flow_v3.
--    top5_share / hhi are recomputed per (campaign, stance, type) from
--    the underlying donor distribution within that type — never
--    summed across types.
------------------------------------------------------------

CREATE TABLE IF NOT EXISTS finance_summary_by_type (
    finance_campaign_id  TEXT NOT NULL,
    stance               TEXT NOT NULL,
    receipt_type         TEXT NOT NULL,
    total_amount         REAL NOT NULL,
    n_committees         INTEGER,
    n_transactions       INTEGER,
    top5_share           REAL,                 -- 0..100, pct of total
    hhi                  REAL,                 -- Herfindahl-Hirschman, 0..10000
    PRIMARY KEY (finance_campaign_id, stance, receipt_type)
);

DROP INDEX IF EXISTS idx_summary_bytype_measure;
CREATE INDEX idx_summary_bytype_measure
    ON finance_summary_by_type (finance_campaign_id, stance);

CREATE TABLE IF NOT EXISTS finance_top_donors_by_type (
    finance_campaign_id  TEXT NOT NULL,
    stance               TEXT NOT NULL,
    receipt_type         TEXT NOT NULL,
    donor_name_canon     TEXT NOT NULL,
    donor_type           TEXT,
    donor_sector         TEXT,
    total_amount         REAL NOT NULL,
    n_underlying_rows    INTEGER,
    attribution_source_mode TEXT,              -- modal attribution_source across rows
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, donor_name_canon)
);

DROP INDEX IF EXISTS idx_topdonors_bytype_amount;
CREATE INDEX idx_topdonors_bytype_amount
    ON finance_top_donors_by_type
       (finance_campaign_id, stance, receipt_type, total_amount DESC);

CREATE TABLE IF NOT EXISTS finance_timeline_weekly_by_type (
    finance_campaign_id  TEXT NOT NULL,
    stance               TEXT NOT NULL,
    receipt_type         TEXT NOT NULL,
    week_start           TEXT NOT NULL,        -- Monday ISO
    weekly_amount        REAL NOT NULL,
    cumulative_amount    REAL NOT NULL,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, week_start)
);

------------------------------------------------------------
-- 4. Aggregate VIEWS: cross-type totals
--    Each view reads from finance_flow_v3 directly so top5_share / HHI
--    and cumulative timeline are recomputed against the merged donor
--    distribution — NEVER summed from the by-type materialized
--    rows. This is the Codex round-2 gotcha encoded as a structural
--    invariant.
--    Views are dropped + recreated on every init_db.py run so
--    definitions can iterate.
------------------------------------------------------------

DROP VIEW IF EXISTS finance_summary_total;
CREATE VIEW finance_summary_total AS
WITH per_donor AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           SUM(amount) AS donor_total
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance, donor_name_canon
),
campaign_totals AS (
    SELECT finance_campaign_id, stance,
           SUM(donor_total) AS grand_total
    FROM   per_donor
    GROUP  BY finance_campaign_id, stance
),
ranked AS (
    SELECT finance_campaign_id, stance, donor_total,
           ROW_NUMBER() OVER (
               PARTITION BY finance_campaign_id, stance
               ORDER BY donor_total DESC
           ) AS rk
    FROM per_donor
),
top5 AS (
    SELECT finance_campaign_id, stance,
           SUM(donor_total) AS top5_sum
    FROM   ranked
    WHERE  rk <= 5
    GROUP  BY finance_campaign_id, stance
),
hhi_calc AS (
    SELECT pd.finance_campaign_id, pd.stance,
           SUM(
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0)) *
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0))
           ) AS hhi
    FROM   per_donor pd
    JOIN   campaign_totals ct
        ON ct.finance_campaign_id = pd.finance_campaign_id
       AND ct.stance               = pd.stance
    GROUP  BY pd.finance_campaign_id, pd.stance
),
flow_agg AS (
    SELECT finance_campaign_id, stance,
           SUM(amount)                  AS total_amount,
           COUNT(DISTINCT committee_id) AS n_committees,
           COUNT(*)                     AS n_transactions
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance
)
SELECT
    fa.finance_campaign_id,
    fa.stance,
    fa.total_amount,
    fa.n_committees,
    fa.n_transactions,
    CASE
        WHEN ct.grand_total > 0
        THEN 100.0 * t5.top5_sum / ct.grand_total
        ELSE NULL
    END                                  AS top5_share,
    h.hhi                                AS hhi
FROM   flow_agg fa
LEFT JOIN campaign_totals ct
       ON ct.finance_campaign_id = fa.finance_campaign_id
      AND ct.stance               = fa.stance
LEFT JOIN top5 t5
       ON t5.finance_campaign_id = fa.finance_campaign_id
      AND t5.stance               = fa.stance
LEFT JOIN hhi_calc h
       ON h.finance_campaign_id = fa.finance_campaign_id
      AND h.stance               = fa.stance;

DROP VIEW IF EXISTS finance_top_donors_total;
CREATE VIEW finance_top_donors_total AS
SELECT
    finance_campaign_id,
    stance,
    donor_name_canon,
    SUM(amount)                                         AS total_amount,
    MAX(donor_type)                                     AS donor_type,
    MAX(donor_sector)                                   AS donor_sector,
    json_group_array(DISTINCT receipt_type)             AS flow_types,
    json_group_array(DISTINCT attribution_source)       AS attribution_sources,
    -- primary_attribution_source: modal attribution by dollar weight
    -- (computed approximately via SQL; refinement in Python if needed)
    (SELECT attribution_source
     FROM finance_flow_v3 f2
     WHERE f2.quarantine_reason IS NULL
       AND f2.finance_campaign_id = f.finance_campaign_id
       AND f2.stance               = f.stance
       AND f2.donor_name_canon     = f.donor_name_canon
     GROUP BY attribution_source
     ORDER BY SUM(amount) DESC
     LIMIT 1)                                           AS primary_attribution_source,
    COUNT(*)                                            AS n_underlying_rows
FROM finance_flow_v3 f
WHERE quarantine_reason IS NULL
GROUP BY finance_campaign_id, stance, donor_name_canon;

DROP VIEW IF EXISTS finance_timeline_weekly_total;
CREATE VIEW finance_timeline_weekly_total AS
WITH per_week AS (
    SELECT finance_campaign_id, stance, week_start, SUM(amount) AS weekly_amount
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance, week_start
)
SELECT
    finance_campaign_id,
    stance,
    week_start,
    weekly_amount,
    SUM(weekly_amount) OVER (
        PARTITION BY finance_campaign_id, stance
        ORDER BY week_start
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_amount
FROM per_week;
