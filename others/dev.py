# -*- coding:utf-8 -*-

import json
import logging
import re
import os
import sys
import time
from collections import defaultdict
from multiprocessing.dummy import Pool

from pprint import pprint as pp

import requests
from tornado.log import enable_pretty_logging


TOOLS_APP_URL = 'http://127.0.0.1/apps/tools/api/'
GET_MAIL_LIST_URL = '%sget_wl_mail_list_by_tag?tag=wl1' % TOOLS_APP_URL
SEND_MAIL_URL = '%ssend_mail' % TOOLS_APP_URL
SEND_CPE_SYSLOG_URL = '%ssend_cpe_syslog' % TOOLS_APP_URL
CLI_URL = 'http://127.0.0.1:8080/api/v1/sync/cli'
CREDENTIAL_URL = 'http://127.0.0.1:8080/api/v1/credential'


PATH = '/data/n7k_mac_check/'
CMD_FN = os.path.join(PATH, 'n7k_mac_check_cmd.json')
FE_FN = os.path.join(PATH, 'n7k_mac_fe.json')
LAST_MISSED_FN = os.path.join(PATH, 'last_missed.json')
LAST_ERRORED_FN = os.path.join(PATH, 'last_errored.json')
CHECK_OUTPUT_FN = os.path.join(PATH, 'missed_mac.html')


re_BD = re.compile('\d+\s+(?P<vlan>\d+)\s+(?P<bd>\d+)')
re_MAC_PORT = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                         '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+'
                         '(\d+\s+F\s+F\s+|ip.*?\s+|\s)'
                         '(?P<port>\S+)', re.I)
re_FE_MAC = re.compile('(?P<fe>\d+)\s+\d+\s+\d+\s+(?P<bd>\d+)'
                       '\s+(?P<mac>\w+\.\w+\.\w+)\s+', re.I)

errored_template = u'''
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
        th,
        td {
            text-align: center;
            line-height: 1.5;
            border: 1px solid #aaaaaa;
        }
        .alarm {
            background: orange;
            color: white;
        }
    </style>
    <h3>N7K Error MAC</h3>
    <table>
        <thead>
            <th>Hostname</th>
            <th>MAC@Vlan</th>
            <th>Slot</th>
            <th>Port@Slot</th>
            <th>Port@Engine</th>
        </thead>
        <tbody>
'''

missed_template = u'''
    </tbody></table>
    <h3>N7K UNSYNC MAC</h3>
    <table>
        <thead>
            <th>Hostname</th>
            <th>Missed MAC@Vlan</th>
            <th>SLOT/FEs</th>
            <th>Last2Days</th>
        </thead>
        <tbody>
    '''


GW_MAC_PREFIXES = '0000.0c07', '0001.d7', '000a.49', '0023.e9', 'f415.63'


def __is_not_today(full_fn, seconds):
    if not DEPLOYED:
        return False
    m_time = os.path.getmtime(full_fn)
    return (time.time() - m_time) > seconds


def __collect(param):
    h = param['hostname']
    logging.info('Collect %s', h)
    try:
        res = requests.post(CLI_URL, json=param)
        if res.status_code == 200:
            data = res.json()
            with open(os.path.join(PATH, 'O__%s.json' % h), 'w') as f:
                json.dump(data, f, indent=4)
        else:
            raise
    except:
        logging.error('Collect %s failed', h)


def __parse_bd(text):
    bd_dict = {}
    for m in re_BD.finditer(text):
        vlan, bd = m.groups()
        bd_dict[bd] = vlan
    return bd_dict


def __parse_mac(text):
    mac_dict = defaultdict(list)
    for m in re_MAC_PORT.finditer(text):
        vlan, mac, _, port = m.groups()
        mac_dict[vlan].append((mac, port))
    return mac_dict


def __parse_fe_mac(hostname, text, bd_dict):
    slot_mac_dict = defaultdict(dict)
    for m in re_FE_MAC.finditer(text):
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


