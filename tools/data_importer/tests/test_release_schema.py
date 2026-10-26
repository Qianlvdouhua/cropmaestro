"""Keep distributed schema assets aligned with the runtime/importer contract."""

from pathlib import Path
import re
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]


class ReleaseSchemaTests(unittest.TestCase):
    def test_memory_ddl_contains_nullable_graph_config_json(self):
        ddl = (REPOSITORY / 'schema/ddl/00_chat_memory.sql').read_text(encoding='utf-8')
        self.assertRegex(ddl, r'(?i)\bgraphConfig\s+JSON\b')
        column = next(line for line in ddl.splitlines() if re.search(r'\bgraphConfig\b', line, re.I))
        self.assertNotIn('NOT NULL', column.upper())

    def test_combined_schema_documents_graph_config(self):
        text = (REPOSITORY / 'schema/schema_bus_rice_demo.txt').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?i)\bgraphConfig\s+JSON\b')

    def test_control_memory_schema_documents_graph_config(self):
        text = (REPOSITORY / 'prompts/bus_rice/control/chat_memory.txt').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?i)\bgraphConfig\s+JSON\b')


if __name__ == '__main__':
    unittest.main()
