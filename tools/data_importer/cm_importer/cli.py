"""CLI for offline preparation and explicit, non-overwriting MySQL publication."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from .package import canonical, prepare_package, verify_package
from .naming import validate_dataset_prefix
from .mysql import apply_package, inspect_database, validate_contract
from .annotations import load_annotations


def _config(path):
    if not path:
        return {}
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('config 必须是 JSON 对象')
    # Deliberately do not support copying inline credentials into packages or logs.
    for section in ('mysql', 'llm'):
        settings = value.get(section, {})
        if not isinstance(settings, dict):
            raise ValueError(section + ' 配置必须为对象')
        if any(key in settings for key in ('password', 'api_key', 'token', 'secret')):
            raise ValueError('config 不接受明文密码或密钥字段，请改用 password_env/api_key_env')
    return value


def _llm(config, offline):
    settings = dict(config.get('llm', {}))
    enabled = settings.pop('enabled', bool(settings))
    if not isinstance(enabled, bool):
        raise ValueError('llm.enabled 必须为布尔值')
    return settings if enabled and not offline else None


def _output(args, config):
    if args.out:
        return Path(args.out)
    path = Path(args.input)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    public_settings = {'crop': args.crop, 'contract': config.get('cache_contract'), 'llm': config.get('llm'),
                       'offline': args.offline, 'encoding': args.encoding, 'sheet': args.sheet}
    if getattr(args, '_annotations_hash', None):
        public_settings['annotations_sha256'] = args._annotations_hash
    if getattr(args, '_evaluation_hash', None):
        from .evaluation import RENDERER_VERSION
        public_settings.update(evaluation_sha256=args._evaluation_hash, evaluation_renderer=RENDERER_VERSION)
    if args.dataset_prefix is not None:
        public_settings['dataset_prefix'] = args.dataset_prefix
    settings_hash = hashlib.sha256(canonical(public_settings).encode()).hexdigest()[:8]
    safe_stem = re.sub(r'[^\w.-]', '_', path.stem)[:48] or 'data'
    return Path(config.get('output_root', 'outputs')) / f'{safe_stem}-{source_hash}-{settings_hash}'


def _emit(value, stream=None):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str), file=stream or sys.stdout)


def parser():
    result = argparse.ArgumentParser(description='CropMaestro 原始数据接入：七提示词与非覆盖 MySQL 发布')
    sub = result.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'run'):
        child = sub.add_parser(command, help='离线准备接入包' if command == 'prepare' else '准备并发布到已配置的 MySQL')
        child.add_argument('input', help='CSV/TSV/XLSX 原始文件')
        child.add_argument('--crop', help='无法自动识别时提供作物英文名称，例如 rice')
        child.add_argument('--dataset-prefix', type=validate_dataset_prefix,
                           help='数据集文件和 MySQL 表的前缀，例如 genesys_rice；省略时使用作物名称')
        child.add_argument('--out', help='新接入包目录；已存在的不同包不会覆盖')
        child.add_argument('--config', help='一次性 JSON 配置文件')
        child.add_argument('--encoding', help='需要时明确 CSV 编码，例如 gb18030')
        child.add_argument('--sheet', help='XLSX 工作表名称')
        child.add_argument('--offline', action='store_true', help='禁用外部模型；使用已提供的离线注释，否则采用保守词法标注')
        child.add_argument('--annotations', help='助手依据来源整理的离线注释 JSON；不调用外部模型')
        child.add_argument('--evaluation-policy', help='绑定输入数据SHA256的目标与评分策略JSON，分位数由工具计算')
    verify = sub.add_parser('verify', help='核验已准备接入包的文件、行数和哈希')
    verify.add_argument('package')
    inspect = sub.add_parser('inspect', help='只读检查目标 MySQL 与缓存字段契约')
    inspect.add_argument('--config', required=True)
    inspect.add_argument('--template-cache', help='既有缓存表，例如 corn_cache_results')
    apply = sub.add_parser('apply', help='把已核验的接入包发布到 MySQL，绝不覆盖已有其他表')
    apply.add_argument('package')
    apply.add_argument('--config', required=True)
    deploy = sub.add_parser('deploy-prompts', help='将最终提示词放入固定 n8n 目录；默认仅预览')
    deploy.add_argument('directory', help='包含七份最终 txt 的目录，不重新生成内容')
    deploy.add_argument('--dataset-prefix', required=True, help='文件名前缀，例如 genesys_rice')
    deploy.add_argument('--apply', action='store_true', help='在服务器文件系统实际部署七份提示词')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'deploy-prompts':
            from .deployment import deploy_prompts
            _emit(deploy_prompts(args.directory, args.dataset_prefix, apply=args.apply))
            return 0
        config = _config(getattr(args, 'config', None))
        annotation_path = getattr(args, 'annotations', None)
        if annotation_path is not None and not annotation_path.strip():
            raise ValueError('离线注释路径不能为空')
        annotations = load_annotations(annotation_path) if annotation_path is not None else None
        if annotations is not None:
            args._annotations_hash = hashlib.sha256(canonical(annotations).encode()).hexdigest()
        evaluation_path = getattr(args, 'evaluation_policy', None)
        if evaluation_path is not None and not evaluation_path.strip():
            raise ValueError('评价策略路径不能为空')
        evaluation = load_annotations(evaluation_path) if evaluation_path else None
        if evaluation is not None:
            args._evaluation_hash = hashlib.sha256(canonical(evaluation).encode()).hexdigest()
        if args.command == 'verify':
            package = verify_package(args.package)
            _emit({'status': 'VERIFIED', 'package_id': package['manifest']['package_id'],
                   'crop': package['profile']['crop'], 'row_count': package['profile']['row_count'],
                   'prompt_files': 7, 'semantic_mode': package['profile'].get('semantic_provenance', {}).get('mode'),
                   'scoring_configured': 'evaluation' in package['profile'],
                   'cache_contract_confirmed': package['profile']['cache_contract'].get('confirmed', False)})
            return 0
        if args.command == 'inspect':
            _emit(inspect_database(config.get('mysql', {}), args.template_cache or config.get('template_cache_table')))
            return 0
        if args.command == 'apply':
            _emit(apply_package(args.package, config))
            return 0
        if args.command == 'run':
            if not args.config:
                raise ValueError('run 需要 --config 一次性服务器配置；只有原始数据时可以先 prepare')
            inspection = inspect_database(config.get('mysql', {}), config.get('template_cache_table'))
            if not inspection['chat_memory_compatible']:
                raise ValueError('共享 chat_memory 不兼容；未修改服务器')
            if 'cache_contract' in inspection:
                explicit = config.get('cache_contract', {})
                if explicit.get('confirmed') and validate_contract(explicit) != inspection['cache_contract']:
                    raise ValueError('配置与实际缓存模板接口不一致；未修改服务器')
                config['cache_contract'] = inspection['cache_contract']
            validate_contract(config.get('cache_contract', {}))
            _emit({'phase': 'PREFLIGHT_OK', 'warnings': inspection.get('warnings', [])}, sys.stderr)
        output = _output(args, config)
        prepared = prepare_package(args.input, output, crop=args.crop, cache_contract=config.get('cache_contract'),
                                   llm_config=_llm(config, args.offline), encoding=args.encoding, sheet=args.sheet, annotations=annotations,
                                   dataset_prefix=args.dataset_prefix, evaluation_policy=evaluation)
        if args.command == 'run':
            _emit({'phase': 'PREPARED', 'path': str(output), 'row_count': prepared['row_count']}, sys.stderr)
            _emit(apply_package(output, config))
        else:
            _emit(prepared)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Deliberately no tracebacks or config/request dumps in the user-facing CLI.
        if isinstance(exc, ValueError):
            message = str(exc)
        elif isinstance(exc, OSError):
            message = '文件或网络操作失败，请检查路径、权限和连接；未打印敏感内容'
        else:
            message = '接入包或配置结构无效，请检查 schema'
        _emit({'status': 'FAILED', 'message': message}, sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
