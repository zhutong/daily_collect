import json
import logging

from config import *


def main():
    logging.info('Analysis SNMP')
    with open(PRE_PARSED_SNMP_FN) as f:
        pre_parsed_snmp_data = json.load(f)
    l3_interface = {}
    all_interface = {}
    device_dict = {}
    links = []
    for hostname in pre_parsed_snmp_data:
        data_set = pre_parsed_snmp_data[hostname]

        # IF table
        datas = data_set.get('if_table')
        if datas is None:
            logging.error('No if table: %s', hostname)
            continue
        if_dict = {}
        all_interface[hostname] = {}
        for data in datas:
            interface = data['ifDescr']
            if_index = data['ifIndex']
            # try:
            #     ports.append(','.join((hostname,
            #                            r['ifDescr'],
            #                            r['ifIndex'],
            #                            str(r['ifSpeed']),
            #                            r['adminStatus'],
            #                            r['operStatus'],
            #                            r['mac']
            #                            )))
            # except:
            #     print(hostname, r)
            #     raise
            d = dict(speed=data['ifSpeed'],
                     adminStatus=data['adminStatus'],
                     operStatus=data['operStatus'],
                     ifIndex=if_index,
                     macAddress=data['mac'],
                     interface=interface
                     )
            all_interface[hostname][interface] = d
            if_dict[if_index] = d
        # IF IP table
        datas = data_set.get('if_ip_table')
        if datas is None:
            logging.error('No if ip table: %s', hostname)
            continue
        ip_dict = {}
        for data in datas:
            if_index = data['ifIndex']
            try:
                if_data = if_dict[if_index]
            except:
                logging.error('analysis if ip entry error: %s', hostname)
                continue
            if 'ip' not in if_data:
                if_data.update(data)
            ip_dict[data['ip']] = if_data
        if ip_dict:
            l3_interface[hostname] = ip_dict

        # CDP
        datas = pre_parsed_snmp_data[hostname].get('cdp_table')
        if datas is None:
            logging.error('No cdp table: %s', hostname)
            datas = []
        for item in datas:
            nei = item['neighbor']
            device_dict[nei] = dict(hostname=nei, ipaddress='')
            links.append(dict(hostname=hostname,
                              remote_device=nei,
                              local_if=if_dict[item['l_ifIndex']
                                               ]['interface'],
                              remote_if=item['r_port']))

        # LLDP
        datas = pre_parsed_snmp_data[hostname].get('lldp_table')
        if datas is None:
            logging.error('No lldp table: %s', hostname)
            datas = []
        for item in datas:
            nei = item['neighbor']
            device_dict[nei] = dict(hostname=nei, ipaddress='')
            try:
                l_if = if_dict[item['l_ifIndex']]['interface']
            except:
                logging.error('analysis LLDP entry error: %s', hostname)
                continue
            links.append(dict(hostname=hostname,
                              remote_device=nei,
                              local_if=if_dict[item['l_ifIndex']
                                               ]['interface'],
                              remote_if=item['r_port']))

    with open('/tmp/l3_interface.json', 'w') as f:
        json.dump(l3_interface, f, indent=4)

    with open('/tmp/interface.json', 'w') as f:
        json.dump(all_interface, f, indent=4)

    with open('/tmp/topology.json', 'w') as f:
        data = dict(devices=list(device_dict.values()),
                    links=links)
        json.dump(data, f, indent=4)
