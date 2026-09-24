"""Copy finalized prompts to the fixed n8n directories without regenerating them."""

import os
from pathlib import Path, PurePosixPath
import tempfile

from .naming import validate_dataset_prefix
from .package import SUFFIXES, digest_bytes


DEPLOY_ROOT = '/data/n8n_data'
PROMPT_DIRECTORIES = {
    'data': '',
    'cache_results': '',
    'mapping_data': 'Mapping',
    'conditional_prompt': 'Prompt',
    'score_prompt': 'Prompt',
    'rule': 'Prompt/rule',
    'unit': 'Prompt/unit',
}


def _no_links(path):
    for component in (path, *path.parents):
        if component.is_symlink() or getattr(component, 'is_junction', lambda: False)():
            raise ValueError('部署路径不得包含符号链接或目录联接：' + str(component))


def _target_state(path, raw):
    _no_links(path)
    if path.exists():
        if not path.is_file():
            raise ValueError('目标不是普通文件：' + str(path))
        if path.read_bytes() != raw:
            raise ValueError('目标提示词内容冲突，不覆盖：' + str(path))
        return 'UNCHANGED'
    return 'COPY'


def _publish_file(path, raw):
    # Preflight happens for all files first. Recheck each target before writing.
    if _target_state(path, raw) == 'UNCHANGED':
        return 'UNCHANGED'
    path.parent.mkdir(parents=True, exist_ok=True)
    _no_links(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        try:
            # A complete file becomes visible at once; link never overwrites.
            # No unsafe copy fallback for filesystems that do not support links.
            os.link(temporary, path)
        except FileExistsError:
            return _target_state(path, raw)
        if path.read_bytes() != raw:
            raise ValueError('部署后文件内容校验失败：' + str(path))
        return 'COPIED'
    finally:
        os.unlink(temporary)


def deploy_prompts(directory, dataset_prefix, *, apply=False):
    """Preview by default; apply only on the filesystem visible to the workflow.

    This checks file integrity, not semantic correctness or database readiness.
    All seven destinations follow the user's fixed workflow directory contract.
    """
    prefix = validate_dataset_prefix(dataset_prefix)
    source = Path(directory).absolute()
    _no_links(source)
    assets = {}
    for suffix in SUFFIXES:
        name = f'{prefix}_{suffix}.txt'
        path = source / name
        _no_links(path)
        if not path.is_file():
            raise ValueError('缺少提示词文件：' + name)
        if path.stat().st_size > 2_000_000:
            raise ValueError('提示词文件超过部署大小上限：' + name)
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('提示词文件必须是 UTF-8：' + name) from exc
        if not text.strip():
            raise ValueError('提示词文件为空：' + name)
        assets[suffix] = raw

    result = {
        'status': 'PLANNED',
        'dataset_prefix': prefix,
        'files': [],
        'pending': [
            {'filename': f'{prefix}_{suffix}.txt', 'reason': '未提供工作流读取目录，未部署'}
            for suffix in SUFFIXES if suffix not in PROMPT_DIRECTORIES
        ],
    }
    for suffix, relative in PROMPT_DIRECTORIES.items():
        name = f'{prefix}_{suffix}.txt'
        result['files'].append({
            'filename': name,
            'target': str(PurePosixPath(DEPLOY_ROOT) / relative / name),
            'sha256': digest_bytes(assets[suffix]),
            'action': 'PLANNED',
        })
    if not apply:
        return result

    root = Path(DEPLOY_ROOT)
    if not root.is_absolute():
        raise ValueError('目标必须是当前系统的绝对路径；请在能访问 /data/n8n_data 的服务器环境执行 --apply')
    _no_links(root)
    targets = []
    for item, (suffix, relative) in zip(result['files'], PROMPT_DIRECTORIES.items()):
        path = root / relative / item['filename']
        # Check existing parents now so a non-directory fails before any copy.
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError('目标父路径不是目录：' + str(parent))
        _target_state(path, assets[suffix])
        item['target'] = str(path)
        targets.append((item, path, assets[suffix]))
    try:
        for item, path, raw in targets:
            item['action'] = _publish_file(path, raw)
        for item, path, raw in targets:
            if _target_state(path, raw) != 'UNCHANGED':
                raise ValueError('部署后目标文件缺失：' + str(path))
    except (OSError, ValueError) as exc:
        raise ValueError('提示词部署中断；可能已有部分文件写入，未自动回滚。'
                         '请核对目标文件、权限和硬链接支持；同内容可安全重试，不同内容不会覆盖。') from exc
    result['status'] = 'DEPLOYED_CONFIGURED_FILES'
    return result
