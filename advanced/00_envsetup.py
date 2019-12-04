########################################
#  生成交换机端口状态信息
#  生成ARP/MAC信息
#  推送至环境搭建工具
#  推送至交换机端口利用率统计工具
########################################

import json
import logging
from collections import defaultdict

import requests

from config import *
from .modules.portpairtools import get_port_pair_id, regulate_port_name


ENVSETUP_API_URL = APP_URL + 'envsetup/api/sync_switch_info'
PORT_STATISTIC_URL = APP_URL + 'port_statistic/api/update'

admin_down = ('disabled', 'sfpAbsent', 'xcvrAbsen')
operate_down = ('notconnect', 'notconnec', 'down')

PRE_PATH = opj(PARSED_CLI_PATH, 'pre')
MAIN_PATH = opj(PARSED_CLI_PATH, 'main')


def get_fex_speed_and_location():
    logging.info('Analysis fex speed & location')

    fex_speed = {}
    fex_location = {}
    for fn in os.listdir(PRE_PATH):
        hostname = fn[:-5]
        location = []
        p = opj(PRE_PATH, fn)
        with open(p) as f:
            d = json.load(f).get('show fex', [])
            for i in d:
                speed = 10000 if '-10GE' in i['model'] else 1000
                fex_speed[(hostname, i['id'])] = speed
                _location = i['location']
                try:
                    _, _location = _location.split('/')
                except:
                    pass
                location.append(dict(fex_id=i['id'], location=_location))
        if location:
            fex_location[hostname] = location
    return fex_speed, fex_location


def get_n7k_port_speed():
    logging.info('Analysis n7k port speed')

    n7k_port_speed = {}
    for fn in os.listdir(MAIN_PATH):
        if 'FOR-MGT' not in fn:
            continue
        hostname = fn[:-5]
        p = opj(MAIN_PATH, fn)
        with open(p) as f:
            d = json.load(f)
        module = {}
        for m in d.get('show module', []):
            model = m['model']
            if 'F248' not in model:
                continue
            if 'XP' in model:
                module[m['slot']] = 10000
            else:
                module[m['slot']] = 1000
        for v in d.get('show vdc membership', []):
            name = v['name']
            if 'VDC1' in name:
                continue
            if name == 'Unallocated':
                name = hostname
            ports = {}
            for p in v['members']:
                slot = p.split('/')[0][-1]
                speed = module.get(slot)
                if speed is None:
                    break
                else:
                    ports[p] = speed
            if ports:
                n7k_port_speed[name] = ports
    with open('/tmp/n7k_interface_speed.json', 'w') as f:
        json.dump(n7k_port_speed, f, indent=4)
    return n7k_port_speed


def parse_interface(access_switches, n7k_port_speed, fex_speed):
    logging.info('Analysis interface info')

    results = []
    sw_port_info = {}
    for fn in os.listdir(MAIN_PATH):
        hostname = fn[:-5]
        if hostname not in access_switches:
            continue
        with open(opj(MAIN_PATH, fn)) as f:
            data = json.load(f)
        ports = data.get('show interface description', [])
        port_desc = dict((p['interface'], p['description']) for p in ports)
        ports = data.get('show interface status', [])
        sw_port_info[hostname] = {}
        n7k_port = n7k_port_speed.get(hostname, {})
        for p in ports:
            s = p['status']
            if s in admin_down:
                admin = 'down'
            elif p['vlan'] == '1' and s == 'down':
                admin = 'down'
            else:
                admin = 'up'
            if admin == 'down':
                operate = 'down'
            else:
                operate = 'down' if s in operate_down else 'up'
            i = p['interface']
            if i.startswith('Gi'):
                speed = 1000
            elif i.startswith('Te'):
                speed = 10000
            elif i.startswith('Fa'):
                speed = 100
            elif i.startswith('Eth'):  # Nexus
                if hostname.startswith('JD70SW'):
                    speed = n7k_port.get(i, 1000)
                else:
                    if '10G' in p['speed']:
                        speed = 10000
                    else:
                        speed = 1000
                        # fex_id = i[8:11]
                        # speed = fex_speed.get((hostname, fex_id), 1000)
            try:
                pair_id = get_port_pair_id(hostname, i, 1)
                description = port_desc.get(i, '')
                results.append(dict(hostname=hostname,
                                    interface=i,
                                    description=description,
                                    pair_id=pair_id,
                                    speed=speed,
                                    vlan=p['vlan'],
                                    adminStatus=admin,
                                    operStatus=operate
                                    ))
                sw_port_info[hostname][i] = dict(description=description,
                                                 speed=speed,
                                                 vlan=p['vlan'],
                                                 pair_id=pair_id,
                                                 adminStatus=admin,
                                                 operStatus=operate
                                                 )
            except:
                logging.warning(hostname)
    with open('/tmp/switch_interface_info.json', 'w') as f:
        json.dump(sw_port_info, f, indent=4)
    return results


def get_all_gws(hostnames):
    url = APP_URL + 'tools/api/get_gateway'
    res = requests.post(url, json={'hostname': hostnames})
    gws = list(res.json().values())
    url = APP_URL + 'tools/api/rac_private_net_gateway'
    res = requests.post(url, json={'hostname': hostnames})
    rac_private_gws = list(res.json().values())
    gws.extend(rac_private_gws)
    return list(set(gws))


