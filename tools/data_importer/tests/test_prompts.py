import copy
import json
import os
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from cm_importer.prompts import render_prompts
from cm_importer.semantics import SemanticError, enrich_profile


def example_profile():
    return {
        "format_version": 1,
        "crop": "rice",
        "source": {"filename": "rice.csv", "sha256": "abc123", "encoding": "utf-8-sig"},
        "row_count": 3,
        "fields": [
            {"source_name": "株高(cm)", "name": "株高(cm)", "sql_type": "DECIMAL(5,2)",
             "kind": "numeric", "unit": "cm", "unit_evidence": "column_header",
             "stats": {"count": 3, "observed": 2, "missing": 1, "distinct": 2,
                       "min": "80", "max": "100", "mean": "90", "median": "90",
                       "p25": "85", "p75": "95"},
             "values": [{"value": "80", "count": 1}, {"value": "100", "count": 1}], "notes": []},
            {"source_name": "protein", "name": "protein", "sql_type": "DECIMAL(4,2)",
             "kind": "numeric", "unit": None, "unit_evidence": None,
             "stats": {"count": 3, "observed": 2, "missing": 1, "distinct": 2,
                       "min": "7.5", "max": "8.5", "mean": "8", "median": "8",
                       "p25": "7.75", "p75": "8.25"}, "values": [], "notes": []},
            {"source_name": "粒型", "name": "粒型", "sql_type": "VARCHAR(10)",
             "kind": "categorical", "unit": None, "unit_evidence": None,
             "stats": {"count": 3, "observed": 3, "missing": 0, "distinct": 2},
             "values": [{"value": "短粒", "count": 2}, {"value": "长\"粒\n原值", "count": 1}], "notes": []},
            {"source_name": "品种编号", "name": "品种编号", "sql_type": "VARCHAR(20)",
             "kind": "identifier", "unit": None, "unit_evidence": None,
             "stats": {"count": 3, "observed": 3, "missing": 0, "distinct": 3},
             "values": [{"value": "PRIVATE-ID-DO-NOT-ENUMERATE", "count": 1}], "notes": []},
        ],
        "warnings": ["单位仅采纳来源证据"],
        "cache_contract": {"query_task_type": "VARCHAR(64)", "time_column": "create_at",
                           "session_id_length": 64, "confirmed": False},
        "extra_data": {"preserve": [1, 2]},
    }


def semantic_response(fields):
    return {"fields": [{"name": f["name"], "label_zh": "语义标签", "category": "描述信息",
                        "aliases": ["字段别名"], "limitations": ["需人工核验"]} for f in fields]}


@contextmanager
def model_server(responder):
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            records.append({"path": self.path, "body": payload,
                            "authorization": self.headers.get("Authorization")})
            status, response = responder(payload, len(records))
            body = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"base_url": f"http://127.0.0.1:{server.server_port}/v1", "model": "local-test",
               "timeout": 3, "temperature": 0, "max_tokens": 4096}, records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def success_responder(payload, request_number):
    inputs = json.loads(payload["messages"][1]["content"])
    return 200, {"choices": [{"message": {"content": json.dumps(semantic_response(inputs["fields"]), ensure_ascii=False)}}]}


class LexicalSemanticsTests(unittest.TestCase):
    def test_fallback_preserves_facts_and_does_not_mutate_input(self):
        profile = example_profile()
        before = copy.deepcopy(profile)
        result = enrich_profile(profile)
        self.assertEqual(profile, before)
        self.assertEqual(result["extra_data"], before["extra_data"])
        for original, updated in zip(profile["fields"], result["fields"]):
            for key, value in original.items():
                self.assertEqual(updated[key], value)
        self.assertEqual(result["fields"][0]["semantic"]["label_zh"], "株高")
        self.assertEqual(result["fields"][1]["semantic"]["category"], "营养品质")
        self.assertIsNone(result["fields"][1]["unit"])
        self.assertEqual(result["semantic_provenance"]["mode"], "lexical")

    def test_unknown_names_and_origins_do_not_gain_unsupported_traits(self):
        profile = example_profile()
        profile["fields"] = [{"name": name, "source_name": name, "kind": "text", "unit": None}
                             for name in ["mystery_z", "origin", "height"]]
        result = enrich_profile(profile)
        self.assertEqual(result["fields"][0]["semantic"]["label_zh"], "mystery_z")
        self.assertNotIn("适应", json.dumps(result["fields"][1]["semantic"], ensure_ascii=False))
        self.assertNotIn("抗倒", json.dumps(result["fields"][2]["semantic"], ensure_ascii=False))

    def test_qualified_names_do_not_acquire_unqualified_aliases(self):
        profile = example_profile()
        profile["fields"] = [{"name": name, "source_name": name, "kind": "numeric", "unit": None}
                             for name in ["protein_index", "height_ratio", "株高变化率"]]
        result = enrich_profile(profile)
        for original, field in zip(profile["fields"], result["fields"]):
            self.assertEqual(field["semantic"]["label_zh"], original["name"])
            self.assertEqual(field["semantic"]["aliases"], [])