def __mac_tuple2mac_dict(mac_tuple):
    mac_dict = defaultdict(dict)
    for vlan, mac_ports in mac_tuple.items():
        for mac, port in mac_ports:
            mac_dict[vlan][mac] = port
    return mac_dict


def collect():
    logging.info('Start collecting')
    with open(CMD_FN) as f:
        commands = json.load(f)
    pool = Pool(4)
    params = []
    for h, c in commands.items():
        p = dict(hostname=h, commands=c, wait=5)
        params.append(p)
    pool.map(__collect, params)
    pool.close()
    pool.join()
    logging.info('Finish collecting')


def check_one(n7k_module_chips, hostname, fn):
    try:
        with open(fn) as f:
            data = json.load(f)

        fe_bd_mac_dict = {}
        slot_sw_mac_dict = {}
        for o in data['output']:
            cmd = o['command']
            txt = o['output']
            if 'vlan' in cmd:
                bd_dict = __parse_bd(txt)
            elif cmd == 'show mac address-table':
                global_mac_dict = __parse_mac(txt)
            elif cmd.startswith('show mac address-table '):
                slot_sw_mac_dict[cmd.split()[-1]] = __parse_mac(txt)
            elif cmd.startswith('show hardware'):
                slot_fe_mac_dict = __parse_fe_mac(hostname, txt, bd_dict)
                fe_bd_mac_dict[cmd.split()[-1]] = slot_fe_mac_dict

        # check slot software mac entry
        hw_missed_mac = defaultdict(list)
        slot_vlan_chips = n7k_module_chips[hostname]
        for vlan, slot_dict in slot_vlan_chips.items():
            vlan_macs = global_mac_dict[vlan]
            if GW_ONLY:
                gen_vlan_mac = (m[0] for m in vlan_macs
                                if m[0].startswith(GW_MAC_PREFIXES))
            else:
                gen_vlan_mac = (m[0] for m in vlan_macs)
            vlan_mac_set = set(gen_vlan_mac)
            if not vlan_mac_set:
                # logging.warn('%s no GW mac for vlan: %s', hostname, vlan)
                continue
            for slot, fes in slot_dict.items():
                for fe in fes:
                    fe = str(fe)
                    chip_vlan_mac_set = set(
                        fe_bd_mac_dict[slot][fe].get(vlan, []))
                    missed = vlan_mac_set - chip_vlan_mac_set
                    for m in missed:
                        key = '%s@%s' % (m, vlan)
                        hw_missed_mac[key].append('%s/%s' % (slot, fe))

        # check slot software mac entry
        sw_errored_mac = defaultdict(list)
        global_vlan_mac_dict = __mac_tuple2mac_dict(global_mac_dict)
        for slot, slot_dict in slot_sw_mac_dict.items():
            slot_vlan_mac_dict = __mac_tuple2mac_dict(slot_dict)
            for vlan, g_mac_dict in global_vlan_mac_dict.items():
                s_mac_dict = slot_vlan_mac_dict[vlan]
                for m, p in g_mac_dict.items():
                    s_p = s_mac_dict.get(m)
                    if p == 'vPC' or s_p is None:
                        continue
                    if s_p != p:
                        key = '%s@%s' % (m, vlan)
                        sw_errored_mac[key].append((slot, p, s_p))
    except:
        raise
        logging.warning('Check %s fail', hostname)
    return hw_missed_mac, sw_errored_mac


