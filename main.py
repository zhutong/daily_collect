# -*- coding:utf-8 -*-

import importlib
import json
import logging
import re
import shutil
import sys
import time
import uuid
from collections import defaultdict
from multiprocessing import Pool as MPool
from multiprocessing.dummy import Pool as TPool

import requests
from tornado import options
from tornado.log import enable_pretty_logging

from config import *

enable_pretty_logging()

sys.path.append(APP_PATH)


def __save_json(data, fn):
    with open(fn, 'w') as f:
        json.dump(data, f, indent=4)


def __new_job():
    start_time = time.strftime(TIMESTAMP_FORMAT)
    uid = uuid.uuid4().hex[:8]
    job_id = start_time + '_' + uid
    with open(JOB_TEMP_FN, 'w') as f:
        f.write(job_id)
    logging.info('new job created with ID: %s', job_id)
    return job_id


def __add_commands(commands, hostname, all_commands, depend_cmd=None, parsed_pre_data=None):
    if depend_cmd:
        params = parsed_pre_data.get(hostname, {}).get(depend_cmd, [])
        cmd_list = commands[0]['command_group']
        for p in params:
            for cmd in cmd_list:
                all_commands.append(cmd.format(**p))
    else:
        try:
            cmd_list = [c['command'] for c in commands]
        except:
            logging.error(commands)
        for cmd in cmd_list:
            if cmd not in all_commands:
                all_commands.append(cmd)


def get_all_commands(pre_stage=False):
    if pre_stage:
        logging.info('Stage 1: Get all device\'s pre-collect command list')
        command_define_file = PRE_COMMAND_DEFINE_FN
        command_file = PRE_COMMAND_TEMP_FN
        parsed_data = None
    else:
        logging.info('Stage 4: Get all device\'s command list')
        command_define_file = COMMAND_DEFINE_FN
        command_file = COMMAND_TEMP_FN
        with open(PRE_PARSED_CLI_FN) as f:
            parsed_data = json.load(f)
    with open(DEVICE_GROUP_DEFINE_FN) as f:
        device_group_define = json.load(f)
    with open(command_define_file) as f:
        command_define = json.load(f)
    command_dict = defaultdict(list)
    for item in command_define:
        filters = []
        if item.get('devices'):
            filters = item.get('devices')
        elif item.get('device_groups'):
            for i in item['device_groups']:
                g = device_group_define.get(i)
                if g is None:
                    logging.warning('Device group "%s" not defined!', i)
                else:
                    f = g.get('filter')
                    if not f:
                        logging.warning(
                            'Device group "%s" not define filter!', i)
                    else:
                        filters.extend(f)
        if not filters:
            continue
        query_str = '&'.join(('query=%s' % f for f in filters))
        url = DEVICE_FILTER_URL + query_str
        devices = requests.get(url).json()['filtered']
        commands = item['commands']
        depend_cmd = item.get('dependency')
        for d in devices:
            __add_commands(commands, d, command_dict[d],
                           depend_cmd, parsed_data)
    __save_json(command_dict, command_file)
    return command_dict


def __add_oids(collections, hostname, oid_dict, depend_oid=None, parsed_pre_data=None):
    if depend_oid:
        params = parsed_pre_data.get(hostname, {}).get(depend_oid, [])
        oid_list = oids[0]['oid_group']
        for p in params:
            for oid in oid_list:
                all_oids.append(oid.format(**p))
    else:
        oid_dict[hostname].extend(collections)


def get_all_oids(pre_stage=False):
    if pre_stage:
        logging.info('Stage 1: Get all device\'s pre-collect oid list')
        oid_define_file = PRE_OID_DEFINE_FN
        oid_file = PRE_OID_TEMP_FN
        parsed_data = None
    else:
        logging.info('Stage 4: Get all device\'s oid list')
        oid_define_file = OID_DEFINE_FN
        oid_file = OID_TEMP_FN
        with open(PRE_PARSED_SNMP_FN) as f:
            parsed_data = json.load(f)
    try:
        with open(oid_define_file) as f:
            oid_define = json.load(f)
    except:
        return {}
    with open(DEVICE_GROUP_DEFINE_FN) as f:
        device_group_define = json.load(f)
    oid_dict = defaultdict(list)
    for item in oid_define:
        filters = []
        if item.get('devices'):
            filters = item.get('devices')
        elif item.get('device_groups'):
            for i in item['device_groups']:
                g = device_group_define.get(i)
                if g is None:
                    logging.warning('Device group "%s" not defined!', i)
                else:
                    f = g.get('filter')
                    if not f:
                        logging.warning(
                            'Device group "%s" not define filter!', i)
                    else:
                        filters.extend(f)
        if not filters:
            continue
        query_str = '&'.join(('query=%s' % f for f in filters))
        url = DEVICE_FILTER_URL + query_str
        devices = requests.get(url).json()['filtered']
        collections = item['collections']
        depend_oid = item.get('dependency')
        for d in devices:
            __add_oids(collections, d, oid_dict, depend_oid, parsed_data)
    __save_json(oid_dict, oid_file)
    return oid_dict


