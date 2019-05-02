# -*- coding:utf-8 -*-

import json
import logging
import re
import os
import sys
from collections import defaultdict

from pprint import pprint as pp

from tornado.log import enable_pretty_logging


PATH = '/data/jd7k_mac_check/'
FE_FN = os.path.join(PATH, 'n7k_mac_fe.json')


re_BD = re.compile('\d+\s+(?P<vlan>\d+)\s+(?P<bd>\d+)')
re_MAC_PORT = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                         '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+'
                         '(\d+\s+F\s+F\s+|ip.*?\s+|\s)'
                         '(?P<port>\S+)', re.I)
re_FE_MAC = re.compile('(?P<fe>\d+)\s+\d+\s+\d+\s+(?P<bd>\d+)'
                       '\s+(?P<mac>\w+\.\w+\.\w+)\s+', re.I)


GW_MAC_PREFIXES = '0000.0c07', '0001.d7', '000a.49', '0023.e9', 'f415.63'


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
            # gen_vlan_mac = (m[0] for m in vlan_macs)
            gen_vlan_mac = (m[0]
                            for m in vlan_macs if m[0].startswith(GW_MAC_PREFIXES))
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
                    if p=='vPC' or s_p is None:
                        continue
                    if s_p != p:
                        key = '%s@%s' % (m, vlan)
                        sw_errored_mac[key].append((slot, p, s_p))
    except:
        raise
        logging.warning('Check %s fail', hostname)
    return hw_missed_mac, sw_errored_mac


if __name__ == '__main__':
    enable_pretty_logging()

    with open(FE_FN) as f:
        n7k_module_chips = json.load(f)

    for fn in os.listdir(PATH):
        if not fn.startswith('O__'):
            continue
        full_fn = os.path.join(PATH, fn)
        hostname = fn[3:-5]
        hw_missed_mac, sw_errored_mac = check_one(
            n7k_module_chips, hostname, full_fn)
        # if(hw_missed_mac):
        #     logging.error(hostname)
        #     pp(hw_missed_mac)
        #     break
        if(sw_errored_mac):
            logging.error(hostname)
            pp(sw_errored_mac)
            # break
