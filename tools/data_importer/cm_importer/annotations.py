"""Validate offline assistant annotations without changing measured data or statistics."""

import copy
import hashlib
import json
from pathlib import Path
import re


_FIELD_KEYS = {'name', 'label_zh', 'category', 'aliases', 'limitations', 'unit', 'unit_evidence', 'source_descriptor'}
_STATUSES = {'dataset_linked', 'provider_reference', 'source_column_only',
             'ambiguous_dataset_link', 'dataset_linked_incomplete', 'passport_metadata'}
_DESCRIPTOR_KEYS = {'status', 'original_header', 'source_column', 'definition', 'descriptor_url',
                    'evidence_id', 'reference_unit', 'official_categories', 'observed_categories', 'limitations'}
_HASH = re.compile(r'[a-f0-9]{64}')


def load_annotations(path):
    raw = Path(path).read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError('离线注释文件超过大小预算')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('离线注释 JSON 包含重复属性')
            result[key] = value
        return result
    parsed = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)
    if not isinstance(parsed, dict):
        raise ValueError('离线注释必须为 JSON 对象')
    return parsed


def _text(value, maximum=4000, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip())
            or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError('离线注释含无效或过长字符串')
    return value


def _string_list(value, maximum=30):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('离线注释列表类型或长度无效')
    for item in value:
        _text(item)


