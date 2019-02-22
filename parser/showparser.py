# -*- coding: utf-8 -*-

import re
import logging


def parse_mac(text, *args, **kwargs):
    """
    思科设备的show mac address table命令解析器
    """
    re_mac = re.compile('\w?\s+?(?P<vlan>\d+)\s+'
                        '(?P<mac>\w+\.\w+\.\w+)\s+dynamic\s+'
                        '(\d+\s+F\s+F\s+|ip.*?\s+|\s)'
                        '(?P<port>\S+)',
                        re.I)
    return [m.groupdict() for m in re_mac.finditer(text)]


def parse_arp(text, *args, **kwargs):
    re_mac = re.compile('(?P<ip>\d+\.\d+\.\d+\.\d+)\s+.*?\s+'
                        '(?P<mac>\w+\.\w+\.\w+)\s+'
                        '(ARPA\s+)?'
                        '(?P<port>\S+)')
    return [m.groupdict() for m in re_mac.finditer(text)]


def parse_version(text, *args, **kwargs):
    software_re = re.compile('^\s+system:\s+version (?P<version>.*)$', re.M)
    memory_re = re.compile('(?P<mem>\d+)\s+kB of memory', re.M)
    flash_re = re.compile('^\s+bootflash:\s+(?P<flash>\d+)\s+kB', re.M)
    slot0_re = re.compile('^\s+slot0:\s+(?P<slot>\d+)\s+kB', re.M)

    found = software_re.findall(text)
    if found:
        software = found[0].strip()
    else:
        software = ''
    found = memory_re.findall(text)
    if found:
        memory = found[0]
    else:
        memory = ''
    found = flash_re.findall(text)
    if found:
        flash = found[0]
    else:
        flash = ''
    found = slot0_re.findall(text)
    if found:
        slot0 = found[0]
    else:
        slot0 = ''

    hardware = ''
    if 'NX-OS' in text:
        platform = 'NXOS'
        for line in text.splitlines():
            if 'system:' in line:
                version = line.split()[-1]
                break
            elif '  cisco Nexus' in line:
                hardware = line.split()[1]
                break
    else:
        platform = 'IOS'
        version = text.split('Version ')[1].split()[0].split(',')[0]
        for line in text.splitlines():
            if 'K bytes of memory.' in line:
                memory = line.split()[-4].split('K')[0]
                hardware = line.split()[1]
            elif 'bytes of Flash' in line:
                flash = line.split('K', 1)[0]

    return [dict(hardware=hardware,
                 platform=platform,
                 version=version,
                 memory=memory,
                 flash=flash,
                 slot0=slot0)]


def parse_vlan_brief(text, *args, **kwargs):
    re_vlan = re.compile('(?P<id>\d+)\s+(?P<name>\S+)\s+active')
    vlans = []
    text = text.split('-----')[-1]
    for l in text.splitlines():
        r = re_vlan.match(l)
        if r:
            _id, name = r.groups()
            ss = l.split()
            ports = []
            for p in ss[3:]:
                m = p.rstrip(',')
                if m.startswith('E'):
                    m = m.replace('Eth', 'Ethernet')
                elif m.startswith('G'):
                    m = m.replace('Gi', 'GigabitEthernet')
                elif m.startswith('T'):
                    m = m.replace('Te', 'TenGigabitEthernet')
                ports.append(m)
            vlans.append(dict(id=_id, name=name, ports=ports))
        elif not l.strip():
            break
        elif l.startswith(' '):
            for m in l.strip().split(', '):
                if m.startswith('E'):
                    m = m.replace('Eth', 'Ethernet')
                elif m.startswith('G'):
                    m = m.replace('Gi', 'GigabitEthernet')
                elif m.startswith('T'):
                    m = m.replace('Te', 'TenGigabitEthernet')
                ports.append(m)
    return vlans


def parse_location(text, *args, **kwargs):
    re_location = re.compile('snmp-server\slocation\s+(?P<location>.*)')
    return [m.groupdict() for m in re_location.finditer(text)]


