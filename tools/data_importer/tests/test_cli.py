import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', '-m', 'cm_importer', *map(str, args)],
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_help(self):
        result = self.command('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('prepare', result.stdout)

    def test_explicit_blank_evaluation_is_not_silent_fallback(self):
        result = self.command('prepare','missing.csv','--crop','rice','--evaluation-policy',' ')
        self.assertEqual(result.returncode,1)
        self.assertIn('评价策略路径不能为空',result.stderr)

    def test_prepare_then_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'rice.csv'
            source.write_text('编号,叶长(cm)\n001,12.5\n', encoding='utf-8')
            out = Path(tmp) / 'prepared'
            result = self.command('prepare', source, '--out', out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['row_count'], 1)
            checked = self.command('verify', out)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)['status'], 'VERIFIED')

    def test_apply_needs_configuration_not_credentials_in_error(self):
        result = self.command('apply', 'missing-package')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('config', result.stderr)

    def test_deploy_prompts_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for suffix in ('data', 'cache_results', 'mapping_data', 'conditional_prompt', 'score_prompt', 'rule', 'unit'):
                (directory / f'genesys_rice_{suffix}.txt').write_text('提示词', encoding='utf-8')
            result = self.command('deploy-prompts', directory, '--dataset-prefix', 'genesys_rice')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'PLANNED')
            self.assertEqual(len(report['files']), 7)
            self.assertEqual(len(report['pending']), 0)


if __name__ == '__main__':
    unittest.main()
