import importlib
import json
from pathlib import Path
import tempfile
import unittest


class PackageTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('cm_importer.package')
        except ModuleNotFoundError:
            self.fail('cm_importer.package is not implemented')

    def test_seven_prompts_and_verified_rows(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'rice.csv'
            source.write_text('编号,叶长(cm)\n001,12.5\n002,\n', encoding='utf-8', newline='')
            out = Path(tmp) / 'out'
            result = mod.prepare_package(source, out, crop='rice')
            self.assertEqual(result['row_count'], 2)
            self.assertEqual(len(list((out / 'prompts').glob('*.txt'))), 7)
            verified = mod.verify_package(out)
            self.assertEqual(verified['rows'][0][0], '001')
            self.assertIsNone(verified['rows'][1][1])
            self.assertEqual(mod.prepare_package(source, out, crop='rice')['package_id'], result['package_id'])

    def test_tampered_prompt_rejected(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'rice.csv'
            source.write_text('编号,值\n001,1\n', encoding='utf-8')
            out = Path(tmp) / 'out'
            mod.prepare_package(source, out, crop='rice')
            (out / 'prompts' / 'rice_unit.txt').write_text('wrong unit', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '哈希|hash'):
                mod.verify_package(out)

    def test_existing_unrelated_directory_not_overwritten(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'rice.csv'
            source.write_text('编号\n001\n', encoding='utf-8')
            out = Path(tmp) / 'out'
            out.mkdir()
            original = out / 'keep.txt'
            original.write_text('user file', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '已存在|existing'):
                mod.prepare_package(source, out, crop='rice')
            self.assertEqual(original.read_text(), 'user file')

    def test_manifest_cannot_reference_external_file(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'rice.csv'
            source.write_text('编号\n001\n', encoding='utf-8')
            out = Path(tmp) / 'out'
            mod.prepare_package(source, out, crop='rice')
            path = out / 'manifest.json'
            manifest = json.loads(path.read_text(encoding='utf-8'))
            manifest['files']['../private.txt'] = '0' * 64
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '文件清单|路径|manifest'):
                mod.verify_package(out)

    def test_reuse_rejects_autodetected_crop_change(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            rice, wheat = Path(tmp) / 'rice.csv', Path(tmp) / 'wheat.csv'
            for path in (rice, wheat):
                path.write_text('id,value\n001,1\n', encoding='utf-8')
            out = Path(tmp) / 'out'
            mod.prepare_package(rice, out)
            with self.assertRaisesRegex(ValueError, '其他数据|作物|配置'):
                mod.prepare_package(wheat, out)


if __name__ == '__main__':
    unittest.main()