def __collect_cli_and_save(param):
    path, hostname, commands = param
    logging.info('Start CLI collecting %s', hostname)
    fn = opj(path, hostname + '.json')
    data = dict(hostname=hostname,
                commands=commands)
    if not DEBUG:
        res = requests.post(CLI_COLLECTOR_URL, data=json.dumps(data))
        if res.status_code == 200:
            with open(fn, 'w') as f:
                f.write(res.text)
    logging.info('Finish CLI collecting %s', hostname)


def collect_cli(pre_stage=False, command_dict=None):
    if pre_stage:
        logging.info('Stage 2: Start CLI pre collecting')
        command_temp_fn = PRE_COMMAND_TEMP_FN
        path = opj(RAW_CLI_PATH, 'pre')
        stage = 2
    else:
        logging.info('Stage 5: Start CLI main collecting')
        command_temp_fn = COMMAND_TEMP_FN
        path = opj(RAW_CLI_PATH, 'main')
        stage = 5
    if command_dict is None:
        with open(command_temp_fn) as f:
            command_dict = json.load(f)
    pool = TPool(MAX_CLI_WORKERS)
    params = []
    for hostname, commands in command_dict.items():
        if commands:
            params.append((path, hostname, commands))
    pool.map(__collect_cli_and_save, params)
    pool.close()
    pool.join()
    logging.info('Stage %d CLI finished', stage)


def __collect_snmp_and_save(param):
    path, hostname, collections = param
    logging.info('Start SNMP collecting %s', hostname)
    fn = opj(path, hostname + '.json')
    output_dict = {}
    if not DEBUG:
        for collection in collections:
            data = dict(hostname=hostname,
                        commands=collection)
            res = requests.post(SNMP_COLLECTOR_URL,
                                data=json.dumps(data))
            if res.status_code == 200:
                output_dict[collection['name']] = res.json()
        __save_json(output_dict, fn)
    logging.info('Finish SNMP collecting %s', hostname)


def collect_snmp(pre_stage=False, oid_dict=None):
    if pre_stage:
        logging.info('Stage 2: Start SNMP pre collecting')
        oid_temp_fn = PRE_OID_TEMP_FN
        stage = 2
        sub_path = 'pre'
    else:
        logging.info('Stage 5: Start SNMP main collecting')
        oid_temp_fn = OID_TEMP_FN
        stage = 5
        sub_path = 'main'
    if oid_dict is None:
        try:
            with open(oid_temp_fn) as f:
                oid_dict = json.load(f)
        except:
            logging.info('Stage %d SNMP finished', stage)
            return
    pool = TPool(MAX_SNMP_WORKERS)
    params = []
    path = opj(RAW_SNMP_PATH, sub_path)
    for hostname, collections in oid_dict.items():
        params.append((path, hostname, collections))
    pool.map(__collect_snmp_and_save, params)
    pool.close()

    logging.info('Stage %d SNMP finished', stage)


def __get_cli_parser(pre_stage=False):
    command_define_file = PRE_COMMAND_DEFINE_FN if pre_stage else COMMAND_DEFINE_FN

    with open(command_define_file) as f:
        command_define = json.load(f)
    parser_dict = {}
    group_commands = {}
    for item in command_define:
        for cmd in item['commands']:
            parser_def = cmd.get('parser')
            if parser_def is None:
                continue
            try:
                module = importlib.import_module('parser.%s' % (parser_def[0]))
                parser = getattr(module, parser_def[1])
                parser_dict[cmd['command']] = parser
            except:
                logging.error('Load parser failed: %s.%s', *parser_def)
                raise
            group = cmd.get('command_group')
            if group:
                group_commands[cmd['command']] = group[-1]
    return parser_dict, group_commands


