"""Build the CAL-ACCESS source capability matrix for the v3 plan.

Output: data/CalAccess/SOURCE_MATRIX.md — what columns each table has,
FORM_TYPE distributions, and which key fields are non-empty in a sample.
Run once per fresh dump as the first Phase 0 step.
"""
from pathlib import Path
import csv
from collections import Counter

DUMP = Path('data/CalAccess/DUMP_2026-05-13/CalAccess/DATA')
TARGETS = [
    'RCPT_CD', 'LOAN_CD', 'S496_CD', 'S497_CD',
    'EXPN_CD', 'S401_CD', 'CVR_CAMPAIGN_DISCLOSURE_CD',
]

KEYS_OF_INTEREST = [
    'FORM_TYPE', 'BAL_NUM', 'BAL_NAME', 'SUP_OPP_CD',
    'AMEND_ID', 'MEMO_CODE', 'MEMO_REFNO', 'TRAN_ID', 'LINE_ITEM',
    'FILING_ID', 'FILER_ID', 'FILER_NAML',
    'AMOUNT', 'LOAN_AMT1', 'LOAN_AMT2', 'LOAN_AMT3', 'LOAN_AMT4',
    'LOAN_AMT5', 'LOAN_AMT6', 'LOAN_AMT7', 'LOAN_AMT8',
    'RCPT_DATE', 'EXPN_DATE', 'LOAN_DATE1', 'LOAN_DATE2',
    'SCHED_DATE', 'DATE_FIRST', 'DATE_LAST', 'ELECT_DATE',
    'CTRIB_NAML', 'PAYEE_NAML', 'BAKREF_TID',
]

SAMPLE_ROWS = 200_000
NULL_MARKER = chr(92) + 'N'  # backslash + N (CalAccess null sentinel)


def survey(path: Path):
    size_mb = path.stat().st_size / 1e6
    with path.open(encoding='latin-1', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader, [])
        form_types = Counter()
        nonempty = {k: 0 for k in KEYS_OF_INTEREST if k in header}
        sample_count = 0
        for row in reader:
            sample_count += 1
            if sample_count > SAMPLE_ROWS:
                break
            d = dict(zip(header, row))
            for k in nonempty:
                v = d.get(k, '')
                if v and v != NULL_MARKER:
                    nonempty[k] += 1
            ft = d.get('FORM_TYPE', '').strip()
            if ft:
                form_types[ft] += 1
        return {
            'size_mb': round(size_mb, 1),
            'header': header,
            'header_count': len(header),
            'sample_rows_read': sample_count,
            'form_type_distribution': dict(form_types.most_common(20)),
            'key_presence_count_in_sample': nonempty,
        }


def main():
    matrix = {}
    for t in TARGETS:
        p = DUMP / f'{t}.TSV'
        matrix[t] = {'error': 'missing'} if not p.exists() else survey(p)

    out = Path('data/CalAccess/SOURCE_MATRIX.md')
    lines = [
        '# CAL-ACCESS Source Capability Matrix',
        '',
        f'Built 2026-05-13 from `data/CalAccess/DUMP_2026-05-13/`.',
        f'Sampling first {SAMPLE_ROWS:,} rows per table for FORM_TYPE / key-field stats.',
        '',
    ]
    for table, info in matrix.items():
        lines.append(f'## {table}')
        if 'error' in info:
            lines.append(f'**MISSING:** {info["error"]}')
            lines.append('')
            continue
        lines.append(f'- File size: **{info["size_mb"]} MB**')
        lines.append(
            f'- Columns ({info["header_count"]}): '
            + ', '.join(f'`{c}`' for c in info['header'])
        )
        lines.append(f'- Sample size: {info["sample_rows_read"]:,} rows')
        if info['form_type_distribution']:
            lines.append('- **FORM_TYPE distribution** (in sample):')
            for ft, cnt in info['form_type_distribution'].items():
                lines.append(f'    - `{ft}` — {cnt:,} rows')
        lines.append('- **Key fields present in header**:')
        for k in KEYS_OF_INTEREST:
            if k in info['header']:
                present = info['key_presence_count_in_sample'].get(k, 0)
                lines.append(
                    f'    - `{k}` ✓ (non-empty: {present:,} / '
                    f'{info["sample_rows_read"]:,})'
                )
        missing = [k for k in KEYS_OF_INTEREST if k not in info['header']]
        if missing:
            lines.append('- **Key fields NOT in header**:')
            lines.append('    - ' + ', '.join(f'`{k}`' for k in missing))
        lines.append('')

    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'Matrix written: {out}')
    print(f'Tables surveyed: {sum(1 for v in matrix.values() if "error" not in v)} of {len(TARGETS)}')


if __name__ == '__main__':
    main()
