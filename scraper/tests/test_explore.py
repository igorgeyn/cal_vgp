"""Exercise the actual exported Explore helpers with Node, without a browser."""
import json
import shutil
import subprocess

import pytest

from src.website.explore import SCRIPT


def evaluate(expression):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for browser-rule parity')
    result = subprocess.run([node, '-e', SCRIPT + '\nconsole.log(JSON.stringify(' + expression + '));'],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('years,label', [
    ([1999, 1998], '1998–99'), ([2009, 2000, 2004], '2000–09'),
    ([2020, 2024], '2020–24'), ([2015], '2015'), ([], 'Years unavailable'),
])
def test_decade_label_uses_actual_years(years, label):
    assert evaluate(f'Explore.decadeLabel({json.dumps(years)})') == label


@pytest.mark.parametrize('passed,total,rated,text', [
    (0, 0, False, '0 of 0'), (1, 1, False, '1 of 1'),
    (3, 4, False, '3 of 4'), (3, 5, True, '60%'),
])
def test_small_cells_never_show_a_rate_or_color(passed, total, rated, text):
    cell = evaluate(f'Explore.cell({passed},{total})')
    assert cell['rated'] is rated and cell['text'] == text
    if not rated:
        assert cell['bg'] == 'transparent'
        assert '%' not in cell['text'] and '%' not in cell['label']
        assert 'too few' in cell['label']


def test_higher_minimum_keeps_counts_and_cannot_lower_the_five_floor():
    assert evaluate('Explore.cell(4,5,10).text') == '4 of 5'
    assert evaluate('Explore.cell(1,1,0).rated') is False


def test_coverage_is_a_disjoint_partition_including_missing_both():
    records = [dict(passed=1, field='Bond'), dict(passed=0, field='Bond'),
               dict(passed=1), dict(passed=0, field='  '), dict(passed=None),
               dict(passed=None, field='Bond'), dict(passed='1', field='Bond')]
    result = evaluate(f'Explore.coverage({json.dumps(records)}, "field")')
    assert result == dict(total=7, counted=2, missingColumn=2, missingOutcome=3)
    assert result['total'] == sum(result[k] for k in ('counted', 'missingColumn', 'missingOutcome'))
    assert evaluate('Explore.coverage([], "field")') == dict(total=0, counted=0, missingColumn=0, missingOutcome=0)


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_sort_never_promotes_small_extreme_cells(direction):
    expression = '''[{total:1,rate:100},{total:8,rate:60},{total:4,rate:0},{total:9,rate:70}]
        .sort((a,b)=>Explore.compareCells(a,b,c=>c.rate,"%s")).map(c=>c.total)''' % direction
    assert evaluate(expression) == ([8,9,1,4] if direction == 'asc' else [9,8,1,4])


@pytest.mark.parametrize('years,label', [
    ([2011, 2013, 2015, 2022, 2023, 2024], '2011, 2013, 2015, 2022–24'),
    ([1998, 1999, 2000, 2001], '1998–2001'), ([2024, 2024], '2024'), ([], 'Years unavailable'),
])
def test_year_ranges_list_gaps_instead_of_implying_a_span(years, label):
    assert evaluate(f'Explore.yearRanges({json.dumps(years)})') == label


def test_a_count_only_reason_suppresses_rates_at_any_size():
    cell = evaluate('Explore.cell(60, 92, 5, "county figures are counts only")')
    assert cell['rated'] is False and cell['text'] == '60 of 92' and cell['bg'] == 'transparent'
    assert cell['label'] == '60 of 92 passed; county figures are counts only'
    assert evaluate('Explore.cell(60, 92, 5, null).rated') is True
