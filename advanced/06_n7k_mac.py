import json
import logging
import re
from collections import defaultdict

import requests

from config import *

re_port = re.compile('Ethernet(\d+)/(\d+)$')

MAC_FE_FILE = '/data/n7k_mac_check/n7k_mac_fe.json'
CHECK_CMD_FILE = '/data/n7k_mac_check/n7k_mac_check_cmd.json'
F5_GW_MAC_FILE = '/data/n7k_mac_check/f5_mac.json'
L3_PORT_FILE = '/tmp/l3_interface.json'
CHECK_SOFTWARE_CMD = 'show mac address-table {slot}'
CHECK_HARDWARE_CMD = 'show hardware mac address-table {slot}'
CHECK_CONSYSTENCY_CMD = 'show forwarding consistency l2 {slot}'


def get_module_chip(ports, down_ports, m1):
    data = defaultdict(list)
    slots = []
    for p in ports:
        if p in down_ports:
            continue
        r = re_port.match(p)
        if r:
            slot, port = r.groups()
            slots.append(slot)
            if m1:
                data[slot].append(0)
            else:
                data[slot].append((int(port)-1)//4)
    # return slots, [dict(slot=s, chips=list(set(data[s]))) for s in data]
    return slots, {s: list(set(data[s])) for s in data}


def check_command(n7k, slots, m1):
    lines = []
    lines.append('show vlan internal bd-info vlan-to-bd all-vlan')
    lines.append('show mac address-table')
    for s in slots:
        lines.append(CHECK_SOFTWARE_CMD.format(slot=s))
        lines.append(CHECK_HARDWARE_CMD.format(slot=s))
        if m1:
            lines.append(CHECK_CONSYSTENCY_CMD.format(slot=s))
    return lines


def main():
    logging.info('Analysis N7K MAC')
    n7k_module_chips = {}
    commands = {}
    path = opj(PARSED_CLI_PATH, 'main')
    for fn in os.listdir(path):
        hostname = fn[:-5]
        if 'JD70SW' not in hostname and 'NF70SW' not in hostname:
            continue
        # if '0A-' in hostname or '0B-' in hostname:
        #     continue
        if 'VDC1' in hostname or 'C0' in hostname:
            continue
        is_M1 = hostname.startswith('NF70SW') and ('-B6' not in hostname)
        if not is_M1:
            is_M1 = ('JD70SW0A-T0' in hostname) or ('JD70SW0B-T0' in hostname)
        with open(opj(path, fn)) as f:
            data = json.load(f)
        ports = data.get('show interface status', [])
        down_ports = [p['interface']
                      for p in ports if p['status'] != 'connected']
        vlans = data.get('show vlan brief', [])
        all_slots = []
        # module_chips = []
        module_chips = {}
        for v in vlans[1:]:
            slots, chips = get_module_chip(v['ports'], down_ports, is_M1)
            all_slots.extend(slots)
            # module_chips.append(dict(vlan=v['id'], chips=chips))
            module_chips[v['id']] = chips
        slots = sorted(list(set(all_slots)), key=lambda x: int(x))
        if not slots:
            continue
        # n7k_module_chips[hostname] = dict(
        #     slots=slots, fe=module_chips)
        n7k_module_chips[hostname] = module_chips
        commands[hostname] = check_command(hostname, slots, is_M1)
    with open(MAC_FE_FILE, 'w') as f:
        json.dump(n7k_module_chips, f)
    with open(CHECK_CMD_FILE, 'w') as f:
        json.dump(commands, f, indent=4)

    with open(L3_PORT_FILE) as f:
        data = json.load(f)

    f5_mac = []
    for d, ip_dict in data.items():
        if 'SL' not in d:
            continue
        for ip, info in ip_dict.items():
            # and 'internal' in info['interface']:
            if info['operStatus'] == 'up':
                mac = info['macAddress']
                if mac == '0000.0000.0000':
                    continue
                f5_mac.append(info['macAddress'])
    with open(F5_GW_MAC_FILE, 'w') as f:
        json.dump(list(set(f5_mac)), f, indent=2)
