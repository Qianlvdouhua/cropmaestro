"""Non-overwriting MySQL publication, with stage ownership and read-back checks."""

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .data import decimal_text
from .naming import effective_dataset_prefix
from .package import canonical, atomic_json, verify_package


def quote_identifier(name):
    if not isinstance(name, str) or not name or len(name) > 64 or re.search(r'[\x00-\x1f\x7f`]', name) or name != name.strip():
        raise ValueError('SQL 标识符无效')
    return '`' + name + '`'


def validate_sql_type(value):
    if not isinstance(value, str):
        raise ValueError('SQL 类型无效')
    value = value.upper()
    if value in {'TEXT', 'LONGTEXT', 'TIMESTAMP'}:
        return value
    varchar = re.fullmatch(r'VARCHAR\(([1-9]\d{0,4})\)', value)
    decimal = re.fullmatch(r'DECIMAL\(([1-9]\d?),([0-9]\d?)\)', value)
    if varchar and int(varchar.group(1)) <= 16000:
        return value
    if decimal and 0 <= int(decimal.group(2)) <= min(30, int(decimal.group(1))) and int(decimal.group(1)) <= 65:
        return value
    raise ValueError('SQL 类型不在允许范围内')


def validate_contract(contract):
    if contract.get('confirmed') is not True:
        raise ValueError('缓存表接口尚未确认 confirmed；先 inspect 既有缓存表或明确配置')
    if contract.get('time_column') not in {'create_at', 'created_at'}:
        raise ValueError('缓存时间列须明确为 create_at 或 created_at')
    task_type = validate_sql_type(contract.get('query_task_type', ''))
    if task_type != 'TEXT' and not task_type.startswith('VARCHAR('):
        raise ValueError('query_task 类型须为 TEXT 或 VARCHAR')
    length = contract.get('session_id_length')
    if type(length) is not int or not 1 <= length <= 255:
        raise ValueError('session_id 长度无效')
    return dict(contract, query_task_type=task_type)


def expected_columns(profile, cache=False):
    result = []
    for field in profile['fields']:
        quote_identifier(field['name'])
        result.append({'name': field['name'], 'sql_type': validate_sql_type(field['sql_type'])})
    if cache:
        contract = validate_contract(profile['cache_contract'])
        result.extend([{'name': 'query_task', 'sql_type': contract['query_task_type']},
                       {'name': contract['time_column'], 'sql_type': 'TIMESTAMP'},
                       {'name': 'query_hash', 'sql_type': 'VARCHAR(64)'},
                       {'name': 'session_id', 'sql_type': f"VARCHAR({contract['session_id_length']})"}])
    if len({f['name'].casefold() for f in result}) != len(result):
        raise ValueError('数据字段与缓存保留字段冲突')
    return result


