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
re_MAC = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                    '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+.*', re.I)
re_MAC_PORT = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                    '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+.*', re.I)
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
    mac_dict = defaultdict(set)
    for m in re_MAC.finditer(text):
        vlan, mac = m.groups()
        mac_dict[vlan].add(mac)
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

        hw_missed_mac = defaultdict(list)
        sw_missed_mac = defaultdict(list)
        # check slot software mac entry
        slot_vlan_chips = n7k_module_chips[hostname]
        for vlan, slot_dict in slot_vlan_chips.items():
            vlan_macs = global_mac_dict[vlan]
            # vlan_mac_set = set(vlan_macs)
            vlan_gw_mac_set = set(
                [m for m in vlan_macs if m.startswith(GW_MAC_PREFIXES)])
            if not vlan_gw_mac_set:
                # logging.warn('%s no GW mac for vlan: %s', hostname, vlan)
                continue
            for slot, fes in slot_dict.items():
                for fe in fes:
                    fe = str(fe)
                    chip_vlan_mac_set = set(
                        fe_bd_mac_dict[slot][fe].get(vlan, []))
                    # missed = vlan_mac_set - chip_vlan_macs
                    missed = vlan_gw_mac_set - chip_vlan_mac_set
                    for m in missed:
                        key = '%s@%s' % (m, vlan)
                        hw_missed_mac[key].append('%s/%s' % (slot, fe))
        # check slot software mac entry
        for slot, slot_dict in slot_sw_mac_dict.items():
            for vlan, sw_mac_dict in slot_dict.items():
                missed =  global_mac_dict[vlan] - sw_mac_dict
                for m in missed:
                    key = '%s@%s' % (m, vlan)
                    sw_missed_mac[key].append(slot)        
    except:
        raise
        logging.warning('Check %s fail', hostname)
    return hw_missed_mac, sw_missed_mac


if __name__ == '__main__':
    enable_pretty_logging()

    with open(FE_FN) as f:
        n7k_module_chips = json.load(f)

    for fn in os.listdir(PATH):
        if not fn.startswith('O__'):
            continue
        full_fn = os.path.join(PATH, fn)
        hostname = fn[3:-5]
        hw_missed_mac, sw_missed_mac = check_one(n7k_module_chips, hostname, full_fn)
        # if(hw_missed_mac):
        #     logging.error(hostname)
        #     pp(hw_missed_mac)
        #     break
        if(sw_missed_mac):
            logging.error(hostname)
            pp(sw_missed_mac)
