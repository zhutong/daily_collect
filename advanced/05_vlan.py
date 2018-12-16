import json
import logging
import re
from collections import defaultdict

import requests

from config import *

re_port = re.compile('Ethernet(\d+)/(\d+)$')

config_file = '/tmp/missed_vlan.txt'


def __get_device_info():
    rows = requests.get(DEVICE_INFO_URL).json()
    devices = {}
    for r in rows['data']:
        devices[r['hostname']] = r
    return devices


def __get_gateway(hostname):
    special_gateway = {
        'NFF1': 'NF70SW0A-F1-VDC2',
        'NFF2': 'NF70SW0A-F2-VDC4',
        'NFF3': 'NF70SW0A-F3-VDC3',
        'JDF2': 'JD70SW0A-F2-VDC4',
        'JDF3': 'JD70SW0A-F3-VDC5',
    }
    try:
        site = hostname[:2]
        zone = hostname.split('-')[1]
        return special_gateway.get(site+zone,
                                   site+'70SW0A-'+zone+'-VDC3')
    except:
        return None


def __filter_vlan(vlan, site):
    n = vlan['name']
    if 'FW' in n or 'monitor' in n or 'ternal' in n:
        return False
    if 'S1ToB5' in n or 'Temp_' in n:
        return False
    i = int(vlan['id'])
    if site == 'NF' and i > 1000:
        return False
    if site == 'JD' and i < 1006:
        return False
    return True


def get_vlan_set(vlan_list, ds=False, site=None):
    if ds:
        vlans = [v['id'] for v in vlan_list if __filter_vlan(v, site)]
    else:
        vlans = [v['id'] for v in vlan_list]
    return set(vlans)


def create_vlan_config(missed):
    device_dict = __get_device_info()
    lines = []
    hw_template = 'sys\r\n%squit\r\nsave\r\ny\r\n'
    ios_template = 'config t\r\n%swrite\r\n'
    nxos_template = 'config t\r\n%scopy running start\r\n'
    for hostname, vlans in missed:
        try:
            ip = device_dict[hostname]['ip']
        except:
            ip = 'unknown'
        lines.append('===')
        lines.append('%s (%s)' % (hostname, ip))
        one_config = ['vlan %s\r\n' % v for v in vlans]
        one_config = ''.join(one_config)
        if '91BL' in hostname:  # HW blade
            lines.append(hw_template % one_config)
        elif '50SW' in hostname or ('55SW' in hostname) or ('56SW' in hostname) or ('70SW' in hostname):
            lines.append(nxos_template % one_config)
        else:
            lines.append(ios_template % one_config)
    config = '\r\n'.join(lines)
    with open(config_file, 'w') as f:
        f.write(config)


def send_mail():
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']
    data = {
        "subject": "并行任务脚本 - 添加缺失的VLANs",
        "body_plain": "你好！\n\n请审阅附件。",
        "attach": [config_file],
        "receivers": receivers,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def main():
    logging.info('Analysis VLAN')
    ds_vlan = {}
    as_vlan = {}
    n7k_module_chips = {}
    path = opj(PARSED_CLI_PATH, 'main')
    for fn in os.listdir(path):
        hostname = fn[:-5]
        with open(opj(path, fn)) as f:
            data = json.load(f)
        if '91BL' in hostname:
            vlans = data.get('display vlan | in common', [])
        else:
            vlans = data.get('show vlan brief', [])
        if len(vlans) <= 1:
            continue
        # get device's vlan
        if __get_gateway(hostname) == hostname:
            site = hostname[:2]
            zone = hostname.split('-')[1]
            ds_vlan[site+zone] = get_vlan_set(vlans, True, site)
        elif '0A-' in hostname or '0B-' in hostname:
            continue
        else:
            as_vlan[hostname] = get_vlan_set(vlans)

    # check missed vlan
    missed_vlan_list = []
    for hostname in as_vlan:
        site = hostname[:2]
        zone = hostname.split('-')[1]
        ds_vlan_set = ds_vlan.get(site+zone)
        if ds_vlan_set:
            sw_vlan_set = as_vlan[hostname]
            missed_vlan = list(ds_vlan_set - sw_vlan_set)
            if missed_vlan:
                fn = 'show vlan brief__%s.json' % hostname
                with open(opj(ANALIZED_DATA_PATH, fn), 'w') as f:
                    json.dump([{'missed_vlan': dict(value=missed_vlan,
                                                    alarm=3)}],
                              f, indent=4)
                missed_vlan_list.append((hostname, missed_vlan))
    create_vlan_config(missed_vlan_list)
    send_mail()