def create_table_sql(name, columns, marker, cache=False):
    if not re.fullmatch(r'cm-import:[a-f0-9]{64}', marker):
        raise ValueError('任务归属标记无效')
    parts = []
    for column in columns:
        sql_type = validate_sql_type(column['sql_type'])
        default = ' DEFAULT CURRENT_TIMESTAMP' if cache and sql_type == 'TIMESTAMP' else ''
        parts.append(quote_identifier(column['name']) + ' ' + sql_type + ' NULL' + default)
    if cache:
        parts += ['KEY `cm_session_query` (`session_id`, `query_hash`)']
    return ('CREATE TABLE ' + quote_identifier(name) + ' (' + ', '.join(parts)
            + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC COMMENT='" + marker + "'")


def rows_digest(rows, fields):
    hashes = []
    for row in rows:
        if len(row) != len(fields):
            raise ValueError('回读行列数不一致')
        normalized = []
        for value, field in zip(row, fields):
            if value is None:
                normalized.append(None)
            elif field['sql_type'].upper().startswith('DECIMAL'):
                number = Decimal(str(value))
                if not number.is_finite():
                    raise ValueError('非有限数值')
                normalized.append(decimal_text(number))
            else:
                normalized.append(str(value))
        hashes.append(hashlib.sha256(canonical(normalized).encode()).digest())
    return hashlib.sha256(b''.join(sorted(hashes))).hexdigest()


def connect(config):
    try:
        import pymysql
    except ImportError as exc:
        raise ValueError('缺少 PyMySQL；请安装 requirements.txt') from exc
    for key in ('host', 'user', 'database'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError('MySQL 配置缺少 ' + key)
    quote_identifier(config['database'])
    secret_name = config.get('password_env', 'CM_MYSQL_PASSWORD')
    password = os.environ.get(secret_name)
    if password is None:
        raise ValueError('尚未设置 MySQL 密码环境变量 ' + secret_name)
    kwargs = dict(host=config['host'], port=int(config.get('port', 3306)), user=config['user'],
                  password=password, database=config['database'], charset='utf8mb4', autocommit=False,
                  connect_timeout=10, read_timeout=60, write_timeout=60,
                  local_infile=False, cursorclass=pymysql.cursors.DictCursor)
    if config.get('ssl_ca'):
        kwargs.update(ssl_ca=config['ssl_ca'], ssl_verify_cert=True, ssl_verify_identity=True)
    elif config['host'] not in {'localhost', '127.0.0.1', '::1'} and not config.get('trusted_private_network', False):
        raise ValueError('远程 MySQL 需要 ssl_ca 验证或明确配置 trusted_private_network')
    try:
        connection = pymysql.connect(**kwargs)
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")
            cursor.execute("SET SESSION time_zone='+00:00'")
        return connection
    except pymysql.MySQLError as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else 'connection'
        raise ValueError(f'MySQL 连接或会话初始化失败（错误码 {code}）；未展示凭证') from None


def _table_info(connection, name):
    with connection.cursor() as cursor:
        cursor.execute('SELECT TABLE_COMMENT, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (name,))
        return cursor.fetchone()


def _columns(connection, name):
    with connection.cursor() as cursor:
        cursor.execute('SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION', (name,))
        return cursor.fetchall()


def inspect_database(config, template_cache=None, connection=None):
    own = connection is None
    connection = connection or connect(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION() AS version, DATABASE() AS db')
            server = cursor.fetchone()
        memory = _columns(connection, 'chat_memory')
        memory_names = {x['COLUMN_NAME'].casefold() for x in memory}
        required = {'id', 'session_id', 'question', 'answer', 'created_at', 'sql', 'query_hash', 'varieties', 'graphconfig'}
        result = {'server_version': server['version'], 'database': server['db'],
                  'chat_memory_compatible': required <= memory_names, 'chat_memory_columns': memory,
                  'warnings': []}
        if not result['chat_memory_compatible']:
            result['warnings'].append('共享 chat_memory 缺失或字段不完整；请先初始化环境，工具不修改它。')
        if template_cache:
            quote_identifier(template_cache)
            columns = {x['COLUMN_NAME']: x for x in _columns(connection, template_cache)}
            times = [x for x in ('create_at', 'created_at') if x in columns]
            if len(times) != 1 or not {'query_task', 'session_id', 'query_hash'} <= columns.keys():
                raise ValueError('指定缓存模板表缺少四个可识别缓存字段，或时间列存在歧义')
            session = re.fullmatch(r'varchar\((\d+)\)', columns['session_id']['COLUMN_TYPE'], re.I)
            if not session or columns['query_hash']['COLUMN_TYPE'].lower() != 'varchar(64)' or columns[times[0]]['COLUMN_TYPE'].lower() != 'timestamp':
                raise ValueError('缓存模板的 session/query_hash/time 类型不在第一版支持范围')
            contract = {'query_task_type': columns['query_task']['COLUMN_TYPE'].upper(), 'time_column': times[0],
                        'session_id_length': int(session.group(1)), 'confirmed': True}
            result['cache_contract'] = validate_contract(contract)
            if any(x['COLUMN_NAME'] == 'session_id' and x['COLUMN_TYPE'].lower() != f"varchar({contract['session_id_length']})" for x in memory):
                result['warnings'].append('chat_memory 与缓存 session_id 长度不同；保留现有接口，工作流须使用共同允许的长度。')
        return result
    finally:
        if own:
            connection.close()


def _verify_table(connection, name, columns, marker, expected_digest=None, expected_count=None):
    info = _table_info(connection, name)
    if not info or info['TABLE_TYPE'] != 'BASE TABLE' or info['TABLE_COMMENT'] != marker:
        raise ValueError('目标表不属于本次接入包：' + name)
    actual = _columns(connection, name)
    if [(x['COLUMN_NAME'], x['COLUMN_TYPE'].upper()) for x in actual] != [(x['name'], x['sql_type']) for x in columns]:
        raise ValueError('服务器表结构与接入包不一致：' + name)
    with connection.cursor() as cursor:
        cursor.execute('SELECT ' + ','.join(quote_identifier(x['name']) for x in columns) + ' FROM ' + quote_identifier(name))
        records = cursor.fetchall()
    if expected_count is not None and len(records) != expected_count:
        raise ValueError('服务器记录数不一致：' + name)
    if expected_digest is not None:
        values = [[record[field['name']] for field in columns] for record in records]
        if rows_digest(values, columns) != expected_digest:
            raise ValueError('服务器数据回读校验不一致：' + name)


def apply_package(directory, config, connection=None):
    package = verify_package(directory)
    profile, rows, manifest = package['profile'], package['rows'], package['manifest']
    package_contract = validate_contract(profile['cache_contract'])
    db_config = config.get('mysql', config)
    prefix = effective_dataset_prefix(profile)
    data_name, cache_name = prefix + '_data', prefix + '_cache_results'
    columns, cache_columns = expected_columns(profile), expected_columns(profile, cache=True)
    marker = 'cm-import:' + manifest['package_id']
    target_digest = rows_digest(rows, columns)
    lock = 'cm:' + hashlib.sha256((db_config.get('database', '') + ':' + prefix).encode()).hexdigest()[:48]
    record_path = Path(directory) / 'publication.json'
    state = {'status': 'PREFLIGHT', 'package_id': manifest['package_id'], 'database': db_config.get('database'),
             'data_table': data_name, 'cache_table': cache_name, 'row_count': len(rows), 'created_objects': []}
    def check_package_identity():
        current = verify_package(directory)
        if current['manifest']['package_id'] != manifest['package_id']:
            raise ValueError('接入包在导入过程中发生变化，请停止替换文件并重新核对数据与提示词')

    own = connection is None
    connection = connection or connect(db_config)
    locked = False
    try:
        inspection = inspect_database(db_config, template_cache=config.get('template_cache_table'), connection=connection)
        actual_contract = inspection.get('cache_contract')
        configured_contract = config.get('cache_contract')
        if actual_contract is not None and validate_contract(actual_contract) != package_contract:
            raise ValueError('实际缓存模板与接入包契约不一致，请在新目录重新准备')
        if configured_contract is not None and (configured_contract.get('confirmed') or actual_contract is None):
            if validate_contract(configured_contract) != package_contract:
                raise ValueError('当前环境缓存契约与接入包不一致，请在新目录重新准备')
        if not inspection['chat_memory_compatible']:
            raise ValueError('共享 chat_memory 尚不兼容；没有创建或修改业务表')
        if not re.match(r'^8\.', inspection['server_version']):
            raise ValueError('第一版发布仅支持已按 MySQL 8.x 设计的服务；其他版本需单独验证')
        with connection.cursor() as cursor:
            cursor.execute('SELECT GET_LOCK(%s, 0) AS acquired', (lock,))
            locked = cursor.fetchone()['acquired'] == 1
        if not locked:
            raise ValueError('同一数据集前缀已有发布任务运行；请稍后重试')
        present = [_table_info(connection, data_name), _table_info(connection, cache_name)]
        if any(present):
            if not all(present) or any(x['TABLE_COMMENT'] != marker for x in present):
                raise ValueError('目标表已存在且非本接入包完整发布结果；拒绝覆盖或追加')
            _verify_table(connection, data_name, columns, marker, target_digest, len(rows))
            # Existing cache may have legitimate runtime results; never read/clear its contents on retry.
            actual_cache = _columns(connection, cache_name)
            if [(x['COLUMN_NAME'], x['COLUMN_TYPE'].upper()) for x in actual_cache] != [(x['name'], x['sql_type']) for x in cache_columns]:
                raise ValueError('已发布缓存结构发生变化，拒绝操作')
            check_package_identity()
            state['status'] = 'ALREADY_PUBLISHED'
            atomic_json(record_path, state)
            return state
        token = uuid.uuid4().hex[:12]
        stage_data, stage_cache = 'cm_stage_' + token + '_data', 'cm_stage_' + token + '_cache'
        state['status'] = 'STAGING'
        atomic_json(record_path, state)
        with connection.cursor() as cursor:
            for name, schema, cache in ((stage_data, columns, False), (stage_cache, cache_columns, True)):
                cursor.execute(create_table_sql(name, schema, marker, cache=cache))
                state['created_objects'].append(name)
                atomic_json(record_path, state)
            insert = ('INSERT INTO ' + quote_identifier(stage_data) + ' ('
                      + ','.join(quote_identifier(x['name']) for x in columns) + ') VALUES (' + ','.join(['%s'] * len(columns)) + ')')
            for start in range(0, len(rows), 250):
                cursor.executemany(insert, rows[start:start + 250])
        connection.commit()
        _verify_table(connection, stage_data, columns, marker, target_digest, len(rows))
        _verify_table(connection, stage_cache, cache_columns, marker, expected_count=0)
        # Check files again before making either final table visible.
        check_package_identity()
        if _table_info(connection, data_name) or _table_info(connection, cache_name):
            raise ValueError('最终目标在暂存期间被占用，拒绝覆盖')
        with connection.cursor() as cursor:
            cursor.execute('RENAME TABLE ' + quote_identifier(stage_data) + ' TO ' + quote_identifier(data_name)
                           + ', ' + quote_identifier(stage_cache) + ' TO ' + quote_identifier(cache_name))
        state['status'] = 'TABLES_PUBLISHED'
        atomic_json(record_path, state)
        _verify_table(connection, data_name, columns, marker, target_digest, len(rows))
        _verify_table(connection, cache_name, cache_columns, marker, expected_count=0)
        check_package_identity()
        state.update(status='PUBLISHED', prompts_path=str((Path(directory) / 'prompts').resolve()),
                     warnings=profile.get('warnings', []))
        atomic_json(record_path, state)
        return state
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:
            pass
        state['failed_at'] = state['status']
        state['status'] = 'PARTIAL_OR_FAILED'
        state['error_type'] = type(exc).__name__
        try:
            atomic_json(record_path, state)
        except OSError:
            pass
        if isinstance(exc, ValueError):
            raise
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else type(exc).__name__
        raise ValueError(f'MySQL 发布未完成（{code}），请检查 publication.json；暂存对象保留，未自动删除') from None
    finally:
        if locked:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT RELEASE_LOCK(%s)', (lock,))
            except Exception:
                pass
        if own:
            connection.close()
