import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SUFFIXES = ('data', 'cache_results', 'mapping_data', 'conditional_prompt', 'score_prompt', 'rule', 'unit')


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('cm_importer.deployment'), '部署功能尚未实现')
        self.module = importlib.import_module('cm_importer.deployment')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'prompts'
        self.source.mkdir()
        for suffix in SUFFIXES:
            (self.source / f'genesys_rice_{suffix}.txt').write_bytes(('玉米格式\r\n' + suffix).encode())

    def deploy(self, **kwargs):
        return self.module.deploy_prompts(self.source, 'genesys_rice', **kwargs)

    def test_all_seven_fixed_paths_include_schema_files_at_root(self):
        result = self.deploy()
        self.assertEqual(result['status'], 'PLANNED')
        paths = {item['filename']: item['target'] for item in result['files']}
        expected = {'data': '', 'cache_results': '', 'mapping_data': 'Mapping', 'conditional_prompt': 'Prompt',
                    'score_prompt': 'Prompt', 'rule': 'Prompt/rule', 'unit': 'Prompt/unit'}
        self.assertEqual(paths, {f'genesys_rice_{k}.txt': f'/data/n8n_data/{v + "/" if v else ""}genesys_rice_{k}.txt'
                                 for k, v in expected.items()})
        self.assertEqual(result['pending'], [])

    def test_preview_does_not_create_destination(self):
        root = self.base / 'destination'
        with patch.object(self.module, 'DEPLOY_ROOT', str(root)):
            self.deploy()
        self.assertFalse(root.exists())

    def test_apply_preserves_bytes_and_repeated_apply_skips(self):
        with patch.object(self.module, 'DEPLOY_ROOT', str(self.base / 'destination')):
            result = self.deploy(apply=True)
            self.assertEqual(result['status'], 'DEPLOYED_CONFIGURED_FILES')
            self.assertEqual(len(result['files']), 7)
            for item in result['files']:
                self.assertEqual(Path(item['target']).read_bytes(), (self.source / item['filename']).read_bytes())
                self.assertEqual(item['action'], 'COPIED')
            repeated = self.deploy(apply=True)
            self.assertTrue(all(item['action'] == 'UNCHANGED' for item in repeated['files']))

    def test_conflict_is_checked_before_any_copy(self):
        root = self.base / 'destination'
        target = root / 'Prompt/unit/genesys_rice_unit.txt'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing')
        with patch.object(self.module, 'DEPLOY_ROOT', str(root)):
            with self.assertRaisesRegex(ValueError, '冲突'):
                self.deploy(apply=True)
        self.assertEqual(target.read_bytes(), b'existing')
        self.assertFalse((root / 'Mapping').exists())
        self.assertFalse((root / 'genesys_rice_data.txt').exists())

    def test_missing_or_invalid_source_prevents_deployment(self):
        target = self.source / 'genesys_rice_rule.txt'
        for raw in (b'', b'   ', b'\xff'):
            target.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.deploy()
        target.unlink()
        with self.assertRaises(ValueError):
            self.deploy()

    def test_invalid_prefix_is_rejected(self):
        with self.assertRaises(ValueError):
            self.module.deploy_prompts(self.source, '../rice')

    def test_relative_destination_is_rejected_on_apply(self):
        with patch.object(self.module, 'DEPLOY_ROOT', 'relative/destination'):
            with self.assertRaisesRegex(ValueError, '绝对路径'):
                self.deploy(apply=True)

    def test_destination_directory_instead_of_file_is_rejected(self):
        root = self.base / 'destination'
        (root / 'Mapping/genesys_rice_mapping_data.txt').mkdir(parents=True)
        with patch.object(self.module, 'DEPLOY_ROOT', str(root)):
            with self.assertRaises(ValueError):
                self.deploy(apply=True)


if __name__ == '__main__':
    unittest.main()