def parse_port_channel(text, *args, **kwargs):
    po_re = re.compile('^(?P<id>\d+)\s+Po\d+.*?'
                       '(?P<members>((Eth|Te|Gi)[\d/.]+'
                       '\(\w\)\s+\n?){1,16})',
                       re.M)
    pos = [m.groupdict() for m in po_re.finditer(text)]
    for r in pos:
        members = []
        for m in r['members'].split():
            m = m.split('(')[0]
            if m.startswith('E'):
                m = m.replace('Eth', 'Ethernet')
            elif m.startswith('G'):
                m = m.replace('Gi', 'GigabitEthernet')
            elif m.startswith('T'):
                m = m.replace('Te', 'TenGigabitEthernet')
            members.append(m)
        r['members'] = members

    return pos


def parse_cdp_detail(text, *args, **kwargs):
    cdp_re = re.compile(
        'Device ID:\s?(?P<neighbor>\S+).*?'
        'ddress:\s(?P<ip>\d+\.\d+\.\d+\.\d+).*?'
        'Interface:\s(?P<l_port>\S+),.*?'
        'port\):\s(?P<r_port>\S+)',
        re.M | re.S)
    cdps = [m.groupdict() for m in cdp_re.finditer(text)]
    for r in cdps:
        r['neighbor'] = r['neighbor'].split('.')[0].split('(')[0]
    return cdps


def parse_lldp_detail(text, *args, **kwargs):
    lldps = []
    lp = ''
    rp = ''
    for line in text.splitlines():
        if line.lower().startswith('port id'):
            rp = line.split()[-1]
            rp = regulate_port_name(rp)
        elif line.lower().startswith('local port id'):
            lp = line.split()[-1]
            lp = regulate_port_name(lp)
        elif line.lower().startswith('system name'):
            neighbor = line.split()[-1]
        elif line.lower().startswith('management address'):
            ip = line.split()[-1]
            lldps.append(dict(neighbor=neighbor,
                              ip=ip,
                              l_port=lp,
                              r_port=rp))
    return lldps


def parse_fex(text, *args, **kwargs):
    code_map = {
        "N2K-C2148T-1GE": 'redwood',
        "N2K-C2224TP-1GE": 'portola',
        "N2K-C2248TP-1GE": 'portola',
        "N2K-C2232PP-10GE": 'woodside',
        "N2K-C2232TM-10GE": 'woodside',
        "N2K-C2248TP-E-1GE": 'princeton',
        "N2K-C2232TM-E-10GE": 'woodside',
        "N2K-C2248PQ-10GE": 'woodside',
        "N2K-C2348UPQ-10GE": 'tiburon',
    }
    re_fex = re.compile(
        '(?P<id>\d+)\s+FEX\d+_(?P<location>\S+)\s+'
        'Online\s+(?P<model>\S+)\s+(?P<sn>\S+)')
    fexes = [m.groupdict() for m in re_fex.finditer(text)]
    for f in fexes:
        f['code_name'] = code_map[f['model']]

    return fexes


def parse_module(text, *args, **kwargs):
    platform = 'NXOS' if ('WWN' in text or 'Xbar' in text) else 'IOS'
    module = []
    sub_module = []
    xbar = []
    module_sn = []
    xbar_sn = []
    module_diag = []
    start = False
    for line in text.splitlines():
        if line.startswith('--'):
            continue
        if line.startswith('Mod Ports'):
            start = True
            mylist = module
        elif line.startswith(('Mod MAC', ' M MAC')):
            start = True
            mylist = module_sn
        elif 'Sub-Module' in line:
            start = True
            mylist = sub_module
        elif 'Diag' in line:
            start = True
            mylist = module_diag
        elif 'Module-Type' in line:
            start = True
            if 'Xbar' in line:
                mylist = xbar
            else:
                mylist = module
        elif 'Serial-Num' in line:
            start = True
            if 'Xbar' in line:
                mylist = xbar_sn
            else:
                mylist = module_sn
        elif not line.strip():
            start = False
        elif start:
            ss = line.split('*')[0].split()
            mylist.append(ss)

    module_list = []
    for i, m in enumerate(module):
        if platform == 'IOS':
            sn = m[-1]
            status = module_sn[i][-1]
            diag = ''
        else:
            sn = module_sn[i][-1]
            status = m[-1]
            try:
                diag = module_diag[i][-1]
            except:
                diag = ''
        module_list.append(
            dict(slot=m[0],
                 model=m[-2],
                 sn=sn,
                 status=status,
                 diag=diag,
                 module='module'))
    for i, m in enumerate(sub_module):
        module_list.append(
            dict(slot=m[0],
                 model=m[-4],
                 sn=m[-3],
                 status=m[-1],
                 module='sub_module'))
    for i, m in enumerate(xbar):
        module_list.append(
            dict(slot=m[0],
                 model=m[-2],
                 sn=xbar_sn[i][-1],
                 status=m[-1],
                 module='xbar'))
    return module_list