def _json_tree(value, depth=0):
    if depth > 8:
        raise ValueError('离线注释嵌套过深')
    if isinstance(value, str):
        _text(value, empty=True)
    elif isinstance(value, dict):
        if len(value) > 600:
            raise ValueError('离线注释对象过大')
        for key, item in value.items():
            _text(key, 200)
            _json_tree(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ValueError('离线注释列表过大')
        for item in value:
            _json_tree(item, depth + 1)
    elif value is not None and type(value) not in {int, bool}:
        raise ValueError('离线注释只接受明确的 JSON 字符串、整数、布尔值和容器')


def _descriptor(value, field, evidence):
    if not isinstance(value, dict) or set(value) - _DESCRIPTOR_KEYS or value.get('status') not in _STATUSES:
        raise ValueError('来源描述符状态或字段无效')
    if 'evidence_id' in value and value['evidence_id'] not in evidence:
        raise ValueError('来源描述符引用未知证据')
    official = value.get('official_categories', [])
    if not isinstance(official, list):
        raise ValueError('官方类别应为列表')
    for item in official:
        if not isinstance(item, dict) or set(item) - {'code', 'title', 'description'}:
            raise ValueError('官方类别结构无效')
        _text(item.get('code'), 100)
        _text(item.get('title'), 1000)
    observed = value.get('observed_categories', [])
    if not isinstance(observed, list):
        raise ValueError('观察类别应为列表')
    actual = {item['value'] for item in field['values']}
    seen = set()
    for item in observed:
        if not isinstance(item, dict) or set(item) - {'value', 'label_zh', 'match_status', 'official_codes', 'limitations'}:
            raise ValueError('观察类别注释结构无效')
        raw = item.get('value')
        if not isinstance(raw, str) or raw not in actual or raw in seen:
            raise ValueError('观察类别必须是本数据中真实存在且不重复的原始值')
        seen.add(raw)
        _text(item.get('label_zh'), 500)
        if 'official_codes' in item:
            _string_list(item['official_codes'], 100)
            if any(code not in {category['code'] for category in official} for code in item['official_codes']):
                raise ValueError('观察类别引用了不存在的来源代码')


def _canonical_unit(unit):
    return {'days': 'day', 'd': 'day', '天': 'day', '厘米': 'cm', '毫米': 'mm'}.get(unit, unit)


def apply_annotations(profile, annotations):
    """Return a copy enriched only with validated semantics and evidenced unit metadata."""
    if not isinstance(annotations, dict) or set(annotations) != {
            'format_version', 'source_sha256', 'authoring', 'evidence', 'dataset_context', 'fields'}:
        raise ValueError('离线注释顶层字段不符合格式')
    _json_tree(annotations)
    encoded = json.dumps(annotations, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(encoded) > 2_000_000:
        raise ValueError('离线注释超过大小预算')
    if annotations['format_version'] != 1 or annotations['source_sha256'] != profile['source']['sha256']:
        raise ValueError('离线注释版本或原始数据 SHA256 不匹配')
    author = annotations['authoring']
    if (not isinstance(author, dict) or set(author) != {'mode', 'author', 'external_model_called'}
            or author.get('mode') != 'assistant_assisted' or author.get('external_model_called') is not False):
        raise ValueError('离线注释必须明确标记为助手辅助且未调用外部模型')
    _text(author.get('author'), 200)
    evidence_rows = annotations['evidence']
    if not isinstance(evidence_rows, list) or not evidence_rows:
        raise ValueError('离线注释需要来源证据清单')
    evidence = {}
    for item in evidence_rows:
        if not isinstance(item, dict) or set(item) != {'id', 'sha256', 'locator'}:
            raise ValueError('证据记录格式无效')
        _text(item['id'], 100)
        _text(item['locator'])
        if not isinstance(item['sha256'], str) or not _HASH.fullmatch(item['sha256']) or item['id'] in evidence:
            raise ValueError('证据哈希无效或ID重复')
        evidence[item['id']] = item
    if not isinstance(annotations['dataset_context'], dict):
        raise ValueError('数据集背景必须为对象')
    supplied = annotations['fields']
    fields = profile['fields']
    if not isinstance(supplied, list) or len(supplied) != len(fields):
        raise ValueError('离线注释必须覆盖且仅覆盖全部真实字段')
    by_name = {}
    for item in supplied:
        if not isinstance(item, dict) or set(item) != _FIELD_KEYS:
            raise ValueError('字段注释不允许改写统计、SQL类型或添加其他字段')
        name = _text(item['name'], 64)
        if name in by_name:
            raise ValueError('字段注释重复')
        by_name[name] = item
    if set(by_name) != {field['name'] for field in fields}:
        raise ValueError('离线注释含未知字段或缺失字段')
    result = copy.deepcopy(profile)
    for field in result['fields']:
        annotation = by_name[field['name']]
        _text(annotation['label_zh'], 120)
        _text(annotation['category'], 80)
        _string_list(annotation['aliases'], 10)
        _string_list(annotation['limitations'])
        _descriptor(annotation['source_descriptor'], field, evidence)
        unit = annotation['unit']
        proof = annotation['unit_evidence']
        if unit is not None:
            _text(unit, 50)
            if (not isinstance(proof, dict) or set(proof) != {'scope', 'evidence_id', 'locator'}
                    or proof.get('scope') not in {'dataset_linked', 'source_header'}
                    or proof.get('evidence_id') not in evidence):
                raise ValueError('实际单位需要直接关联或原表头证据，参考单位不能提升为已确认')
            _text(proof['locator'])
            if proof['scope'] == 'dataset_linked' and annotation['source_descriptor']['status'] != 'dataset_linked':
                raise ValueError('单位证据与描述符关联状态矛盾')
            prior = field.get('unit')
            if prior is not None and _canonical_unit(prior) != _canonical_unit(unit):
                raise ValueError('离线注释单位与原表头单位冲突')
            if proof['scope'] == 'source_header' and prior is None:
                raise ValueError('原表头没有可确认单位，不能伪造表头证据')
            field.update(unit=unit, unit_evidence=copy.deepcopy(proof))
        elif proof is not None:
            raise ValueError('未提供单位时不得附加已确认单位证据')
        field['semantic'] = {key: copy.deepcopy(annotation[key]) for key in ('label_zh', 'category', 'aliases', 'limitations')}
        field['semantic']['evidence'] = 'assistant_assisted_source_annotations'
        field['source_descriptor'] = copy.deepcopy(annotation['source_descriptor'])
    result['dataset_context'] = copy.deepcopy(annotations['dataset_context'])
    result['semantic_provenance'] = dict(author, annotations_sha256=hashlib.sha256(encoded).hexdigest(),
                                         evidence=copy.deepcopy(evidence_rows))
    result.setdefault('warnings', []).append('字段语义由助手结合来源资料整理，未调用外部模型；不等同领域专家认证或跨来源可比性验证。')
    return result
