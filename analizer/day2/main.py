# -*- coding:utf-8 -*-

import json
import os
import time
import logging

from collections import defaultdict

import requests

from ..tools import *
from config import opj, PARSED_SNMP_PATH, PARSED_CLI_PATH, LAST_OUTPUT_DATA_PATH


def login(datas, *args):
    alarms = (
        ('Connection_Closed', 4),
        ('Timeout', 4),
        ('TIMEOUT', 4),
        ('LOGIN_FAILED', 3),
        ('Wrong username', 3),
        ('Hostname not match', 3),
        ('ip address not found', 3),
        ('CONNECTION_CLOSED', 4),
    )
    alarm_items = []
    for d in datas:
        v = d['msg']
        if v.startswith('<'):
            v = v[1:-1]
        alarm_level = contains(v, alarms) or 0
        new_value = {'msg': dict(value=v, alarm=alarm_level)}
        alarm_items.append(new_value)
    return alarm_items, alarm_items


def interface(datas, *args):
    alarms = (100000, 5), (10000, 4), (1000, 3), (10, 2)
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k in ('crc', 'rx_drop', 'tx_drop', 'rx_error', 'tx_error'):
                alarm_level = great_then(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def interface_status(datas, *args):
    alarms = (
        (('err-disabled',
          'secViolEr',
          'linkFlapE',
          'faulty'), 5),
        (('xcvrSpeed',
          'suspended',
          'sfpInvali'), 4),
        (('inactive',
          ), 3)
    )
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k == 'status':
                alarm_level = belongs(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def __get_down_interfaces():
    ignores = ('disabled', 'sfpAbsent', 'xcvrAbsen',
               'notconnect', 'notconnec', 'down')
    all_down_interfaces = {}
    path = opj(PARSED_CLI_PATH, 'main')
    for fn in os.listdir(path):
        with open(opj(path, fn)) as f:
            data = json.load(f).get('show interface status')
            if not data:
                continue
            down_interfaces = []
            for r in data:
                if r['status'] in ignores:
                    down_interfaces.append(r['interface'])
            all_down_interfaces[fn[:-5]] = down_interfaces
    return all_down_interfaces


def __get_down_interfaces_snmp():
    all_down_interfaces = {}
    path = opj(PARSED_SNMP_PATH, 'pre')
    for fn in os.listdir(path):
        with open(opj(path, fn)) as f:
            data = json.load(f).get('if_table')
            if not data:
                continue
            down_interfaces = []
            for r in data:
                if r['operStatus'] == 'down':
                    down_interfaces.append(r['ifDescr'])
            all_down_interfaces[fn[:-5]] = down_interfaces
    return all_down_interfaces


down_interfaces = __get_down_interfaces_snmp()


def interface_trans(datas, hostname, *args):
    alarms = ('(4)', 4), ('(3)', 3)
    processed = []
    alarm_items = []
    for d in datas:
        if_name = d['interface']
        if if_name in down_interfaces.get(hostname, []):
            continue
        new_value = {}
        for k, v in d.items():
            if k != 'interface':
                try:
                    v1 = float(v.split()[0])
                except:
                    v1 = v
                new_value[k] = dict(value=v1)
                alarm_level = contains(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
                elif '97SN' in hostname and k == 'rx_pwr':
                    try:
                        if v1 > 1 or v1 < -6:
                            new_value[k]['alarm'] = 2
                            alarm_items.append(new_value)
                    except:
                        pass
            else:
                new_value[k] = dict(value=v)
        processed.append(new_value)
    return processed, alarm_items


def n7k_slot_flash(datas, *args):
    alarms = ('0xf0 UU UU UU UU', 5),
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k in ('slot_5_raid', 'slot_6_raid'):
                alarm_level = not_equals(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def n7k_log_space(datas, *args):
    alarms = (99, 4), (95, 3)
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k in ('slot_5_log_space', 'slot_6_log_space'):
                alarm_level = great_then(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def n7k_tacacs_memory(datas, *args):
    alarms = (90, 4), (85, 3)
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k == 'pecentage':
                alarm_level = great_then(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def __get_last_fex_data(hostname):
    fex = {}
    try:
        with open(opj(LAST_OUTPUT_DATA_PATH, 'parsed', 'cli', 'main', '%s.json' % hostname)) as f:
            data = json.load(f)['attach fex']
        for d in data:
            fex[d['fex']] = d
    except:
        logging.warning('No last fex data: %s', hostname)
    return fex


def fex_pwr_rx_crc(datas, hostname, *args):
    pw_alarms = ('OK', 5),
    crc_alarms = (1000000, 5), (100000, 4), (10000, 3)
    processed = []
    alarm_items = []
    last_fex_dict = __get_last_fex_data(hostname)
    for d in datas:
        new_value = {}
        last_fex = last_fex_dict.get(d['fex'])
        for k, v in d.items():
            new_value[k] = dict(value=v)
            if k in ('pw1_status', 'pw2_status'):
                alarm_level = not_equals(v, pw_alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
            elif 'RX_CRC' in k:
                try:
                    v0 = last_fex[k]
                    increased = v - v0
                except:
                    increased = 0
                alarm_level = great_then(increased, crc_alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def n5k_logic(datas, hostname, *args):
    thresholds = {
        '50': 12500,
        '55': 16000,
        '56': 32000
    }
    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
            t = thresholds[hostname[2:4]]
            if int(v) > t:
                new_value[k]['alarm'] = 4
                alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def module(datas, *args):
    s_alarms = (('Fail', 'PwrDown'), 5),
    d_alarms = (('Fail',), 4),

    processed = []
    alarm_items = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            alarmed = False
            new_value[k] = dict(value=v)
            if k == 'status':
                alarm_level = belongs(v, s_alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
                    alarmed = True
            elif k == 'diag' and not alarmed:
                alarm_level = belongs(v, d_alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


def inventory(datas, *args):
    processed = []
    for d in datas:
        new_value = {}
        for k, v in d.items():
            new_value[k] = dict(value=v)
        processed.append(new_value)
    return processed, []


def __get_last_mds_data(hostname, cmd):
    default_data = [{
        "F16_IPA_IPA0_CNT_BAD_CRC": 0,
        "F16_IPA_IPA0_CNT_CORRUPT": 0,
        "F16_IPA_IPA1_CNT_BAD_CRC": 0,
        "F16_IPA_IPA1_CNT_CORRUPT": 0,
        "INTERNAL_ERROR_CNT": 0,
        "HIGH_IN_BUF_PKT_CRC_ERR_COUNT": 0
    }]
    try:
        with open(opj(LAST_OUTPUT_DATA_PATH, 'parsed', 'cli', 'main', '%s.json' % hostname)) as f:
            return json.load(f).get(cmd, default_data)
    except:
        return default_data


def mds_asic_crc_err(datas, hostname, *args):
    crc_alarms = (10000, 5), (1000, 4),  (10, 3), (0, 2)
    last_mds_dict = __get_last_mds_data(hostname,
                                        'show hardware internal errors all')[0]
    alarm_items = []
    processed = []
    new_value = {}
    check_counters = list(last_mds_dict.keys())
    alarmed = False
    for each_counter in check_counters:
        old_value, current_value = last_mds_dict[each_counter], datas[0][each_counter]
        increased = current_value - old_value
        new_value[each_counter] = dict(value=current_value)
        alarm_level = great_then(increased, crc_alarms)
        if alarm_level:
            new_value[each_counter]['alarm'] = alarm_level
            new_value[each_counter]['increased'] = increased
            alarm_items.append(new_value)
    processed.append(new_value)
    return processed, alarm_items


def __get_mds_down_port_pair():
    start = time.time() - 3600*24
    all_down_interfaces = {}
    path = opj(PARSED_CLI_PATH, 'main')
    for fn in os.listdir(path):
        if '97SN' not in fn:
            continue
        with open(opj(path, fn)) as f:
            rows = json.load(f).get(
                "show logging log | begin \"2019 \" | grep \"Link failure loss of signal\"")
        if not rows:
            continue
        events = defaultdict(list)
        for r in rows:
            s = r['timestamp']
            i = time.mktime(time.strptime(s, "%Y %b %d %H:%M:%S"))
            if i < start:
                continue
            events[r['interface']].append(dict(int_time=i, str_time=s))
        if events:
            all_down_interfaces[fn[:-5]] = events
    return all_down_interfaces


mds_down_port_pair = __get_mds_down_port_pair()
MDS_ONBOARD_FN = '/data/mds_onboard_err/last_mds_onboard_%s.json'


def __get_last_mds_onboard(hostname):
    try:
        with open(MDS_ONBOARD_FN % hostname) as f:
            return json.load(f)
    except:
        return {}


def __save_last_mds_onboard(hostname, data):
    with open(MDS_ONBOARD_FN % hostname, 'w') as f:
        json.dump(data, f, indent=4)


def mds_onboard_err(datas, hostname, *args):
    cmd = 'show logging onboard error-stats'
    onboard_alarms = (1000, 5), (100, 4),  (10, 3), (0, 2)
    alarm_items, processed = [], []
    last_onboard = __get_last_mds_onboard(hostname)
    for d in datas:
        port = d['interface']
        err_cnt = d['onboard_err']
        new_value = dict(interface=dict(value=port),
                         onboard_err=dict(value=err_cnt))
        if port not in mds_down_port_pair.get(hostname, {}):
            old_err_cnt = last_onboard.get(port, 0)
            increased = err_cnt - old_err_cnt
            alarm_level = great_then(increased, onboard_alarms)
            if alarm_level:
                new_value['onboard_err']['alarm'] = alarm_level
                new_value['onboard_err']['increased'] = increased
                alarm_items.append(new_value)
        processed.append(new_value)
        last_onboard[port] = err_cnt
    __save_last_mds_onboard(hostname, last_onboard)
    return processed, alarm_items


def mds_interface_err_counter(datas, hostname, *args):
    alarms = (100000, 5), (10000, 4), (1000, 3), (10, 2)
    processed = []
    alarm_items = []
    for d in datas:
        port = d['interface']
        new_value = dict(interface=dict(value=port))
        pair_down = port in mds_down_port_pair.get(hostname, {})

        for k, v in d.items():
            if k != 'interface':
                new_value[k] = dict(value=v)
                if pair_down:
                    continue
                alarm_level = great_then(v, alarms)
                if alarm_level:
                    new_value[k]['alarm'] = alarm_level
                    alarm_items.append(new_value)
        processed.append(new_value)
    return processed, alarm_items


methods = {
    'login': login,
    'show interface': interface,
    'show interface trans detail': interface_trans,
    'show interface status': interface_status,
    'show processes memory | in taca': n7k_tacacs_memory,
    'slot 5 show system internal raid': n7k_slot_flash,
    'slot 6 show system internal raid': n7k_slot_flash,
    'slot 5 show system internal flash': n7k_log_space,
    'slot 6 show system internal flash': n7k_log_space,
    'attach fex': fex_pwr_rx_crc,
    'show module': module,
    'show inventory': inventory,
    'show hardware internal errors all': mds_asic_crc_err,
    'show logging onboard error-stats': mds_onboard_err,
    'show interface detail-counters': mds_interface_err_counter,
    'show spanning-tree summary total | in vlans': n5k_logic,
}
