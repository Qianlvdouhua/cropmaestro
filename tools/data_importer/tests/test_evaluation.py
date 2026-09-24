import copy
import sqlite3
import re
import tempfile
from pathlib import Path
import unittest

from cm_importer.data import profile_table
from cm_importer.evaluation import apply_evaluation, example_sql, score_case
from cm_importer.prompts import render_prompts
from cm_importer.package import prepare_package, verify_package


def sqlite_sql(sql):
    """Only translate MySQL's UTF-8 string literal constructor for offline SQLite tests."""
    return re.sub(r"CONVERT\(X'([0-9a-f]*)' USING utf8mb4\)",
                  lambda m: "'"+bytes.fromhex(m[1]).decode('utf-8').replace("'", "''")+"'", sql)


def fixture():
    p = profile_table({'headers': ['id', 'name', 'trait', 'risk'],
                       'rows': [[str(i), 'n'+str(i), str(i), 'LOW' if i < 5 else 'HIGH'] for i in range(11)],
                       'source': {'filename': 'rice.csv', 'sha256': 'a'*64}}, crop='rice')
    policy = {'format_version': 1, 'source_sha256': 'a'*64,
              'authoring': 'assistant_assisted', 'identity_fields': ['id', 'name'],
              'metrics': [dict(id='many', field='trait', method='quantile', direction='higher',
                               exclude_values=[], rationale='本批相对较大分档，非农艺最优'),
                          dict(id='safe', field='risk', method='ordered',
                               order=['LOW', 'HIGH'], rationale='原类别低风险优先')],
              'goals': [dict(id='G01', terms=['高产'], support='proxy', metrics=['many'],
                            explanation='仅按辅助指标分档，不是实测产量排名'),
                        dict(id='G02', terms=['稳产'], support='proxy', metrics=['safe'],
                            explanation='仅按风险类别，非稳产认证')],
              'unsupported': ['蛋白质'], 'limitations': ['仅当前样本']}
    return p, policy


class EvaluationTests(unittest.TestCase):
    def test_quantiles_and_no_mutation(self):
        p, policy = fixture()
        original = copy.deepcopy(p)
        result = apply_evaluation(p, policy)
        m = result['evaluation']['metrics'][0]
        self.assertEqual(m['cuts'], ['2', '4', '6', '8'])
        self.assertEqual(p, original)
        self.assertEqual(result['fields'], original['fields'])

    def test_case_boundaries_null_outside_and_plateau(self):
        p, policy = fixture()
        m = apply_evaluation(p, policy)['evaluation']['metrics'][0]
        db = sqlite3.connect(':memory:')
        expression = score_case(m)
        for v, expected in [(None, 100), (-1, 200), (0, 80), (2, 60), (4, 40),
                            (6, 20), (8, 0), (10, 0), (11, 200)]:
            score = db.execute('SELECT '+expression+' FROM (SELECT ? AS trait)', (v,)).fetchone()[0]
            self.assertEqual(score, expected, v)
        db.close()

    def test_lower_direction_and_excluded_zero(self):
        p, policy = fixture()
        policy['metrics'][0].update(direction='lower', exclude_values=['0'])
        m = apply_evaluation(p, policy)['evaluation']['metrics'][0]
        db = sqlite3.connect(':memory:')
        for value, expected in [(0, 200), (1, 0), (10, 80), (None, 100)]:
            self.assertEqual(db.execute('SELECT '+score_case(m)+' FROM (SELECT ? AS trait)',
                                        (value,)).fetchone()[0], expected)
        db.close()

    def test_reject_bad_policy_and_incomplete_distribution(self):
        p, policy = fixture()
        for mutate in [lambda q: q.update(source_sha256='b'*64),
                       lambda q: q['metrics'][0].update(field='fake'),
                       lambda q: q['metrics'][0].update(direction='guess'),
                       lambda q: q['metrics'][0].update(cuts=['1','2','3','4']),
                       lambda q: q['metrics'][1].update(order=['LOW']),
                       lambda q: q['goals'][0].update(metrics=['missing'])]:
            bad = copy.deepcopy(policy)
            mutate(bad)
            with self.assertRaises(ValueError):
                apply_evaluation(p, bad)
        p['fields'][2]['values'] = []
        with self.assertRaises(ValueError):
            apply_evaluation(p, policy)

    def test_example_executes_and_deduplicates(self):
        p, policy = fixture()
        enriched = apply_evaluation(p, policy)
        sql = example_sql(enriched, ['G01', 'G02', 'G02'])
        self.assertEqual(sql.count('WHEN `risk` IS NULL'), 1)
        self.assertNotIn('`trait` DESC', sql)
        self.assertIn('`total_score` ASC', sql)
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE rice_data (id TEXT, name TEXT, trait REAL, risk TEXT)')
        db.executemany('INSERT INTO rice_data VALUES (?,?,?,?)',
                       [(str(i), 'n'+str(i), i, 'LOW' if i < 5 else 'HIGH') for i in range(11)])
        self.assertEqual(len(db.execute(sqlite_sql(sql)).fetchall()), 5)
        db.close()

    def test_renderer_consistent_and_corn_style(self):
        p, policy = fixture()
        prompts = render_prompts(apply_evaluation(p, policy))
        self.assertEqual(len(prompts), 7)
        for suffix in ('mapping_data', 'rule', 'conditional_prompt', 'score_prompt'):
            self.assertIn('G01', prompts['rice_'+suffix+'.txt'])
            self.assertNotIn('只有用户明确选定数学评分方式及参数后', prompts['rice_'+suffix+'.txt'])
        score = prompts['rice_score_prompt.txt']
        self.assertIn('①【字段类型与统计信息】', score)
        self.assertIn('CASE', score)
        self.assertIn('样本相对分档', score)
        self.assertIn('字段名\t类型\t注释',prompts['rice_data.txt'])
        self.assertNotIn('source_descriptor',prompts['rice_data.txt'])
        self.assertIn('query_hash\tVARCHAR(64)',prompts['rice_cache_results.txt'])

    def test_prepare_policy_is_hashed_and_new_version_not_overwritten(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/'rice.csv'
            source.write_text('id,name,trait,risk\n'+'\n'.join(f'{i},n{i},{i},'+('LOW' if i<5 else 'HIGH') for i in range(11)),encoding='utf-8')
            _, policy = fixture()
            policy['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            out = Path(temp)/'package'
            prepare_package(source,out,crop='rice',evaluation_policy=policy)
            self.assertIn('evaluation',verify_package(out)['profile'])
            self.assertEqual(prepare_package(source,out,crop='rice',evaluation_policy=policy)['status'],'PREPARED_EXISTING')
            policy['metrics'][0]['direction']='lower'
            with self.assertRaises(ValueError):
                prepare_package(source,out,crop='rice',evaluation_policy=policy)

    def test_conditional_mapping_checks_real_fields_and_does_not_add_scores(self):
        p, policy = fixture()
        policy['related_targets'] = [dict(category='结构关联', terms=['理想株型'], fields=['trait'],
                                         explanation='仅明确方向后选择，不默认评分')]
        enriched = apply_evaluation(p,policy)
        self.assertIn('理想株型',render_prompts(enriched)['rice_mapping_data.txt'])
        self.assertEqual(len(enriched['evaluation']['metrics']),2)
        policy['related_targets'][0]['fields']=['fake']
        with self.assertRaises(ValueError):
            apply_evaluation(p,policy)


if __name__ == '__main__':
    unittest.main()
