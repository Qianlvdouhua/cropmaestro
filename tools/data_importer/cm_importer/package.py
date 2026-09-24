"""Immutable, hash-checked data and seven-prompt packages."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from .data import read_table, profile_table
from .naming import effective_dataset_prefix, validate_dataset_prefix

SUFFIXES = ('data', 'cache_results', 'mapping_data', 'score_prompt', 'rule', 'conditional_prompt', 'unit')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _request_fingerprint(crop, cache_contract, encoding, sheet, llm_config, dataset_prefix=None, annotations_hash=None, evaluation_hash=None):
    llm_public = {k: v for k, v in (llm_config or {}).items()
                  if k in {'model', 'temperature', 'max_tokens', 'json_mode'}}
    request = {'crop': crop, 'cache_contract': cache_contract, 'encoding': encoding,
               'sheet': sheet, 'llm': llm_public, 'llm_enabled': llm_config is not None}
    # The default prefix is already represented by crop in legacy fingerprints.
    if dataset_prefix is not None and dataset_prefix != crop:
        request['dataset_prefix'] = validate_dataset_prefix(dataset_prefix)
    if annotations_hash is not None:
        request['annotations_sha256'] = annotations_hash
    if evaluation_hash is not None:
        from .evaluation import RENDERER_VERSION
        request.update(evaluation_sha256=evaluation_hash, evaluation_renderer=RENDERER_VERSION)
    return digest_bytes(canonical(request).encode())


def prepare_package(input_path, output_dir, crop=None, cache_contract=None, llm_config=None, encoding=None, sheet=None,
                    dataset_prefix=None, annotations=None, evaluation_policy=None):
    from .semantics import enrich_profile
    from .prompts import render_prompts
    from .annotations import apply_annotations

    if annotations is not None and llm_config is not None:
        raise ValueError('离线注释与外部模型模式不能同时启用；请选择一个语义来源')
    if dataset_prefix is not None:
        validate_dataset_prefix(dataset_prefix)
    output = Path(output_dir).resolve()
    table = read_table(input_path, encoding=encoding, sheet=sheet)
    base_profile = profile_table(table, crop=crop, cache_contract=cache_contract)
    if dataset_prefix is not None:
        base_profile['dataset_prefix'] = dataset_prefix
    prefix = effective_dataset_prefix(base_profile)
    annotated = apply_annotations(base_profile, annotations) if annotations is not None else None
    annotation_hash = annotated['semantic_provenance']['annotations_sha256'] if annotated is not None else None
    evaluated = None
    if evaluation_policy is not None:
        from .evaluation import apply_evaluation
        evaluated = apply_evaluation(annotated if annotated is not None else base_profile, evaluation_policy)
    evaluation_hash = evaluated['evaluation']['policy_sha256'] if evaluated is not None else None
    fingerprint = _request_fingerprint(base_profile['crop'], cache_contract, encoding, sheet, llm_config, prefix, annotation_hash, evaluation_hash)
    if output.exists():
        if not (output / 'manifest.json').is_file():
            raise ValueError('输出目录已存在且不是完整接入包；不覆盖 existing files')
        existing = verify_package(output)
        if (existing['profile']['source']['sha256'] != table['source']['sha256']
                or existing['profile']['source']['filename'] != table['source']['filename']
                or existing['profile']['crop'] != base_profile['crop']
                or effective_dataset_prefix(existing['profile']) != prefix
                or existing['manifest'].get('request_fingerprint') != fingerprint):
            raise ValueError('输出目录已存在其他数据或配置版本；请选择新目录')
        return {'status': 'PREPARED_EXISTING', 'package_id': existing['manifest']['package_id'],
                'row_count': existing['profile']['row_count'], 'path': str(output),
                'scoring_configured': 'evaluation' in existing['profile']}
    profile = annotated if annotated is not None else enrich_profile(base_profile, llm_config=llm_config)
    if evaluated is not None:
        profile['evaluation'] = evaluated['evaluation']
    prompts = render_prompts(profile)
    expected = {prefix + '_' + suffix + '.txt' for suffix in SUFFIXES}
    if set(prompts) != expected or any(not isinstance(v, str) or not v.strip() for v in prompts.values()):
        raise ValueError('提示词生成器未返回恰好七个完整文件')
    if any(len(text) > 150000 for text in prompts.values()):
        raise ValueError('单份提示词超过150000字符预算；不能静默截断，请减少字段范围或明确处理')
    profile_raw = (canonical(profile) + '\n').encode('utf-8')
    rows_raw = ''.join(canonical(row) + '\n' for row in table['rows']).encode('utf-8')
    assets = {'profile.json': profile_raw, 'rows.jsonl': rows_raw}
    assets.update({'prompts/' + name: text.encode('utf-8') for name, text in prompts.items()})
    hashes = {name: digest_bytes(raw) for name, raw in assets.items()}
    package_id = digest_bytes(canonical(hashes).encode())
    manifest = {'format_version': 1, 'package_id': package_id, 'crop': profile['crop'],
                'row_count': profile['row_count'], 'request_fingerprint': fingerprint, 'files': hashes}
    if 'dataset_prefix' in profile:
        manifest['dataset_prefix'] = profile['dataset_prefix']
    output.parent.mkdir(parents=True, exist_ok=True)
    # This is a deliverable directory, not a private scratch directory: inherit
    # the explicitly selected parent's permissions. On Windows mkdtemp's private
    # ACL survives rename and would make the resulting package unreadable to its user.
    staging = output.parent / ('.' + output.name + '-prepare-' + uuid.uuid4().hex)
    staging.mkdir()
    for relative, content in assets.items():
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    atomic_json(staging / 'manifest.json', manifest)
    verify_package(staging)
    # mkdir is the exclusive reservation: unlike POSIX rename, it never replaces an empty target.
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise ValueError(f'另一任务已占用输出目录；本次候选包保留在 {staging}') from exc
    try:
        for item in staging.iterdir():
            item.rename(output / item.name)
        staging.rmdir()
    except OSError as exc:
        raise ValueError(f'提示词包交付中断；请保留并检查目录 {output} 和 {staging}') from exc
    verified = verify_package(output)
    return {'status': 'PREPARED', 'package_id': package_id, 'row_count': verified['profile']['row_count'],
            'path': str(output), 'scoring_configured': 'evaluation' in profile,
            'warnings': profile.get('warnings', [])}


def verify_package(directory):
    root = Path(directory).resolve()
    manifest_path = root / 'manifest.json'
    if manifest_path.is_symlink():
        raise ValueError('manifest 路径不得是符号链接')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    crop = manifest.get('crop', '')
    if not isinstance(crop, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', crop):
        raise ValueError('manifest 作物名称无效')
    prefix = effective_dataset_prefix(manifest)
    expected = {'profile.json', 'rows.jsonl'} | {'prompts/' + prefix + '_' + suffix + '.txt' for suffix in SUFFIXES}
    files = manifest.get('files', {})
    if set(files) != expected:
        raise ValueError('manifest 文件清单不符合七提示词约定')
    for relative, expected_hash in files.items():
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('接入包路径越界或符号链接')
        if digest_bytes(path.read_bytes()) != expected_hash:
            raise ValueError('接入包文件哈希 hash 不一致：' + relative)
    if digest_bytes(canonical(files).encode()) != manifest.get('package_id'):
        raise ValueError('接入包标识哈希 hash 不一致')
    profile = json.loads((root / 'profile.json').read_text(encoding='utf-8'))
    if profile.get('format_version') != 1 or profile.get('crop') != crop:
        raise ValueError('profile 版本或作物与 manifest 不一致')
    if (('dataset_prefix' in profile) != ('dataset_prefix' in manifest)
            or effective_dataset_prefix(profile) != prefix):
        raise ValueError('profile dataset_prefix 与 manifest 不一致')
    fields = profile.get('fields', [])
    if not fields or len({f['name'].casefold() for f in fields}) != len(fields):
        raise ValueError('profile 字段为空或重复')
    rows = []
    with (root / 'rows.jsonl').open(encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            if not isinstance(row, list) or len(row) != len(fields) or any(v is not None and not isinstance(v, str) for v in row):
                raise ValueError('数据行结构与字段不一致')
            rows.append(row)
    if len(rows) != profile.get('row_count') or len(rows) != manifest.get('row_count'):
        raise ValueError('数据行数与 manifest 不一致')
    return {'profile': profile, 'rows': rows, 'manifest': manifest}
