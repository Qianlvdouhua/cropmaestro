import copy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cm_importer.package import prepare_package, verify_package
import test_annotations


class AnnotationIntegrationTests(unittest.TestCase):
    def test_explicit_empty_annotation_path_never_enables_model(self):
        from cm_importer.cli import main
        with patch('cm_importer.cli._config', return_value={'llm': {'enabled': True, 'model': 'must-not-call'}}), \
                patch('cm_importer.cli.prepare_package') as prepare, \
                patch('cm_importer.cli._output'), patch('cm_importer.cli._emit'):
            result = main(['prepare', 'rice.csv', '--annotations', ''])
        self.assertEqual(result, 1)
        prepare.assert_not_called()

    def inputs(self, root):
        source = root / 'rice.csv'
        source.write_text('length,colour\n1.25,GREEN\n,PURPLE\n', encoding='utf-8')
        _, annotation = test_annotations.AnnotationTests().fixture()
        annotation['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        return source, annotation

    def prepare(self, source, out, annotation, **kwargs):
        self.assertIn('annotations', inspect.signature(prepare_package).parameters, 'offline annotations API not implemented')
        return prepare_package(source, out, crop='rice', annotations=annotation, **kwargs)

    def test_source_annotations_feed_all_three_factual_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, annotation = self.inputs(root)
            annotation['fields'][0]['limitations'] = ['分档仅适用于来源明确限定的物种']
            self.prepare(source, root / 'out', annotation, dataset_prefix='genesys_rice')
            package = verify_package(root / 'out')
            self.assertEqual(package['profile']['semantic_provenance']['mode'], 'assistant_assisted')
            for suffix in ('rule', 'score_prompt', 'conditional_prompt', 'data', 'cache_results', 'unit'):
                text = (root / 'out/prompts' / f'genesys_rice_{suffix}.txt').read_text(encoding='utf-8')
                self.assertIn('Measured length', text)
                self.assertIn('Source provider', text)
                for limitation in annotation['fields'][0]['limitations']:
                    self.assertIn(limitation, text)
            mapping = (root / 'out/prompts/genesys_rice_mapping_data.txt').read_text(encoding='utf-8')
            self.assertIn('绿色', mapping)

    def test_changed_annotations_cannot_reuse_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, annotation = self.inputs(root)
            first = self.prepare(source, root / 'out', annotation)
            self.assertEqual(self.prepare(source, root / 'out', annotation)['package_id'], first['package_id'])
            altered = copy.deepcopy(annotation)
            altered['fields'][0]['label_zh'] = '另一个标签'
            with self.assertRaises(ValueError): self.prepare(source, root / 'out', altered)

    def test_annotations_and_model_mode_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, annotation = self.inputs(root)
            with self.assertRaisesRegex(ValueError, '注释.*模型|annotations.*llm'):
                self.prepare(source, root / 'out', annotation, llm_config={'model': 'unused'})

    def test_cli_accepts_annotations_without_qwen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, annotation = self.inputs(root)
            path = root / 'annotations.json'
            path.write_text(json.dumps(annotation, ensure_ascii=False), encoding='utf-8')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'cm_importer', 'prepare', str(source),
                                     '--crop', 'rice', '--dataset-prefix', 'genesys_rice', '--offline',
                                     '--annotations', str(path), '--out', str(root / 'out')], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(verify_package(root / 'out')['profile']['semantic_provenance']['mode'], 'assistant_assisted')


if __name__ == '__main__':
    unittest.main()