class PromptRenderingTests(unittest.TestCase):
    def test_exactly_seven_files_with_source_and_cache_draft_scope(self):
        result = render_prompts(enrich_profile(example_profile()))
        expected = {f"rice_{suffix}.txt" for suffix in ["data", "cache_results", "mapping_data",
                    "score_prompt", "rule", "conditional_prompt", "unit"]}
        self.assertEqual(set(result), expected)
        for content in result.values():
            self.assertIn("rice.csv", content)
            self.assertIn("abc123", content)
            self.assertIn("未确认", content)
            self.assertIn("草稿", content)
        self.assertIn("rice_data", result["rice_data.txt"])
        self.assertIn("【表注释】", result["rice_data.txt"])
        self.assertIn("【字段信息】", result["rice_data.txt"])
        self.assertIn("\t", result["rice_data.txt"])
        self.assertNotIn("PRIVATE-ID-DO-NOT-ENUMERATE", "".join(result.values()))

    def test_rule_condition_and_score_share_all_numerical_facts_exactly(self):
        profile = enrich_profile(example_profile())
        result = render_prompts(profile)
        fact_sections = []
        for suffix in ["rule", "conditional_prompt", "score_prompt"]:
            content = result[f"rice_{suffix}.txt"]
            fact_sections.append(content.split("【共同数据事实】\n", 1)[1].split("\n【共同数据事实结束】", 1)[0])
            for field in profile["fields"][:2]:
                for key, value in field["stats"].items():
                    self.assertIn(json.dumps(key) + ": " + json.dumps(value), content)
            self.assertIn("未知", content)
            self.assertIn("有序", content)
            self.assertIn("无序", content)
            self.assertIn("普适", content)
        self.assertEqual(fact_sections[0], fact_sections[1])
        self.assertEqual(fact_sections[1], fact_sections[2])
        raw_category = json.dumps(profile["fields"][2]["values"][1], ensure_ascii=False)
        self.assertIn(raw_category, fact_sections[0])

    def test_dynamic_cache_contract_preserves_extra_column_order(self):
        profile = enrich_profile(example_profile())
        profile["cache_contract"].update(query_task_type="TEXT", time_column="created_at",
                                         session_id_length=128, confirmed=True)
        content = render_prompts(profile)["rice_cache_results.txt"]
        self.assertIn("query_task\tTEXT", content)
        self.assertIn("created_at\tTIMESTAMP", content)
        self.assertIn("session_id\tVARCHAR(128)", content)
        lines = content.split("【字段信息】", 1)[1].splitlines()
        extras = [line.split("\t")[0] for line in lines if "\t" in line][-4:]
        self.assertEqual(extras, ["query_task", "created_at", "query_hash", "session_id"])

    def test_large_categories_are_explicitly_partial_and_never_clip_values(self):
        profile = enrich_profile(example_profile())
        field = profile["fields"][2]
        field["stats"]["distinct"] = 75
        field["values"] = [{"value": f"原始类别_{i:02d}", "count": 1} for i in range(75)]
        result = render_prompts(profile)
        for suffix in ["rule", "conditional_prompt", "score_prompt"]:
            content = result[f"rice_{suffix}.txt"]
            self.assertIn("非穷举", content)
            self.assertIn("用户明确提供的原始值", content)
            self.assertIn("原始类别_00", content)
            self.assertNotIn("原始类别_74", content)

    def test_scoring_requires_user_direction_thresholds_and_available_traits(self):
        result = render_prompts(enrich_profile(example_profile()))
        content = result["rice_score_prompt.txt"]
        for phrase in ["用户", "阈值", "缺失", "惩罚", "最小值", "最优", "拒绝", "缺少", "无序"]:
            self.assertIn(phrase, content)
        self.assertNotIn("SELECT ", "".join(result.values()))
        units = result["rice_unit.txt"]
        self.assertIn("株高(cm)", units)
        self.assertIn("protein", units)
        self.assertIn("未知", units)

    def test_prompt_context_defers_output_contract_to_owning_n8n_node(self):
        result = render_prompts(enrich_profile(example_profile()))
        for suffix in ["rule", "conditional_prompt", "score_prompt"]:
            content = result[f"rice_{suffix}.txt"]
            self.assertIn("所属节点主提示词", content)
            self.assertIn("输出格式", content)
            self.assertIn("SQL", content)
            self.assertNotIn("不生成可执行 SQL", content)
            self.assertNotIn("不输出可执行 SQL", content)

    def test_crop_and_dynamic_cache_contract_match_importer_limits(self):
        profile = enrich_profile(example_profile())
        for width in [1, 512, 16000]:
            profile["cache_contract"].update(query_task_type=f"VARCHAR({width})", session_id_length=255)
            self.assertIn(f"query_task\tVARCHAR({width})", render_prompts(profile)["rice_cache_results.txt"])
        for invalid in ["VARCHAR(0)", "VARCHAR(16001)", "INT"]:
            profile["cache_contract"]["query_task_type"] = invalid
            with self.assertRaises(ValueError):
                render_prompts(profile)
        profile["cache_contract"].update(query_task_type="TEXT", session_id_length=256)
        with self.assertRaises(ValueError):
            render_prompts(profile)
        profile["cache_contract"]["session_id_length"] = 64
        for crop in ["Rice", "r" * 33, "../rice"]:
            profile["crop"] = crop
            with self.assertRaises(ValueError):
                render_prompts(profile)


