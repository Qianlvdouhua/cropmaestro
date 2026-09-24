import importlib
import tempfile
import unittest
from pathlib import Path
import zipfile


class DataTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('cm_importer.data')
        except ModuleNotFoundError:
            self.fail('cm_importer.data is not implemented')

    def read(self, text, **kwargs):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rice.csv'
            path.write_text(text, encoding='utf-8-sig', newline='')
            return mod.read_table(path, **kwargs)

    def test_identifiers_keep_leading_zero_and_zero_is_not_missing(self):
        table = self.read('编号,长度(cm)\n00123,0\n00124,12.50\n00125,\n')
        profile = self.module().profile_table(table, crop='rice')
        self.assertEqual(table['rows'][0], ['00123', '0'])
        self.assertEqual(profile['fields'][0]['kind'], 'identifier')
        numeric = profile['fields'][1]
        self.assertEqual(numeric['stats']['mean'], '6.25')
        self.assertEqual(numeric['stats']['missing'], 1)
        self.assertEqual(numeric['unit'], 'cm')
        self.assertIsNone(table['rows'][2][1])

    def test_fractional_counts_and_decimal_precision_are_not_rounded(self):
        table = self.read('分蘖数\n2.6666666666666665\n4.6666666666666667\n')
        field = self.module().profile_table(table, crop='rice')['fields'][0]
        self.assertEqual(field['sql_type'], 'DECIMAL(17,16)')
        self.assertEqual(field['stats']['mean'], '3.6666666666666666')
        self.assertEqual(field['kind'], 'count')

    def test_quoted_newline_and_raw_enum_preserved(self):
        table = self.read('编号,颜色,备注\n01, GREEN ,"a,b\nsecond"\n02,NA,plain\n')
        self.assertEqual(table['rows'][0][2], 'a,b\nsecond')
        field = self.module().profile_table(table, crop='rice')['fields'][1]
        self.assertEqual({x['value'] for x in field['values']}, {' GREEN ', 'NA'})

    def test_duplicate_headers_rejected(self):
        with self.assertRaisesRegex(ValueError, '重复|duplicate'):
            self.read('颜色,颜色\n红,黄\n')

    def test_malformed_row_rejected(self):
        with self.assertRaisesRegex(ValueError, '列数|columns'):
            self.read('a,b\n1,2,3\n')

    def test_reserved_cache_field_is_mapped_not_lost(self):
        table = self.read('query_hash,值\nabc,1\n')
        field = self.module().profile_table(table, crop='rice')['fields'][0]
        self.assertNotEqual(field['name'], 'query_hash')
        self.assertEqual(field['source_name'], 'query_hash')

    def test_missing_unit_stays_unknown_and_numeric_codes_are_unordered(self):
        table = self.read('等级,未知测量\n1,10.5\n3,12.5\n')
        fields = self.module().profile_table(table, crop='rice')['fields']
        self.assertEqual(fields[0]['kind'], 'categorical')
        self.assertIsNone(fields[1]['unit'])

    def test_mixed_crop_requires_explicit_handling(self):
        table = self.read('作物名称,编号\n玉米,1\n水稻,2\n')
        with self.assertRaisesRegex(ValueError, '多作物|mixed'):
            self.module().profile_table(table, crop='rice')

    def test_explicit_legacy_encoding_and_mixed_values(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rice.csv'
            path.write_bytes('编号,测量\n001,12\n002,NA\n'.encode('gb18030'))
            with self.assertRaisesRegex(ValueError, '解码'):
                mod.read_table(path)
            table = mod.read_table(path, encoding='gb18030')
            field = mod.profile_table(table, crop='rice')['fields'][1]
            self.assertTrue(field['sql_type'].startswith('VARCHAR'))
            self.assertEqual(table['rows'][1][1], 'NA')

    def test_unclosed_quote_is_not_skipped(self):
        with self.assertRaisesRegex(ValueError, 'CSV|列数'):
            self.read('编号,备注\n001,"unterminated\n')

    def test_unrepresentable_precision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '精度'):
            self.module().profile_table(self.read('测量\n0.' + '1' * 31 + '\n'), crop='rice')

    def test_xlsx_numeric_xml_precision_is_preserved(self):
        content_types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
        workbook = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
        rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:A2"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>measurement</t></is></c></row><row r="2"><c r="A2" t="n"><v>0.10000000000000001</v></c></row></sheetData></worksheet>'
        for omit_coordinate in (False, True):
            with self.subTest(omit_coordinate=omit_coordinate), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'rice.xlsx'
                selected_sheet = sheet.replace(' r="A2"', '') if omit_coordinate else sheet
                with zipfile.ZipFile(path, 'w') as archive:
                    for name, text in {'[Content_Types].xml': content_types, 'xl/workbook.xml': workbook,
                                       'xl/_rels/workbook.xml.rels': rels, 'xl/worksheets/sheet1.xml': selected_sheet}.items():
                        archive.writestr(name, text)
                table = self.module().read_table(path)
                self.assertEqual(table['rows'][0][0], '0.10000000000000001')

    def test_xlsx_sparse_empty_cells_and_formatted_identifiers(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rice.xlsx'
            book = openpyxl.Workbook()
            sheet = book.active
            sheet.append(['编号', '数值', '备注'])
            sheet.append([1, None, 'test'])
            sheet['A2'].number_format = '0000'
            sheet.append([2, 3.5, None])
            book.save(path)
            book.close()
            table = self.module().read_table(path)
            self.assertEqual(table['rows'], [['0001', None, 'test'], ['2', '3.5', None]])


if __name__ == '__main__':
    unittest.main()
