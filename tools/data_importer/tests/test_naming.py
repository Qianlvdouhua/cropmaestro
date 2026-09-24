"""Dataset naming remains separate from the crop ontology and legacy packages."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from cm_importer import cli, mysql
from cm_importer.data import profile_table, read_table
from cm_importer.package import SUFFIXES, canonical, digest_bytes, prepare_package, verify_package
from cm_importer.prompts import render_prompts


CONTRACT = {'query_task_type': 'VARCHAR(64)', 'time_column': 'create_at',
            'session_id_length': 64, 'confirmed': True}


class DatasetNamingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'rice.csv'
        self.source.write_text('编号,叶长(cm)\n001,12.5\n002,\n', encoding='utf-8')
        self.output = self.root / 'package'

    def prepare(self, **kwargs):
        return prepare_package(self.source, self.output, crop='rice', cache_contract=CONTRACT, **kwargs)

    def rewrite_json(self, name, value):
        (self.output / name).write_text(canonical(value) + '\n', encoding='utf-8')

    def test_prompts_use_dataset_names_while_crop_stays_rice(self):
        profile = profile_table(read_table(self.source), crop='rice')
        profile['dataset_prefix'] = 'genesys_rice'
        prompts = render_prompts(profile)
        self.assertEqual(set(prompts), {'genesys_rice_' + suffix + '.txt' for suffix in SUFFIXES})
        for text in prompts.values():
            self.assertIn('作物："rice"', text)
            self.assertIn('数据表：genesys_rice_data', text)
            self.assertIn('结果缓存表：genesys_rice_cache_results', text)
        self.assertIn('genesys_rice_data：本次来源的 rice 作物观察数据', prompts['genesys_rice_data.txt'])

    def test_prepare_persists_prefix_and_exactly_seven_prefixed_files(self):
        self.prepare(dataset_prefix='genesys_rice')
        package = verify_package(self.output)
        self.assertEqual(package['profile']['crop'], 'rice')
        self.assertEqual(package['manifest']['crop'], 'rice')
        self.assertEqual(package['profile']['dataset_prefix'], 'genesys_rice')
        self.assertEqual(package['manifest']['dataset_prefix'], 'genesys_rice')
        self.assertEqual({p.name for p in (self.output / 'prompts').iterdir()},
                         {'genesys_rice_' + suffix + '.txt' for suffix in SUFFIXES})
        self.assertEqual(self.prepare(dataset_prefix='genesys_rice')['status'], 'PREPARED_EXISTING')

    def test_legacy_default_profile_manifest_names_and_request_fingerprint_are_preserved(self):
        self.prepare()
        package = verify_package(self.output)
        self.assertNotIn('dataset_prefix', package['profile'])
        self.assertNotIn('dataset_prefix', package['manifest'])
        self.assertEqual({p.name for p in (self.output / 'prompts').iterdir()},
                         {'rice_' + suffix + '.txt' for suffix in SUFFIXES})
        legacy_request = {'crop': 'rice', 'cache_contract': CONTRACT, 'encoding': None,
                          'sheet': None, 'llm': {}, 'llm_enabled': False}
        self.assertEqual(package['manifest']['request_fingerprint'], digest_bytes(canonical(legacy_request).encode()))
        self.assertEqual(self.prepare()['status'], 'PREPARED_EXISTING')

    def test_changing_prefix_changes_request_fingerprint_and_cannot_reuse_output(self):
        self.prepare(dataset_prefix='genesys_rice')
        first = verify_package(self.output)
        before = (self.output / 'manifest.json').read_bytes()
        for prefix in ('another_rice', 'rice', None):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(ValueError, '其他数据|配置|prefix'):
                self.prepare(dataset_prefix=prefix)
        self.assertEqual((self.output / 'manifest.json').read_bytes(), before)
        alternate = self.root / 'alternate'
        prepare_package(self.source, alternate, crop='rice', cache_contract=CONTRACT, dataset_prefix='another_rice')
        second = verify_package(alternate)
        self.assertNotEqual(first['manifest']['request_fingerprint'], second['manifest']['request_fingerprint'])
        self.assertNotEqual(first['manifest']['package_id'], second['manifest']['package_id'])

    def test_unsafe_prefix_values_are_rejected_before_model_or_output_creation(self):
        invalid_values = ['', 'Rice', '1rice', '../rice', 'rice/data', 'rice\\data', 'rice-data',
                          'r' * 33, 'rice\n', 'rice` DROP TABLE x', '稻米', 123, True, [], {}]
        for prefix in invalid_values:
            with self.subTest(prefix=prefix), patch('cm_importer.semantics.enrich_profile') as enrich:
                with self.assertRaisesRegex(ValueError, 'dataset_prefix'):
                    self.prepare(dataset_prefix=prefix)
                enrich.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_prompt_prefix_rejects_wrong_types_including_explicit_null(self):
        profile = profile_table(read_table(self.source), crop='rice')
        for prefix in (None, False, 123, [], {}, 'a\nb', '../rice'):
            with self.subTest(prefix=prefix):
                profile['dataset_prefix'] = prefix
                with self.assertRaisesRegex(ValueError, 'dataset_prefix'):
                    render_prompts(profile)

    def test_maximum_length_prefix_is_valid(self):
        prefix = 'r' * 32
        self.prepare(dataset_prefix=prefix)
        self.assertIn('prompts/' + prefix + '_cache_results.txt', verify_package(self.output)['manifest']['files'])

    def test_manifest_prefix_tampering_is_rejected(self):
        self.prepare(dataset_prefix='genesys_rice')
        original = verify_package(self.output)['manifest']
        for prefix in ('rice', 'other_rice', None, 123, True, {}, '../outside'):
            with self.subTest(prefix=prefix):
                changed = dict(original, dataset_prefix=prefix)
                self.rewrite_json('manifest.json', changed)
                with self.assertRaises(ValueError):
                    verify_package(self.output)
        changed = dict(original)
        changed.pop('dataset_prefix')
        self.rewrite_json('manifest.json', changed)
        with self.assertRaises(ValueError):
            verify_package(self.output)

    def test_profile_prefix_must_match_manifest_even_after_hashes_are_recomputed(self):
        self.prepare(dataset_prefix='genesys_rice')
        original = verify_package(self.output)
        for prefix in ('another_rice', None):
            with self.subTest(prefix=prefix):
                profile = dict(original['profile'])
                if prefix is None:
                    profile.pop('dataset_prefix')
                else:
                    profile['dataset_prefix'] = prefix
                self.rewrite_json('profile.json', profile)
                manifest = dict(original['manifest'], files=dict(original['manifest']['files']))
                manifest['files']['profile.json'] = digest_bytes((self.output / 'profile.json').read_bytes())
                manifest['package_id'] = digest_bytes(canonical(manifest['files']).encode())
                self.rewrite_json('manifest.json', manifest)
                with self.assertRaisesRegex(ValueError, 'dataset_prefix|前缀|一致'):
                    verify_package(self.output)

    def test_legacy_manifest_cannot_gain_an_unhashed_prefix_field(self):
        self.prepare()
        manifest = verify_package(self.output)['manifest']
        manifest['dataset_prefix'] = 'rice'
        self.rewrite_json('manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'dataset_prefix|前缀|一致'):
            verify_package(self.output)

    def test_cli_prepare_and_run_expose_prefix_and_separate_automatic_output_paths(self):
        parser = cli.parser()
        defaults = parser.parse_args(['prepare', str(self.source)])
        for command in ('prepare', 'run'):
            args = parser.parse_args([command, str(self.source), '--dataset-prefix', 'genesys_rice'])
            self.assertEqual(args.dataset_prefix, 'genesys_rice')
            self.assertNotEqual(cli._output(defaults, {}), cli._output(args, {}))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = cli.main(['prepare', str(self.source), '--crop', 'rice', '--out', str(self.output),
                               '--dataset-prefix', 'genesys_rice'])
        self.assertEqual(status, 0)
        self.assertEqual(verify_package(self.output)['profile']['dataset_prefix'], 'genesys_rice')

    def test_mysql_publication_uses_dataset_targets_record_and_lock(self):
        self.prepare(dataset_prefix='genesys_rice')
        connection = RecordingConnection()
        inspection = {'chat_memory_compatible': True, 'server_version': '8.0.0', 'warnings': []}
        with patch('cm_importer.mysql.inspect_database', return_value=inspection), \
                patch('cm_importer.mysql._table_info', return_value=None), \
                patch('cm_importer.mysql._verify_table'):
            state = mysql.apply_package(self.output, {'mysql': {'database': 'test_only'}}, connection=connection)
        self.assertEqual(state['status'], 'PUBLISHED')
        self.assertEqual(state['data_table'], 'genesys_rice_data')
        self.assertEqual(state['cache_table'], 'genesys_rice_cache_results')
        self.assertEqual(json.loads((self.output / 'publication.json').read_text(encoding='utf-8')), state)
        renames = [sql for sql, _ in connection.statements if sql.startswith('RENAME TABLE ')]
        self.assertEqual(len(renames), 1)
        self.assertIn(' TO `genesys_rice_data`', renames[0])
        self.assertIn(' TO `genesys_rice_cache_results`', renames[0])
        locks = [params for sql, params in connection.statements if 'GET_LOCK' in sql or 'RELEASE_LOCK' in sql]
        expected_lock = 'cm:' + hashlib.sha256(b'test_only:genesys_rice').hexdigest()[:48]
        self.assertEqual(locks, [(expected_lock,), (expected_lock,)])


class RecordingConnection:
    """Capture outbound publication SQL without any network connection."""

    def __init__(self):
        self.statements = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def executemany(self, sql, rows):
        self.statements.append((sql, rows))

    def fetchone(self):
        return {'acquired': 1}

    def commit(self):
        pass

    def rollback(self):
        pass


if __name__ == '__main__':
    unittest.main()
