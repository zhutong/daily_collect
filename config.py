# -*- coding:utf-8 -*-

import os
import shutil
from os.path import join as opj

# URL定义
IP = '127.0.0.1'
APP_URL = 'http://%s/apps/' % IP
APP_URL = 'http://%s:9116/apps/' % IP
CLI_COLLECTOR_URL = 'http://%s:8080/api/v1/sync/cli' % IP
SNMP_COLLECTOR_URL = 'http://%s:8080/api/v1/sync/snmp' % IP
DEVICE_INFO_URL = '%sdevice_center/api/device_list' % APP_URL
DEVICE_FILTER_URL = '%sdevice_center/api/filter_device?' % APP_URL
GET_MAIL_LIST_URL = '%stools/api/get_wl_mail_list_by_tag?tag=wl1' % APP_URL
SEND_MAIL_URL = '%stools/api/send_mail' % APP_URL
SEND_RAW_SYSLOG_URL = '%stools/api/send_raw_syslog' % APP_URL
SEND_CPE_SYSLOG_URL = '%stools/api/send_cpe_syslog' % APP_URL


# 路径及文件定义
APP_PATH = os.path.dirname(os.path.abspath(__file__))
DEFINE_PATH = opj(APP_PATH, 'define')
DEVICE_GROUP_DEFINE_FN = opj(DEFINE_PATH, 'device_group.json')
PRE_COMMAND_DEFINE_FN = opj(DEFINE_PATH, 'pre_command.json')
COMMAND_DEFINE_FN = opj(DEFINE_PATH, 'command.json')
PRE_OID_DEFINE_FN = opj(DEFINE_PATH, 'pre_oid.json')
OID_DEFINE_FN = opj(DEFINE_PATH, 'oid.json')
DAILY_ALARMED_FN = '/tmp/daily_alarmed.json'

DATA_PATH = '/data/daily_data'
TEMP_PATH = opj(DATA_PATH, 'temp')
OUTPUT_DATA_PATH = opj(DATA_PATH, 'output')
LAST_OUTPUT_DATA_PATH = opj(DATA_PATH, 'last_output')
RAW_DATA_PATH = opj(OUTPUT_DATA_PATH, 'raw')
RAW_CLI_PATH = opj(RAW_DATA_PATH, 'cli')
RAW_SNMP_PATH = opj(RAW_DATA_PATH, 'snmp')
PARSED_DATA_PATH = opj(OUTPUT_DATA_PATH, 'parsed')
PARSED_CLI_PATH = opj(PARSED_DATA_PATH, 'cli')
PARSED_SNMP_PATH = opj(PARSED_DATA_PATH, 'snmp')
ANALIZED_DATA_PATH = '/data/day2'

JOB_TEMP_FN = opj(TEMP_PATH, 'job.txt')
PRE_COMMAND_TEMP_FN = opj(TEMP_PATH, 'pre_commands.json')
COMMAND_TEMP_FN = opj(TEMP_PATH, 'commands.json')
PRE_PARSED_CLI_FN = opj(TEMP_PATH, 'pre_parsed_cli.json')
PRE_PARSED_SNMP_FN = opj(TEMP_PATH, 'pre_parsed_snmp.json')
PRE_OID_TEMP_FN = opj(TEMP_PATH, 'pre_oid.json')
OID_TEMP_FN = opj(TEMP_PATH, 'oids.json')


def create_dirs():
    os.mkdir(OUTPUT_DATA_PATH)
    os.mkdir(RAW_DATA_PATH)
    os.mkdir(PARSED_DATA_PATH)
    for p in (RAW_CLI_PATH, RAW_SNMP_PATH, PARSED_CLI_PATH, PARSED_SNMP_PATH):
        os.mkdir(p)
        for sub_p in ('pre', 'main'):
            os.mkdir(opj(p, sub_p))


def backup_data_path():
    try:
        shutil.rmtree(LAST_OUTPUT_DATA_PATH)
    except:
        pass
    try:
        shutil.move(OUTPUT_DATA_PATH, LAST_OUTPUT_DATA_PATH)
    except:
        pass
    create_dirs()


if not os.path.exists(ANALIZED_DATA_PATH):
    os.mkdir(ANALIZED_DATA_PATH)
if not os.path.exists(DATA_PATH):
    os.mkdir(DATA_PATH)
    os.mkdir(TEMP_PATH)
    create_dirs()

# 时戳格式，采集线程数
TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
MAX_SNMP_WORKERS = 300
MAX_CLI_WORKERS = 120
