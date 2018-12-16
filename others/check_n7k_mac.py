import json
import logging
import re
import os
import time
from collections import defaultdict

import requests
from tornado.log import enable_pretty_logging
from jinja2 import Template

APP_URL = 'http://127.0.0.1/apps/tools/api/'
GET_MAIL_LIST_URL = '%sget_wl2_mail_list' % APP_URL
SEND_MAIL_URL = '%ssend_mail' % APP_URL
CLI_URL = 'http://127.0.0.1:8080/api/v1/sync/cli'

PATH = '/data/jd7k_mac_check'
CMD_FN = os.path.join(PATH, 'n7k_mac_check_cmd.json')
FE_FN = os.path.join(PATH, 'n7k_mac_fe.json')
CHECK_OUTPUT_FN = os.path.join(PATH, 'missed_mac.html')

re_bd = re.compile('\d+\s+(?P<vlan>\d+)\s+(?P<bd>\d+)')
re_mac = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                    '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+.*', re.I)
re_slot = re.compile('(?P<fe>\d+)\s+\d+\s+\d+\s+(?P<bd>\d+)'
                     '\s+(?P<mac>\w+\.\w+\.\w+)\s+', re.I)

body_template = '''
    <style>
        h4 {
            margin: 15px 0 0 0;
        }
        table {
            width: 100%;
            max-width: 100%;
            border: 1px solid #aaaaaa;
            border-spacing: 0;
            border-collapse: collapse;
            margin: 3px 0;
        }
        th {
            color: white;
            background-color: #337ab7;
        }
        th, td {
            text-align: center;
            line-height: 1.5;
            border: 1px solid #aaaaaa;
        }
    </style>
    <h3>嘉定N7K未同步网关MAC地址</h3>
    <table>
        <thead>
            {% for f in ('Hostname','VLAN', 'SLOT', 'FE', 'Missed MAC') %}
            <th>{{ f }}</th>
            {% endfor %}
        </thead>
        <tbody>
        {% for hostname, datas in alarm.items() %}
            {% for data in datas %}
            <tr>
                <td>{{ hostname }}</td>
                {% for f in ('vlan', 'slot', 'fe') %}
                <td>{{ data[f] }}</td>
                {% endfor %}
                <td>{{ ' | '.join(data['mac']) }}</td>
            </tr>
            {% endfor %}
        {% endfor %}
        </tbody>
    </table>'''


GW_MAC_PREFIXES = '0000.0c07', '0001.d7', '0023.e9', '000a.49', 'f415.63'


def __parse_bd(text):
    bd_dict = {}
    for m in re_bd.finditer(text):
        vlan, bd = m.groups()
        bd_dict[bd] = vlan
    return bd_dict


def __parse_mac(text):
    mac_dict = defaultdict(set)
    for m in re_mac.finditer(text):
        vlan, mac = m.groups()
        mac_dict[vlan].add(mac)
    return mac_dict


def __parse_slot_mac(hostname, text, bd_dict):
    slot_mac_dict = defaultdict(dict)
    for m in re_slot.finditer(text):
        fe, bd, mac = m.groups()
        try:
            vlan = bd_dict[bd]
        except KeyError:
            # logging.warning('FE: %s BD: %s MAC: %s', fe, bd, mac)
            continue
        if vlan in slot_mac_dict[fe]:
            slot_mac_dict[fe][vlan].append(mac)
        else:
            slot_mac_dict[fe][vlan] = [mac]
    return slot_mac_dict


def __is_not_today(full_fn, seconds):
    m_time = os.path.getmtime(full_fn)
    return (time.time() - m_time) > seconds


def collect(n7k_module_chips):
    logging.info('Start collecting')
    with open(CMD_FN) as f:
        commands = json.load(f)

    for h, c in commands.items():
        logging.info('Collect %s', h)
        params = dict(hostname=h, commands=c, wait=5)
        try:
            res = requests.post(CLI_URL, json=params)
            if res.status_code == 200:
                data = res.json()
                with open(os.path.join(PATH, 'O__%s.json' % h), 'w') as f:
                    json.dump(data, f, indent=4)
            else:
                raise
        except:
            logging.error('Collect failed')
    logging.info('Finish collecting')


def check(n7k_module_chips, hostname, fn):
    logging.info('check %s', hostname)
    try:
        with open(fn) as f:
            data = json.load(f)
        missed_mac = []
        fe_bd_mac_dict = {}
        for o in data['output']:
            cmd = o['command']
            txt = o['output']
            if 'vlan' in cmd:
                bd_dict = __parse_bd(txt)
            elif cmd == 'show mac address-table':
                mac_dict = __parse_mac(txt)
            else:
                slot = cmd.split()[-1]
                slot_mac_dict = __parse_slot_mac(hostname, txt, bd_dict)
                fe_bd_mac_dict[slot] = slot_mac_dict
        for fe_mac in n7k_module_chips[hostname]['fe']:
            vlan = fe_mac['vlan']
            macs = mac_dict[vlan]
            vlan_gw_macs = set(
                [m for m in macs if m.startswith(GW_MAC_PREFIXES)])
            if not vlan_gw_macs:
                continue
            for d in fe_mac['chips']:
                slot = d['slot']
                for chip in d['chips']:
                    fe = str(chip)
                    chip_vlan_macs = set(
                        fe_bd_mac_dict[slot][fe].get(vlan, []))
                    missed = vlan_gw_macs - chip_vlan_macs
                    if missed:
                        missed_mac.append(dict(vlan=vlan,
                                               slot=slot,
                                               fe=fe,
                                               mac=list(missed)))
    except:
        logging.warning('Check %s fail', hostname)
    return missed_mac


def send_mail(body):
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']
    data = {
        "subject": "Day2: 嘉定N7K未同步的网关MAC",
        'body_html': body,
        "receivers": receivers,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


if __name__ == '__main__':
    enable_pretty_logging()
    if __is_not_today(FE_FN, 12*3600):
        logging.error('Day2数据未更新！')
    else:
        with open(FE_FN) as f:
            n7k_module_chips = json.load(f)

        collect(n7k_module_chips)
        missed_mac_dict = {}
        for fn in os.listdir(PATH):
            if not fn.startswith('O__'):
                continue
            hostname = fn[3:-5]
            full_fn = os.path.join(PATH, fn)
            if __is_not_today(full_fn, 12*3600):
                logging.warning('%s data file timeout', hostname)
                continue
            missed_mac = check(n7k_module_chips, hostname, full_fn)
            if missed_mac:
                missed_mac_dict[hostname] = missed_mac

        mail_body = Template(body_template).render(alarm=missed_mac_dict)
        with open(os.path.join(PATH, CHECK_OUTPUT_FN), 'w') as f:
            f.write(mail_body)

        if missed_mac_dict:
            send_mail(mail_body)
