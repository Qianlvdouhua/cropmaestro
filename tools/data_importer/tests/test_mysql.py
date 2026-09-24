import importlib
import unittest


class MySQLTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('cm_importer.mysql')
        except ModuleNotFoundError:
            self.fail('cm_importer.mysql is not implemented')

    def test_identifier_quoting_rejects_unsafe_names(self):
        mod = self.module()
        self.assertEqual(mod.quote_identifier('叶长(cm)'), '`叶长(cm)`')
        for name in ('', 'x` DROP TABLE y', 'x\n', 'a' * 65):
            with self.assertRaises(ValueError):
                mod.quote_identifier(name)

    def test_types_are_whitelisted(self):
        mod = self.module()
        for valid in ('DECIMAL(17,16)', 'VARCHAR(128)', 'LONGTEXT', 'TEXT', 'TIMESTAMP'):
            self.assertEqual(mod.validate_sql_type(valid), valid)
        for invalid in ('INT); DROP TABLE x;--', 'VARCHAR(0)', 'DECIMAL(3,5)', 'DECIMAL(66,2)'):
            with self.assertRaises(ValueError):
                mod.validate_sql_type(invalid)

    def test_cache_contract_requires_explicit_confirmation(self):
        mod = self.module()
        contract = {'query_task_type': 'TEXT', 'time_column': 'created_at', 'session_id_length': 64, 'confirmed': False}
        with self.assertRaisesRegex(ValueError, '确认|confirmed'):
            mod.validate_contract(contract)
        contract['confirmed'] = True
        self.assertEqual(mod.validate_contract(contract)['time_column'], 'created_at')

    def test_normalized_hash_preserves_duplicates_and_strings(self):
        mod = self.module()
        fields = [{'name': '编号', 'sql_type': 'VARCHAR(3)'}, {'name': '值', 'sql_type': 'DECIMAL(4,2)'}]
        a = [['001', '1.20'], ['002', None]]
        b = [['002', None], ['001', '1.2']]
        self.assertEqual(mod.rows_digest(a, fields), mod.rows_digest(b, fields))
        self.assertNotEqual(mod.rows_digest(a, fields), mod.rows_digest(a + [a[0]], fields))
        self.assertNotEqual(mod.rows_digest(a, fields), mod.rows_digest([['1', '1.20'], ['002', None]], fields))

    def test_cache_schema_has_four_extras_and_no_unique_resource_constraint(self):
        mod = self.module()
        profile = {'crop': 'rice', 'fields': [{'name': '编号', 'sql_type': 'VARCHAR(20)'}],
                   'cache_contract': {'query_task_type': 'TEXT', 'time_column': 'created_at',
                                      'session_id_length': 64, 'confirmed': True}}
        columns = mod.expected_columns(profile, cache=True)
        self.assertEqual([x['name'] for x in columns], ['编号', 'query_task', 'created_at', 'query_hash', 'session_id'])
        ddl = mod.create_table_sql('rice_cache_results', columns, 'cm-import:' + 'a' * 64, cache=True)
        self.assertNotIn('UNIQUE', ddl)
        self.assertNotIn('PRIMARY KEY', ddl)
        self.assertIn('CURRENT_TIMESTAMP', ddl)


if __name__ == '__main__':
    unittest.main()
