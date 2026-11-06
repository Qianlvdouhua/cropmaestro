"""Reproduce frozen CropMaestro RSS and pooled-reference set comparisons.

Python 3.9+; standard library only. No model calls or database access.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def identifiers(text):
    return [s.strip() for s in text.split(';') if s.strip()]


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def reproduce(data_dir, output_dir):
    policies = {}
    for r in read_csv(data_dir / 'query_reference.csv'):
        q = r['query_id']
        if q in policies:
            raise ValueError(f'Duplicate query policy: {q}')
        m = int(r['max_grade'])
        if m not in (0, 1, 2) or int(r['included_in_rss']) != int(m > 0):
            raise ValueError(f'Invalid inclusion or maximum grade: {q}')
        policies[q] = (m, set(identifiers(r['reference_accession_numbers'])))

    labels = {}
    positives = defaultdict(set)
    for r in read_csv(data_dir / 'relevance_judgments.csv'):
        key = (r['query_id'], r['accession_number'])
        if key in labels:
            raise ValueError(f'Duplicate judgment: {key}')
        g = int(r['grade'])
        if key[0] not in policies or g not in (0, 1, 2) or g > policies[key[0]][0]:
            raise ValueError(f'Invalid relevance grade: {key}')
        labels[key] = g
        if g > 0:
            positives[key[0]].add(key[1])
    for q, (_, ref) in policies.items():
        if ref != positives[q]:
            raise ValueError(f'Reference list and positive judgments disagree: {q}')

    runs = defaultdict(dict)
    for r in read_csv(data_dir / 'retrieved_accessions.csv'):
        key = (r['configuration'], r['run'])
        q = r['query_id']
        if q in runs[key]:
            raise ValueError(f'Duplicate query output: {key}/{q}')
        ids = identifiers(r['accession_numbers'])
        if len(ids) != len(set(ids)):
            raise ValueError(f'Duplicate accession: {key}/{q}')
        if len(ids) > 5:
            raise ValueError(f'More than five accessions: {key}/{q}')
        runs[key][q] = ids

    query_rows, run_rows = [], []
    for (configuration, run), predictions in sorted(runs.items()):
        if set(predictions) != set(policies):
            raise ValueError(f'Query coverage mismatch: {configuration}/{run}')
        total_gain = total_denominator = 0
        rss_queries = 0
        set_values = []
        for q, (m, ref) in policies.items():
            ids = predictions[q]
            grades = []
            for accession in ids:
                key = (q, accession)
                if key not in labels:
                    raise ValueError(f'Unjudged accession: {q}/{accession}')
                grades.append(labels[key])
            gain, denominator = sum(grades), 5 * m
            if m > 0:
                total_gain += gain
                total_denominator += denominator
                rss_queries += 1
            hits = len(set(ids) & ref)
            if m > 0 and ref:
                precision = hits / len(ids) if ids else 0.0
                recall = hits / len(ref)
                f1 = 2 * hits / (len(ids) + len(ref))
                set_values.append((precision, recall, f1))
            else:
                precision = recall = f1 = ''
            query_rows.append(dict(
                configuration=configuration, run=run, query_id=q,
                accession_numbers=';'.join(ids), relevance_grades=';'.join(map(str, grades)),
                gain=gain, max_grade=m, normalization_denominator=denominator,
                included_in_rss=int(m > 0), query_rss=gain / denominator if m else '',
                retrieved_count=len(ids), pooled_reference_count=len(ref), intersection_count=hits,
                included_in_set_comparison=int(m > 0 and bool(ref)),
                set_precision=precision, set_recall_pooled_reference=recall, set_f1_pooled_reference=f1))
        if not total_denominator or not set_values:
            raise ValueError(f'No evaluable queries: {configuration}/{run}')
        run_rows.append(dict(
            configuration=configuration, run=run, rss_queries=rss_queries,
            gain=total_gain, normalization_denominator=total_denominator,
            rss=total_gain / total_denominator, set_queries=len(set_values),
            set_precision=mean(v[0] for v in set_values),
            set_recall_pooled_reference=mean(v[1] for v in set_values),
            set_f1_pooled_reference=mean(v[2] for v in set_values)))

    grouped = defaultdict(list)
    for r in run_rows:
        grouped[r['configuration']].append(r)
    group_rows = []
    for configuration, rs in sorted(grouped.items()):
        r = dict(configuration=configuration, runs=len(rs),
                 rss_queries_per_run=rs[0]['rss_queries'], set_queries_per_run=rs[0]['set_queries'])
        for metric in ['rss', 'set_precision', 'set_recall_pooled_reference', 'set_f1_pooled_reference']:
            values = [v[metric] for v in rs]
            r[metric + '_mean'] = mean(values)
            r[metric + '_sd'] = stdev(values) if len(values) > 1 else 0.0
        group_rows.append(r)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in [('query_scores.csv', query_rows), ('run_scores.csv', run_rows),
                       ('configuration_scores.csv', group_rows)]:
        write_csv(output_dir / name, rows)
    print(f'Reproduced {len(group_rows)} configurations, {len(run_rows)} runs, '
          f'{len(query_rows)} query-run records. No database or model access.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    reproduce(args.data_dir, args.output_dir or args.data_dir / 'recomputed')


if __name__ == '__main__':
    main()