def get_arp(gateway_switch_names):
    logging.info('Get all APR info')

    arp_dict = defaultdict(dict)
    for fn in os.listdir(MAIN_PATH):
        hostname = fn[:-5]
        if hostname not in gateway_switch_names:
            continue
        with open(opj(MAIN_PATH, fn)) as f:
            d = json.load(f)
        zone = hostname[:2] + hostname.split('-')[1]
        for a in d.get('show ip arp', []):
            v = a['port'][4:]
            arp_dict[zone][a['ip']] = dict(mac=a['mac'], vlan=v)
    return arp_dict


def get_mac(access_switch_names):
    logging.info('Get all MAC address info')

    mac_dict = defaultdict(dict)
    for fn in os.listdir(MAIN_PATH):
        hostname = fn[:-5]
        if hostname not in access_switch_names:
            continue
        with open(opj(MAIN_PATH, fn)) as f:
            d = json.load(f)
        zone = hostname[:2] + hostname.split('-')[1]
        if '65SW' in hostname:
            mac_table = d.get('show mac-address-table', [])
        else:
            mac_table = d.get('show mac address-table', [])
        for m in mac_table:
            if 'Eth' not in m['port']:
                continue
            k = m['mac'], m['vlan']
            port = regulate_port_name(m['port'])
            mac_dict[zone][k] = dict(switch=hostname, port=port)
    return mac_dict


def server_locate(all_arp_dict, all_mac_dict):
    ip_access_port_list = []
    for zone, arp_dict in all_arp_dict.items():
        mac_dict = all_mac_dict.get(zone, {})
        if not mac_dict:
            logging.warning('No MAC address info: %s', zone)
        for ip, value in arp_dict.items():
            mac = value['mac']
            vlan = value['vlan']
            access_info = mac_dict.get((mac, vlan))
            if access_info is not None:
                value.update(access_info)
            value['ip'] = ip
            value['site'] = zone[:2]
            value['zone'] = zone[2:]
            ip_access_port_list.append(value)
    with open('/tmp/ip_access_port.json', 'w') as f:
        json.dump(ip_access_port_list, f, indent=4)


def ana_pair_ports(eth_ports):
    pair_ports = defaultdict(list)
    for p in eth_ports:
        pair_ports[p['pair_id']].append(p['adminStatus'])
    for i in list(pair_ports.keys()):
        s = pair_ports[i]
        if i.startswith('['):
            if len(s) != 4:
                del pair_ports[i]
                continue
        elif len(pair_ports[i]) != 2:
            del pair_ports[i]
            continue
        s = set(s)
        if len(s) == 1 and list(s)[0] == 'down':
            print(i)
    with open('/tmp/envsetup_as_port1.json', 'w') as f:
        json.dump(pair_ports, f, indent=2)
    with open('/tmp/envsetup_as_port.json', 'w') as f:
        json.dump(eth_ports, f, indent=2)


def push(access_switches, fex_location, eth_ports):
    # update port statistics
    devices = {h['hostname']: h for h in access_switches}
    data = dict(devices=devices, fex=fex_location, interfaces=eth_ports)
    res = requests.post(PORT_STATISTIC_URL, data=json.dumps(data))
    if res.status_code != 200:
        logging.error('Port statistics update failed: %s', res.text)
    else:
        logging.info('Port statistics updated successfully')

    # update device info to envsetup
    data = dict(table='switch_device', data=access_switches)
    res = requests.post(ENVSETUP_API_URL, data=json.dumps(data))
    if res.status_code != 200:
        logging.error('Envsetup device update failed: %s', res.text)
    else:
        logging.info('Envsetup device updated successfully')

    # update fex info to envsetup
    data = dict(table='switch_fex', data=fex_location)
    res = requests.post(ENVSETUP_API_URL, data=json.dumps(data))
    if res.status_code != 200:
        logging.error('Envsetup fex update failed: %s', res.text)
    else:
        logging.info('Envsetup fex updated successfully')

    # update interface info to envsetup
    data = dict(table='switch_interface', data=eth_ports)
    res = requests.post(ENVSETUP_API_URL, data=json.dumps(data))
    if res.status_code != 200:
        logging.error('Envsetup port update failed: %s', res.text)
    else:
        logging.info('Envsetup port updated successfully')


def main():
    filters = [
        "NF|JD|TG !SW0A- !SW0B- SW !OVA cisco|ios|nxos"
    ]
    query_str = '&'.join(('format=all&query=%s' % f for f in filters))
    url = DEVICE_FILTER_URL + query_str
    access_switches = requests.get(url).json()['filtered']
    access_switch_names = []
    for sw in access_switches:
        access_switch_names.append(sw['hostname'])
        try:
            sw['location'] = sw['location'].split('/')[-1]
        except:
            pass
    gateway_switch_names = get_all_gws(access_switch_names)
    all_mac_dict = get_mac(access_switch_names)
    all_arp_dict = get_arp(gateway_switch_names)
    server_locate(all_arp_dict, all_mac_dict)
    n7k_port_speed = get_n7k_port_speed()
    fex_speed, fex_location = get_fex_speed_and_location()
    eth_ports = parse_interface(
        access_switch_names, n7k_port_speed, fex_speed)
    # ana_pair_ports(eth_ports)
    push(access_switches, fex_location, eth_ports)