def parse_inventory(text, *args, **kwargs):
    re_inventory = re.compile(
        'NAME: "(?P<name>.*)",\s+DESCR: "(?P<description>.*)"(\s+)?\n'
        'PID:\s(?P<pid>\S+)?\s+?,.*?SN:\s(?P<sn>\S*)',
        re.M)
    return [m.groupdict() for m in re_inventory.finditer(text)]


def parse_transceiver_re(text, *args, **kwargs):
    re_s = re.compile(
        '(?P<interface>(\S+)?Eth\S+[\d/]+)\s+'
        'transceiver is present.+?'
        'type is\s(?P<type>\S+?)\s.+?'
        'serial number is\s(?P<sn>\S+?)\s.+?'
        'Temperature\s+(?P<temperature>[\d\.N/A]+?)\s.+?'
        'Voltage\s+(?P<voltage>[\d\.N/A]+?)\s.+?'
        'Current\s+(?P<current>[\d\.N/A]+?)\s.+?'
        'Tx Power\s+(?P<tx_pwr>[\-\d\.N/A]+?)\s.+?'
        'Rx Power\s+(?P<rx_pwr>[\-\d\.N/A]+?)\s.+?',
        re.M | re.S)
    return [m.groupdict() for m in re_s.finditer(text)]


def parse_transceiver(text, *args, **kwargs):
    re_interface = re.compile('((\S+)?Eth\S+|fc)[\d/]+')
    ports = []
    port = None
    for l in text.splitlines():
        if re.match(re_interface, l):
            port = dict(interface=l.split()[0])
        elif 'sfp is not present' in l:
            port = None
        elif 'DOM is not supported' in l:
            port = None
        elif port:
            if '++' in l or '--' in l:
                alarm_level = 4
            elif ' + ' in l or ' - ' in l:
                alarm_level = 3
            else:
                alarm_level = 0
            if 'Temperature' in l:
                port['temperature'] = l.split()[1] + ' (%s)' % alarm_level
            elif 'Voltage' in l:
                port['voltage'] = l.split()[1] + ' (%s)' % alarm_level
            elif 'Current' in l:
                port['current'] = l.split()[1] + ' (%s)' % alarm_level
            elif 'Tx Power' in l:
                port['tx_pwr'] = l.split()[2] + ' (%s)' % alarm_level
            elif 'Rx Power' in l:
                port['rx_pwr'] = l.split()[2] + ' (%s)' % alarm_level
                ports.append(port)
    return ports


def parse_vdc_membership(text, *args):
    results = []
    text = text.rsplit('\n', 1)[0]
    for vdc_text in text.split('vdc_id: ')[1:]:
        ss = vdc_text.split()
        vdc = dict(id=ss[0],
                   name=ss[2],
                   members=ss[4:])
        results.append(vdc)
    return results


def parse_ip_interface_brief(text, *args, **kwargs):
    re_interface = re.compile(
        '^(?P<interface>.+?)\s+'
        '(?P<ip>\d+\.\d+\.\d+\.\d+).+?up.+?up',
        re.M)
    return [m.groupdict() for m in re_interface.finditer(text)]


def parse_interface_status(text, *args, **kwargs):
    ports = []
    for l in text.splitlines():
        if l.startswith(('Eth', 'Gi', 'Te', 'Fa')):
            ss = l.split()
            if 'No ' in l or 'X SFP' in l or 'Not Present' in l:
                p = dict(interface=regulate_port_name(ss[0]),
                         status=ss[-6],
                         vlan=ss[-5],
                         duplex=ss[-4],
                         type=' '.join(ss[-2:]),
                         speed=ss[-3])
            else:
                try:
                    p = dict(interface=regulate_port_name(ss[0]),
                             status=ss[-5],
                             vlan=ss[-4],
                             duplex=ss[-3],
                             type=ss[-1],
                             speed=ss[-2])
                except:
                    print(l)
                    raise
            ports.append(p)
    return ports