def __parse_cli_func(data_path, fn, parsed_data_path, parser_dict, group_commands):
    result = {}
    group_commands_start = group_commands.keys()
    with open(opj(data_path, fn)) as f:
        data = json.load(f)
    try:
        if data['status'] != 'success' and not data.get('output'):
            hostname = fn[:-5]
            login = dict(status=data['status'], msg=data['message'])
            result['login'] = [login]
        else:
            hostname = data['hostname']
    except:
        logging.error(fn)
        raise
    in_group = False
    for output in data.get('output', []):
        if output['status'] != 'Ok':
            continue
        cmd = output['command']
        for k in group_commands_start:
            if cmd.startswith(k):
                in_group = True
                parser = parser_dict.get(k)
                text_blocks = []
                exit_group_cmd = group_commands[k]
                result[k] = result.get(k, [])
                break
        if in_group:
            text_blocks.append(output['output'])
            if cmd == exit_group_cmd:
                text = ''.join(text_blocks)
                parsed_item = parser(text)
                try:
                    result[k].append(parsed_item[0])
                except:
                    logging.error('parse %s %s faild', hostname, k)
                    # print(text)
                    # raise
                in_group = False
        else:
            parser = parser_dict.get(cmd)
            if parser:
                # clean \r
                o = output['output'].replace('\r', '')
                try:
                    parsed_item = parser(o)
                    if parsed_item:
                        result[cmd] = parsed_item
                    else:
                        logging.warning('Empty item for %s %s', hostname, cmd)
                except:
                    logging.error('Parse %s %s error!', hostname, cmd)
                    # print(o)
                    # raise
    parsed_fn = opj(parsed_data_path, fn)
    __save_json(result, parsed_fn)
    return hostname, result


def parse_cli(job_id=None, pre_stage=False):
    if pre_stage:
        logging.info('Stage 3: Start parsing pre data')
        stage = 3
        data_path = opj(OUTPUT_DATA_PATH, 'pre')
    else:
        logging.info('Stage 6: Start parsing main data')
        stage = 6
        if job_id is None:
            with open(JOB_TEMP_FN) as f:
                job_id = f.read()

    pool = MPool()
    results = [pool.apply_async(__parse_func,
                                (data_path, fn, pre_stage))
               for fn in os.listdir(data_path)]
    parsed_data = [res.get() for res in results]
    parsed_data = {k: v for k, v in parsed_data}

    if pre_stage:
        __save_json(parsed_data, PRE_PARSED_DATA_FN)
    return parsed_data


def __get_snmp_parser(pre_stage=False):
    oid_define_file = PRE_OID_DEFINE_FN if pre_stage else OID_DEFINE_FN

    try:
        with open(oid_define_file) as f:
            oid_define = json.load(f)
    except:
        return {}, None
    parser_dict = {}
    for item in oid_define:
        for collection in item['collections']:
            parser_def = collection.get('parser')
            if parser_def is None:
                continue
            try:
                module = importlib.import_module('parser.%s' % (parser_def[0]))
                parser = getattr(module, parser_def[1])
                parser_dict[collection['name']] = parser
            except:
                logging.error('Load parser failed: %s.%s', *parser_def)
                raise
    return parser_dict, None


def __parse_snmp_func(data_path, fn, parsed_data_path, parser_dict, *args):
    result = {}
    hostname = fn[:-5]
    with open(opj(data_path, fn)) as f:
        data = json.load(f)
        for name, msg in data.items():
            if msg['status'] != 'success':
                continue
            parser = parser_dict.get(name)
            if parser:
                try:
                    result[name] = parser(msg['output'])
                except:
                    print(hostname)
                    raise
    parsed_fn = opj(parsed_data_path, fn)
    __save_json(result, parsed_fn)
    return hostname, result


def __parse(in_path, out_path, pre_stage, p_name, get_parser, parse_func):
    data_path = opj(in_path, p_name)
    if not os.path.isdir(data_path):
        return {}
    parsed_data_path = opj(out_path, p_name)
    parser_dict, group_commands = get_parser(pre_stage)
    pool = MPool()
    results = [pool.apply_async(parse_func,
                                (data_path,
                                 fn,
                                 parsed_data_path,
                                 parser_dict,
                                 group_commands))
               for fn in os.listdir(data_path)]
    pool.close()
    pool.join()
    parsed_data = [res.get() for res in results]
    return {k: v for k, v in parsed_data}


