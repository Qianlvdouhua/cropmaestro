import copy
from pathlib import Path
import tempfile
import unittest

from cm_importer.data import profile_table


class AnnotationTests(unittest.TestCase):
    def test_explicit_null_annotation_file_is_rejected(self):
        from cm_importer.annotations import load_annotations
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'annotations.json'
            path.write_text('null', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '注释.*对象'):
                load_annotations(path)

    def fixture(self):
        profile = profile_table({'headers': ['length', 'colour'], 'rows': [['1.25', 'GREEN'], [None, 'PURPLE']],
                                 'source': {'filename': 'rice.csv', 'sha256': 'a' * 64}}, crop='rice')
        annotation = {
            'format_version': 1, 'source_sha256': 'a' * 64,
            'authoring': {'mode': 'assistant_assisted', 'author': 'AI assistant', 'external_model_called': False},
            'evidence': [{'id': 'descriptor', 'sha256': 'b' * 64, 'locator': 'local dictionary and cached descriptor'}],
            'dataset_context': {'provider': 'Source provider', 'limitations': ['One source only']},
            'fields': [
                {'name': 'length', 'label_zh': '长度', 'category': '形态', 'aliases': [], 'limitations': [],
                 'unit': 'cm', 'unit_evidence': {'scope': 'dataset_linked', 'evidence_id': 'descriptor', 'locator': 'unit'},
                 'source_descriptor': {'status': 'dataset_linked', 'definition': 'Measured length', 'evidence_id': 'descriptor'}},
                {'name': 'colour', 'label_zh': '颜色', 'category': '形态', 'aliases': [], 'limitations': [],
                 'unit': None, 'unit_evidence': None,
                 'source_descriptor': {'status': 'source_column_only', 'definition': 'Original labels only',
                                       'observed_categories': [{'value': 'GREEN', 'label_zh': '绿色'},
                                                               {'value': 'PURPLE', 'label_zh': '紫色'}]}}
            ]}
        return profile, annotation

    def apply(self, profile, annotation):
        try:
            from cm_importer.annotations import apply_annotations
        except ImportError:
            self.fail('offline annotation entrypoint not implemented')
        return apply_annotations(profile, annotation)

    def test_entrypoint_exists(self):
        try:
            from cm_importer import annotations
        except ImportError:
            self.fail('offline annotation entrypoint not implemented')
        self.assertTrue(callable(getattr(annotations, 'apply_annotations', None)))

    def test_preserves_stats_values_types_and_input(self):
        profile, annotation = self.fixture()
        original = copy.deepcopy(profile)
        result = self.apply(profile, annotation)
        self.assertEqual(profile, original)
        for old, new in zip(profile['fields'], result['fields']):
            for key in ('stats', 'values', 'sql_type', 'kind'):
                self.assertEqual(old[key], new[key])
        self.assertEqual(result['fields'][0]['unit'], 'cm')
        self.assertEqual(result['fields'][0]['semantic']['label_zh'], '长度')
        self.assertEqual(result['semantic_provenance']['mode'], 'assistant_assisted')

    def test_rejects_wrong_source_incomplete_duplicate_or_added_fields(self):
        for mutation in ('source', 'missing', 'duplicate', 'extra'):
            with self.subTest(mutation=mutation):
                profile, annotation = self.fixture()
                if mutation == 'source': annotation['source_sha256'] = 'c' * 64
                elif mutation == 'missing': annotation['fields'].pop()
                elif mutation == 'duplicate': annotation['fields'].append(copy.deepcopy(annotation['fields'][0]))
                else: annotation['fields'][0]['name'] = 'imagined_trait'
                with self.assertRaises(ValueError): self.apply(profile, annotation)

    def test_rejects_fact_overrides_and_unverified_units(self):
        for mutation in ('stats', 'reference', 'missing_evidence', 'bad_evidence'):
            with self.subTest(mutation=mutation):
                profile, annotation = self.fixture()
                field = annotation['fields'][0]
                if mutation == 'stats': field['stats'] = {'mean': '999'}
                elif mutation == 'reference': field['unit_evidence']['scope'] = 'provider_reference'
                elif mutation == 'missing_evidence': field['unit_evidence'] = None
                else: field['unit_evidence']['evidence_id'] = 'unknown'
                with self.assertRaises(ValueError): self.apply(profile, annotation)

    def test_rejects_unobserved_translated_values_and_invalid_unicode(self):
        for mutation in ('value', 'unicode'):
            with self.subTest(mutation=mutation):
                profile, annotation = self.fixture()
                if mutation == 'value': annotation['fields'][1]['source_descriptor']['observed_categories'][0]['value'] = 'BLUE'
                else: annotation['fields'][0]['label_zh'] = '\ud800'
                with self.assertRaises(ValueError): self.apply(profile, annotation)

    def test_provider_reference_stays_reference_not_actual_unit(self):
        profile, annotation = self.fixture()
        annotation['fields'][0].update(unit=None, unit_evidence=None,
                                       source_descriptor={'status': 'provider_reference', 'reference_unit': 'cm',
                                                          'evidence_id': 'descriptor', 'definition': 'Candidate only'})
        result = self.apply(profile, annotation)
        self.assertIsNone(result['fields'][0]['unit'])
        self.assertEqual(result['fields'][0]['source_descriptor']['reference_unit'], 'cm')


if __name__ == '__main__':
    unittest.main()