def parse_interface_description(text, *args, **kwargs):
    ports = []
    for l in text.splitlines():
        if '--' in l:
            continue
        if l.startswith('Eth'):
            ss = l.split()
            p = dict(interface=regulate_port_name(ss[0]),
                     description=ss[-1].strip())
            ports.append(p)
        elif l.startswith(('Gi', 'Te', 'Fa')):
            if 'admin down' in l:
                continue
            ss = l.split()
            description = ' '.join(ss[3:])
            p = dict(interface=regulate_port_name(ss[0]),
                     description=description)
            ports.append(p)
    return ports


def parse_interface(text, *args, **kwargs):
    res = []
    port = None
    start = False
    if ', address:' in text:  # NXOS
        for l in text.splitlines():
            if l.startswith('Eth'):
                if 'is up' in l:
                    port = dict(interface=l.split()[0])
                else:
                    port = None
            if port:
                if ', address:' in l:
                    port['mac'] = l.split()[-3]
                elif 'CRC' in l:
                    port['crc'] = int(l.split()[4])
                elif 'input error' in l:
                    port['rx_drop'] = 0
                    port['rx_error'] = int(l.split(None, 1)[0])
                elif 'output error' in l:
                    port['tx_drop'] = 0
                    port['tx_error'] = int(l.split(None, 1)[0])
                    res.append(port)
                    port = None
    elif 'WWN' in text:  # MDS
        for l in text.splitlines():
            if l.startswith('fc'):
                if 'is up' in l:
                    port = dict(interface=l.split()[0],
                                crc=0)
                    is_rx = True
                else:
                    port = None
            if port:
                if 'Port WWN' in l:
                    port['mac'] = l.split()[-1]
                elif 'discards' in l:
                    ss = l.split()
                    drop = int(ss[0])
                    error = int(ss[1].split(',')[1])
                    if is_rx:
                        port['rx_drop'] = drop
                        port['rx_error'] = error
                        is_rx = False
                    else:
                        port['tx_drop'] = drop
                        port['tx_error'] = error
                        res.append(port)
    else:  # IOS
        for l in text.splitlines():
            if start and not l.startswith(' '):
                r = dict(interface=name,
                         mac=mac,
                         crc=crc,
                         rx_drop=0,
                         rx_error=rx_error,
                         tx_drop=tx_drop,
                         tx_error=tx_error)
                res.append(r)
                start = False
            if 'line protocol is' in l:
                name = l.split()[0]
                if 'Eth' in name and 'line protocol is up' in l:
                    start = True
                    crc = 0
                else:
                    start = False
            elif not start:
                continue
            elif ', address is' in l:
                mac = l.split()[-3]
            elif 'input errors' in l:
                rx_error = int(l.split()[0])
            elif 'output errors' in l:
                tx_error = int(l.split()[0])
            elif 'output drops' in l:
                ss = l.split()
                try:
                    tx_drop = int(ss[-1])
                except:
                    tx_drop = int(ss[-4])
            elif 'CRC' in l:
                crc = int(l.split()[3])
    return res


def parse_route(text, *args, **kwargs):
    return []


re_port_id = re.compile('[\d/\.]+')


def regulate_port_name(name, abbreviate=False):
    try:
        port_id = re_port_id.findall(name)[0]
        l = name[0].upper()
        if abbreviate:
            return l + port_id
        if l == 'T':
            return 'TenGigabitEthernet' + port_id
        elif l == 'G':
            return 'GigabitEthernet' + port_id
        elif l == 'F':
            return 'FastEthernet' + port_id
        elif l == 'E':
            return 'Ethernet' + port_id
        else:
            return name
    except:
        return name


def regulate_mac_address(mac):
    mac = mac.replace(":", "").replace("-", "")
    mac = mac[0:4] + '.' + mac[4:8] + '.' + mac[8:]
    return mac