def parse(pre_stage=False):
    if pre_stage:
        stage = 3
        p_name = 'pre'
    else:
        stage = 6
        p_name = 'main'
    logging.info('Stage %s: Start parsing %s data', stage, p_name)
    # parse cli output
    parsed_data = __parse(RAW_CLI_PATH,
                          PARSED_CLI_PATH,
                          pre_stage,
                          p_name,
                          __get_cli_parser,
                          __parse_cli_func)
    if pre_stage:
        __save_json(parsed_data, PRE_PARSED_CLI_FN)
    logging.info('Stage %s CLI finished', stage)
    # parse snmp output
    parsed_data = __parse(RAW_SNMP_PATH,
                          PARSED_SNMP_PATH,
                          pre_stage,
                          p_name,
                          __get_snmp_parser,
                          __parse_snmp_func)
    if pre_stage:
        __save_json(parsed_data, PRE_PARSED_SNMP_FN)
    logging.info('Stage %s SNMP finished', stage)


def __analysis_one_device(hostname, data, all_methods):
    alarm_dict = {}
    for cmd, items in data.items():
        # logging.info('Analize %s %s', hostname, cmd)
        func = all_methods.get(cmd)
        if func:
            try:
                new_items, alarm_items = func(items, hostname)
                if new_items:
                    fn = '%s__%s.json' % (cmd, hostname)
                    __save_json(new_items, opj(ANALIZED_DATA_PATH, fn))
                    if alarm_items:
                        alarm_dict[cmd] = alarm_items
            except:
                logging.error('Analize error %s %s', hostname, cmd)
                # raise
    return hostname, alarm_dict


def analysis():
    logging.info('Start analize parsed data')
    all_methods = {}
    for f in os.listdir(opj(APP_PATH, 'analizer')):
        if not os.path.isdir(opj(APP_PATH, 'analizer', f)):
            continue
        try:
            module = importlib.import_module('analizer.%s.main' % f)
            methods = getattr(module, 'methods')
            all_methods.update(methods)
        except Exception as e:
            logging.error(e)
            pass
    try:
        shutil.rmtree(ANALIZED_DATA_PATH)
    except:
        pass
    os.mkdir(ANALIZED_DATA_PATH)

    all_results = []
    for parsed_path in (PARSED_CLI_PATH, PARSED_SNMP_PATH):
        if parsed_path == PARSED_SNMP_PATH:
            continue
        for sub_path in ('main', 'pre'):
            path = opj(parsed_path, sub_path)
            parsed_data = {}
            for fn in os.listdir(path):
                with open(opj(path, fn)) as f:
                    parsed_data[fn[:-5]] = json.load(f)

            pool = MPool()
            results = [pool.apply_async(__analysis_one_device,
                                        (hostname, data, all_methods))
                       for hostname, data in parsed_data.items()]
            results = [res.get() for res in results]
            all_results.append(results)
    __save_json(all_results, DAILY_ALARMED_FN)
    logging.info('Analize finished')


def advanced_analysis(n=None):
    files = sorted(os.listdir(opj(APP_PATH, 'advanced')))
    for f in files:
        if not f.endswith('.py'):
            continue
        if n and not f.startswith('%s_' % n):
            continue
        try:
            module = importlib.import_module('advanced.%s' % f.split('.')[0])
            func = getattr(module, 'main')
            func()
        except Exception as e:
            logging.error(e)


if __name__ == '__main__':
    options.define('s', default=0, type=int, help='run stage')
    options.define('n', default=None, type=str, help='advanced script id')
    options.define('d', default=True, type=bool,
                   help='debug mode, don\'t collect')
    options.parse_command_line()
    stage = options.options.s
    script_id = options.options.n
    DEBUG = options.options.d

    if stage == 0:
        backup_data_path()
        oid_dict = get_all_oids(True)
        cli_dict = get_all_commands(True)
        collect_snmp(True, oid_dict)
        collect_cli(True, cli_dict)
        parse(True)
        cli_dict = get_all_commands()
        collect_cli(False, cli_dict)
        parse()
        analysis()
        advanced_analysis()
    elif stage == 1:
        get_all_oids(True)
        get_all_commands(True)
    elif stage == 2:
        collect_snmp(True)
        collect_cli(True)
    elif stage == 3:
        parse(True)
    elif stage == 4:
        get_all_commands()
    elif stage == 5:
        collect_cli()
    elif stage == 6:
        parse()
    elif stage == 7:
        analysis()
    elif stage == 8:
        advanced_analysis(script_id)
    else:
        print('Invalid stage.')