class ModelSemanticsTests(unittest.TestCase):
    def test_real_http_adapter_keeps_data_separate_and_preserves_profile_facts(self):
        original = example_profile()
        before = copy.deepcopy(original)
        with model_server(success_responder) as (config, records):
            with patch.dict(os.environ, {"CM_IMPORTER_TEST_FAKE_KEY": "test-only-fake-token"}):
                config["api_key_env"] = "CM_IMPORTER_TEST_FAKE_KEY"
                result = enrich_profile(original, config)
        self.assertEqual(original, before)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "/v1/chat/completions")
        self.assertEqual(records[0]["authorization"], "Bearer test-only-fake-token")
        request = records[0]["body"]
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["messages"][0]["role"], "system")
        supplied_data = json.loads(request["messages"][1]["content"])
        self.assertEqual(supplied_data["fields"][0]["stats"], before["fields"][0]["stats"])
        self.assertEqual(supplied_data["fields"][0]["unit"], "cm")
        self.assertEqual(supplied_data["fields"][0]["unit_evidence"], "column_header")
        self.assertEqual(supplied_data["fields"][0]["notes"], [])
        self.assertEqual(supplied_data["fields"][0]["values"], before["fields"][0]["values"])
        self.assertNotIn("PRIVATE-ID-DO-NOT-ENUMERATE", json.dumps(supplied_data))
        self.assertEqual(result["fields"][0]["stats"], before["fields"][0]["stats"])
        self.assertEqual(result["fields"][0]["semantic"]["label_zh"], "语义标签")
        self.assertEqual(result["semantic_provenance"]["model"], "local-test")
        self.assertEqual(result["semantic_provenance"]["temperature"], 0)
        self.assertNotIn("test-only-fake-token", json.dumps(result))
        self.assertNotIn("127.0.0.1", json.dumps(result))

    def test_batches_at_twenty_fields_and_explicit_json_mode_compatibility(self):
        profile = example_profile()
        profile["fields"] = [{"name": f"field_{i}", "source_name": f"field_{i}", "kind": "text", "unit": None}
                             for i in range(41)]
        with model_server(success_responder) as (config, records):
            config["json_mode"] = False
            result = enrich_profile(profile, config)
        self.assertEqual(len(result["fields"]), 41)
        self.assertEqual([len(json.loads(r["body"]["messages"][1]["content"])["fields"]) for r in records], [20, 20, 1])
        self.assertTrue(all("response_format" not in r["body"] for r in records))

    def test_model_value_context_is_bounded_and_truncation_is_explicit(self):
        profile = example_profile()
        field = profile["fields"][2]
        field["values"] = [{"value": f"实际类别{i}", "count": 1} for i in range(30)]
        field["stats"]["distinct"] = 30
        with model_server(success_responder) as (config, records):
            enrich_profile(profile, config)
        supplied = json.loads(records[0]["body"]["messages"][1]["content"])["fields"][2]
        self.assertEqual(len(supplied["values"]), 20)
        self.assertEqual(supplied["values"], field["values"][:20])
        self.assertIn("非穷举", supplied["value_scope"])

    def test_rejects_unknown_units_duplicate_missing_and_wrong_typed_fields(self):
        def run_case(change):
            def responder(payload, request_number):
                answer = semantic_response(json.loads(payload["messages"][1]["content"])["fields"])
                change(answer)
                return 200, {"choices": [{"message": {"content": json.dumps(answer)}}]}
            with model_server(responder) as (config, records):
                with self.assertRaises(SemanticError):
                    enrich_profile(example_profile(), config)
            self.assertEqual(len(records), 2)

        for change in [lambda a: a["fields"][0].update(unit="made-up-unit"),
                       lambda a: a["fields"][0].update(name="invented_column"),
                       lambda a: a["fields"].append(copy.deepcopy(a["fields"][0])),
                       lambda a: a["fields"].pop(),
                       lambda a: a["fields"][0].update(aliases="not-a-list"),
                       lambda a: a["fields"][0].update(label_zh="过长" * 100),
                       lambda a: a["fields"][0].update(category="分类\n注入"),
                       lambda a: a.update(scoring={"cutoff": 70})]:
            with self.subTest(change=change):
                run_case(change)

    def test_retry_is_bounded_and_server_error_does_not_leak_response(self):
        def responder(payload, request_number):
            return 503, {"error": "secret-body-api-key-do-not-leak"}
        with model_server(responder) as (config, records):
            with self.assertRaises(SemanticError) as caught:
                enrich_profile(example_profile(), config)
        self.assertEqual(len(records), 2)
        self.assertNotIn("secret-body", str(caught.exception))
        self.assertNotIn("127.0.0.1", str(caught.exception))

    def test_authentication_error_is_not_retried(self):
        with model_server(lambda p, n: (401, {"error": "hidden-response"})) as (config, records):
            with self.assertRaises(SemanticError) as caught:
                enrich_profile(example_profile(), config)
        self.assertEqual(len(records), 1)
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("hidden-response", str(caught.exception))

    def test_rejects_embedded_json_fence_and_duplicate_json_properties(self):
        for malformed in ["prefix\n```json\n{}\n```", '{"fields": [], "fields": VALID_FIELDS}']:
            def responder(payload, request_number):
                answer = semantic_response(json.loads(payload["messages"][1]["content"])["fields"])
                content = malformed.replace("VALID_FIELDS", json.dumps(answer["fields"]))
                return 200, {"choices": [{"message": {"content": content}}]}
            with self.subTest(malformed=malformed):
                with model_server(responder) as (config, records):
                    with self.assertRaises(SemanticError):
                        enrich_profile(example_profile(), config)
                self.assertEqual(len(records), 2)

    def test_invalid_url_cannot_leak_details_from_transport_errors(self):
        with self.assertRaises(SemanticError) as caught:
            enrich_profile(example_profile(), {"base_url": "http://127.0.0.1/private\nSECRET_PATH", "model": "test"})
        self.assertNotIn("SECRET_PATH", str(caught.exception))

    def test_model_rejects_lone_unicode_surrogates_with_bounded_retry(self):
        for invalid in ["\ud800", "\udfff"]:
            def responder(payload, request_number):
                answer = semantic_response(json.loads(payload["messages"][1]["content"])["fields"])
                answer["fields"][0]["label_zh"] = invalid
                return 200, {"choices": [{"message": {"content": json.dumps(answer)}}]}
            with self.subTest(codepoint=hex(ord(invalid))):
                with model_server(responder) as (config, records):
                    with self.assertRaises(SemanticError) as caught:
                        enrich_profile(example_profile(), config)
                self.assertEqual(len(records), 2)
                self.assertNotIn(invalid, str(caught.exception))
                str(caught.exception).encode("utf-8")

    def test_model_preserves_valid_non_bmp_characters_from_json_surrogate_pairs(self):
        def responder(payload, request_number):
            answer = semantic_response(json.loads(payload["messages"][1]["content"])["fields"])
            answer["fields"][0]["label_zh"] = "稻穗\U0001f33e"
            answer["fields"][0]["aliases"] = ["\U0001f33e"]
            return 200, {"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=True)}}]}
        with model_server(responder) as (config, records):
            result = enrich_profile(example_profile(), config)
        self.assertEqual(len(records), 1)
        self.assertEqual(result["fields"][0]["semantic"]["label_zh"], "稻穗\U0001f33e")
        self.assertEqual(result["fields"][0]["semantic"]["aliases"], ["\U0001f33e"])
        json.dumps(result, ensure_ascii=False).encode("utf-8")
        for prompt in render_prompts(result).values():
            prompt.encode("utf-8")

    def test_accepts_only_whole_json_fence_and_retries_invalid_json(self):
        def responder(payload, request_number):
            answer = semantic_response(json.loads(payload["messages"][1]["content"])["fields"])
            content = "not-json" if request_number == 1 else "```json\n" + json.dumps(answer) + "\n```"
            return 200, {"choices": [{"message": {"content": content}}]}
        with model_server(responder) as (config, records):
            result = enrich_profile(example_profile(), config)
        self.assertEqual(len(records), 2)
        self.assertEqual(result["fields"][0]["semantic"]["label_zh"], "语义标签")


if __name__ == "__main__":
    unittest.main()
