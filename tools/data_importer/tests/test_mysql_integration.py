"""Opt-in tests that create only namespaced objects in an isolated test database."""

import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import hashlib
from unittest.mock import patch

from cm_importer.package import prepare_package
from cm_importer.mysql import connect, apply_package, inspect_database, quote_identifier
from cm_importer.package import atomic_json, verify_package

CONTRACT = {'query_task_type': 'VARCHAR(64)', 'time_column': 'create_at',
            'session_id_length': 64, 'confirmed': True}


@unittest.skipUnless(os.environ.get('CM_MYSQL_TEST_CONFIG'), '隔离 MySQL 测试配置未提供')
class MySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path(os.environ['CM_MYSQL_TEST_CONFIG']).read_text(encoding='utf-8'))
        if cls.config['mysql']['database'] != 'cm_onboarding_test':
            raise ValueError('整合测试只允许 cm_onboarding_test 数据库')
        cls.connection = connect(cls.config['mysql'])
        cls.prefix = 'test' + uuid.uuid4().hex[:10]
        # This fixture belongs solely to the explicitly named isolated database.
        with cls.connection.cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS chat_memory (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, session_id VARCHAR(128) NOT NULL, question TEXT, answer TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `sql` TEXT, query_hash VARCHAR(64), varieties TEXT, graphConfig JSON)')
        cls.connection.commit()

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def package(self, root, crop):
        source = root / 'source.csv'
        source.write_text('编号,长度(cm),分类,备注\n001,0,1,"a,b\nsecond"\n002,2.6666666666666665,3,"x\'); DROP TABLE chat_memory; --"\n003,,5,尾部空格 \n', encoding='utf-8', newline='')
        out = root / crop
        prepare_package(source, out, crop=crop, cache_contract=CONTRACT)
        return out

    def test_publish_readback_repeat_and_preserve_runtime_cache(self):
        crop = self.prefix + 'a'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            result = apply_package(out, self.config, connection=self.connection)
            self.assertEqual(result['status'], 'PUBLISHED')
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(crop + '_data'))
                self.assertEqual(cursor.fetchone()['n'], 3)
                cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(crop + '_cache_results'))
                self.assertEqual(cursor.fetchone()['n'], 0)
                cursor.execute('INSERT INTO ' + quote_identifier(crop + '_cache_results') + ' (`编号`,session_id,query_hash) VALUES (%s,%s,%s)', ('001', 'session', 'hash'))
            self.connection.commit()
            self.assertEqual(apply_package(out, self.config, connection=self.connection)['status'], 'ALREADY_PUBLISHED')
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(crop + '_cache_results'))
                self.assertEqual(cursor.fetchone()['n'], 1)

    def test_existing_table_not_overwritten(self):
        crop = self.prefix + 'b'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            with self.connection.cursor() as cursor:
                cursor.execute('CREATE TABLE ' + quote_identifier(crop + '_data') + ' (sentinel VARCHAR(20))')
                cursor.execute('INSERT INTO ' + quote_identifier(crop + '_data') + ' VALUES (%s)', ('keep',))
            self.connection.commit()
            with self.assertRaisesRegex(ValueError, '已存在|覆盖'):
                apply_package(out, self.config, connection=self.connection)
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT sentinel FROM ' + quote_identifier(crop + '_data'))
                self.assertEqual(cursor.fetchone()['sentinel'], 'keep')

    def test_readonly_inspection_discovers_contract(self):
        crop = self.prefix + 'c'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            apply_package(out, self.config, connection=self.connection)
            info = inspect_database(self.config['mysql'], template_cache=crop + '_cache_results', connection=self.connection)
            self.assertTrue(info['chat_memory_compatible'])
            self.assertEqual(info['cache_contract'], CONTRACT)

    def test_corruption_is_rejected_before_database_write(self):
        crop = self.prefix + 'd'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            (out / 'rows.jsonl').write_text('["bad"]\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '哈希|hash'):
                apply_package(out, self.config, connection=self.connection)
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (crop + '_data',))
                self.assertEqual(cursor.fetchone()['n'], 0)

    def test_advisory_lock_prevents_concurrent_publication(self):
        crop = self.prefix + 'e'
        other = connect(self.config['mysql'])
        lock = 'cm:' + hashlib.sha256(('cm_onboarding_test:' + crop).encode()).hexdigest()[:48]
        try:
            with other.cursor() as cursor:
                cursor.execute('SELECT GET_LOCK(%s, 0)', (lock,))
            with tempfile.TemporaryDirectory() as tmp:
                out = self.package(Path(tmp), crop)
                with self.assertRaisesRegex(ValueError, '发布任务'):
                    apply_package(out, self.config, connection=self.connection)
                with self.connection.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (crop + '_data',))
                    self.assertEqual(cursor.fetchone()['n'], 0)
        finally:
            other.close()

    def test_failure_after_rename_is_reported_and_repeat_does_not_insert(self):
        crop = self.prefix + 'f'
        injected = []
        def fail_after_rename(path, state):
            if state.get('status') == 'TABLES_PUBLISHED' and not injected:
                injected.append(True)
                raise OSError('injected publication journal failure')
            return atomic_json(path, state)
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            with patch('cm_importer.mysql.atomic_json', side_effect=fail_after_rename):
                with self.assertRaisesRegex(ValueError, '发布未完成'):
                    apply_package(out, self.config, connection=self.connection)
            state = json.loads((out / 'publication.json').read_text(encoding='utf-8'))
            self.assertEqual(state['failed_at'], 'TABLES_PUBLISHED')
            result = apply_package(out, self.config, connection=self.connection)
            self.assertEqual(result['status'], 'ALREADY_PUBLISHED')
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(crop + '_data'))
                self.assertEqual(cursor.fetchone()['n'], 3)

    def test_published_data_drift_is_detected_without_overwrite(self):
        crop = self.prefix + 'g'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            apply_package(out, self.config, connection=self.connection)
            with self.connection.cursor() as cursor:
                cursor.execute('UPDATE ' + quote_identifier(crop + '_data') + ' SET `备注`=%s WHERE `编号`=%s', ('external edit', '001'))
            self.connection.commit()
            with self.assertRaisesRegex(ValueError, '回读校验'):
                apply_package(out, self.config, connection=self.connection)
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT `备注` FROM ' + quote_identifier(crop + '_data') + ' WHERE `编号`=%s', ('001',))
                self.assertEqual(cursor.fetchone()['备注'], 'external edit')

    def test_different_valid_package_mid_import_is_rejected(self):
        crop = self.prefix + 'h'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = self.package(root, crop)
            source = root / 'different.csv'
            source.write_text('编号,长度(cm)\n999,7.5\n', encoding='utf-8')
            other = root / 'other'
            prepare_package(source, other, crop=crop, cache_contract=CONTRACT)
            with patch('cm_importer.mysql.verify_package', side_effect=[verify_package(out), verify_package(other)]):
                with self.assertRaisesRegex(ValueError, '接入包.*变化|package.*changed'):
                    apply_package(out, self.config, connection=self.connection)
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (crop + '_data',))
                self.assertEqual(cursor.fetchone()['n'], 0)

    def test_apply_rediscovers_template_contract_for_repeat(self):
        crop = self.prefix + 'i'
        with tempfile.TemporaryDirectory() as tmp:
            out = self.package(Path(tmp), crop)
            apply_package(out, self.config, connection=self.connection)
            runtime_config = dict(self.config, template_cache_table=crop + '_cache_results',
                                  cache_contract=dict(CONTRACT, confirmed=False))
            result = apply_package(out, runtime_config, connection=self.connection)
            self.assertEqual(result['status'], 'ALREADY_PUBLISHED')

    def test_apply_rejects_actual_template_mismatch(self):
        crop = self.prefix + 'j'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = self.package(root, crop)
            apply_package(out, self.config, connection=self.connection)
            newcrop = self.prefix + 'k'
            alternate = root / newcrop
            prepare_package(root / 'source.csv', alternate, crop=newcrop,
                            cache_contract=dict(CONTRACT, query_task_type='TEXT'))
            runtime_config = {'mysql': self.config['mysql'], 'template_cache_table': crop + '_cache_results'}
            with self.assertRaisesRegex(ValueError, '缓存.*不一致|契约.*不一致'):
                apply_package(alternate, runtime_config, connection=self.connection)

    def test_same_crop_prefix_isolation_and_production_shaped_cache(self):
        contract = dict(CONTRACT, query_task_type='TEXT', time_column='created_at')
        config = dict(self.config, template_cache_table=None, cache_contract=contract)
        first_prefix, second_prefix = self.prefix + 'src1', self.prefix + 'src2'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'rice.csv'
            source.write_text('accession,heading_days\n001,80\n002,90\n', encoding='utf-8')
            first, second = root / 'first', root / 'second'
            prepare_package(source, first, crop='rice', dataset_prefix=first_prefix, cache_contract=contract)
            prepare_package(source, second, crop='rice', dataset_prefix=second_prefix, cache_contract=contract)
            for out, prefix in ((first, first_prefix), (second, second_prefix)):
                published = apply_package(out, config, connection=self.connection)
                self.assertEqual(published['status'], 'PUBLISHED')
                self.assertEqual(verify_package(out)['profile']['crop'], 'rice')
                info = inspect_database(config['mysql'], template_cache=prefix + '_cache_results', connection=self.connection)
                self.assertEqual(info['cache_contract'], contract)
                with self.connection.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(prefix + '_data'))
                    self.assertEqual(cursor.fetchone()['n'], 2)
                    cursor.execute('SELECT COUNT(*) AS n FROM ' + quote_identifier(prefix + '_cache_results'))
                    self.assertEqual(cursor.fetchone()['n'], 0)
            self.assertEqual(apply_package(first, config, connection=self.connection)['status'], 'ALREADY_PUBLISHED')


if __name__ == '__main__':
    unittest.main()