def report(missed_mac_dict, errored_mac_dict):
    try:
        with open(LAST_MISSED_FN) as f:
            last_missed = json.load(f)
    except:
        last_missed = {}

    html_lines = [errored_template]
    scripts = defaultdict(list)

    for hostname, datas in errored_mac_dict.items():
        for m, errs in datas.items():
            scripts[hostname].append(m)
            for err in errs:
                html_lines.append('<tr><td>%s</td>' % hostname)
                html_lines.append('<td>%s</td>' % m)
                html_lines.append('<td>%s</td><td>%s</td><td>%s</td>' % tuple(err))
    html_lines.append(missed_template)
    for hostname, datas in missed_mac_dict.items():
        for m, fes in datas.items():
            if m in last_missed.get(hostname, {}):
                html_lines.append('<tr class="alarm">')
                last2days = 'Y'
                scripts[hostname].append(m)
            else:
                html_lines.append('<tr>')
                last2days = 'N'
            html_lines.append('<td>%s</td>' % hostname)
            html_lines.append('<td>%s</td>' % m)
            html_lines.append('<td>%s</td>' % ', '.join(fes))
            html_lines.append('<td>%s</td></tr>' % last2days)
    html_lines.append('</tbody></table>')
    mail_body = '\n'.join(html_lines)

    n7k_list = []
    res = requests.get(CREDENTIAL_URL)
    devices = res.json()['device_info']
    syslogs = []
    for hostname, macs in scripts.items():
        device = devices[hostname]
        ip = device['ip']
        content = '%s MAC not sync: [%s]' % (hostname, '; '.join(macs))
        item = dict(cpe_name='N7K',
                    alert_group='N7K-5-MAC_NOT_SYNC',
                    level=7,
                    ip=ip,
                    content=content)
        syslogs.append(item)

    return mail_body, syslogs


def send_syslog(syslogs):
    for s in syslogs:
        requests.post(SEND_CPE_SYSLOG_URL, json.dumps(s))


def send_mail(body):
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']
    receivers.append('icbc_mds@cisco.com')
    data = {
        "subject": "Day2: 嘉定N7K未同步的网关MAC",
        'body_html': body,
        "receivers": receivers,
        # "attach": [CLEAR_SCRIPT_FN]
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def ana():
    with open(FE_FN) as f:
        n7k_module_chips = json.load(f)

    missed_mac_dict = {}
    errored_mac_dict = {}
    for fn in os.listdir(PATH):
        if not fn.startswith('O__'):
            continue
        full_fn = os.path.join(PATH, fn)
        hostname = fn[3:-5]
        hw_missed_mac, sw_errored_mac = check_one(
            n7k_module_chips, hostname, full_fn)
        if(hw_missed_mac):
            missed_mac_dict[hostname] = hw_missed_mac
            logging.error(hostname)
            pp(hw_missed_mac)
            # break
        if(sw_errored_mac):
            errored_mac_dict[hostname] = sw_errored_mac
            logging.error(hostname)
            pp(sw_errored_mac)
            # break

    # save today's data as last missed data
    with open(LAST_MISSED_FN, 'w') as f:
        json.dump(missed_mac_dict, f, indent=4)
    with open(LAST_ERRORED_FN, 'w') as f:
        json.dump(errored_mac_dict, f, indent=4)

    return missed_mac_dict, errored_mac_dict


enable_pretty_logging()
GW_ONLY = True
DEPLOYED = True and False


if __name__ == '__main__':

    if DEPLOYED:
        if __is_not_today(FE_FN, 12*3600):
            logging.error('Day2数据未更新！')
            sys.exit(1)
        collect()
        sys.exit(1)

    if DEPLOYED:
        missed_mac_dict, errored_mac_dict = ana()
        sys.exit(1)
    else:
        with open(LAST_MISSED_FN) as f:
            missed_mac_dict = json.load(f)
        with open(LAST_ERRORED_FN) as f:
            errored_mac_dict = json.load(f)

    mail_body, syslogs = report(missed_mac_dict, errored_mac_dict)
    pp(syslogs)
    with open(os.path.join(PATH, CHECK_OUTPUT_FN), 'w') as f:
        f.write(mail_body)
    sys.exit(1)

    if DEPLOYED and missed_mac_dict:
        send_mail(mail_body)
        # send_syslog(syslogs)
