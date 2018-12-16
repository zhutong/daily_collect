# -*- coding:utf-8 -*-

import re

re_port_id = re.compile('[\d/\.]+')
re_hostname = re.compile('([A-Z0-9]+[A-Z])([\dA-Z]{2,3})(-.*)')
re_fex_port = re.compile('(Ethernet1)(\d\d)(/1/\d+)')
re_n5k = re.compile('[A-Z]+(50|55|56)SW[\dA-Z]{2,3}-.*')
re_port_range = re.compile('(.*/)([\d,-]+)')
GW_ID = 'ABACDCEFEGHG'


def get_peer_hostname(hostname):
    """
    返回配对的网络设备名称, 如:
    NF55SW05-B5 -> NF55SW06-B5
    JD70SW16-M2-VDC5 -> JD70SW17-M2-VDC5
    JD70SW0E-M2-VDC5 -> JD70SW0F-M2-VDC5
    """
    p, d_id, a = re_hostname.search(hostname).groups()
    # print(p, d_id, a)
    i = GW_ID.find(d_id[-1])
    if i >= 0:
        return '%s0%s%s' % (p, GW_ID[i+1], a)
    d_id = int(d_id)
    peer_id = d_id + 1 if (d_id % 2) else d_id - 1
    return '%s%02d%s' % (p, peer_id, a)


def get_peer_fex_port(portname):
    """
    返回配对的FEX接口名称, 若不匹配FEX接口名称，返回None:
    Ethernet101/1/1 -> Ethernet102/1/1
    Ethernet110/1/1 -> Ethernet109/1/1
    """
    try:
        p, f_id, a = re_fex_port.search(portname).groups()
        f_id = int(f_id)
        peer_id = f_id + 1 if (f_id % 2) else f_id - 1
        return '%s%02d%s' % (p, peer_id, a)
    except:
        return None


def get_port_pair_id(hostname, portname, mode=1):
    """
    返回接口对的ID, mode为0时，仅返回单遍设备的单边接口
    """
    peer_hostname = get_peer_hostname(hostname)
    hostnames = sorted([hostname, peer_hostname])
    if re_n5k.match(hostname):
        peer_portname = get_peer_fex_port(portname)
        if peer_portname:
            portnames = sorted([portname, peer_portname])
            if mode:
                return '[%s|%s]@[%s|%s]' % (portnames[0], portnames[1], hostnames[0], hostnames[1])
            else:
                return '%s@%s' % (portnames[0], hostnames[0])
    if mode:
        return '%s@[%s|%s]' % (portname, hostnames[0], hostnames[1])
    else:
        return '%s@%s' % (portname, hostnames[0])


def parse_port_range(port_range):
    """
    给定接口范围，返回接口列表，支持的输入格式如下：
    Ethernet5/1-6,8-10,9,11
    Ethernet101/1/1-24
    """
    port_range = port_range.replace(' ', '')
    p, a = re_port_range.search(port_range).groups()
    portnames = []
    for s in a.split(','):
        if '-' in s:
            f, l = s.split('-')
            for i in range(int(f), int(l)+1):
                portnames.append('%s%s' % (p, i))
        else:
            portnames.append(p+s)
    return portnames


def get_port_pair_id_range(hostname, port_range, mode=1):
    """
    给定交换机名称及接口范围，返回PortPairId列表
    """
    pair_ids = []
    portnames = parse_port_range(port_range)
    for p in portnames:
        pair_ids.append(get_port_pair_id(hostname, p, mode))
    return pair_ids


def get_pair_members(port_pair_id, mode='list'):
    if '|' not in port_pair_id:
        port, hostname = port_pair_id.split('@')
        port_pair_id = get_port_pair_id(hostname, port)
    ports, hostnames = port_pair_id.split('@')
    hostnames = hostnames[1:-1].split('|')
    if ports.startswith('['):
        ports = ports[1:-1].split('|')
    else:
        ports = [ports]
    if mode == 'list':
        members = []
        for h in hostnames:
            for p in ports:
                members.append((h, p))
    else:
        members = {}
        for h in hostnames:
            members[h] = ports
    return members


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


if __name__ == '__main__':
    print(get_peer_hostname('NF31BL100-B5'))

    print(get_port_pair_id('JD70SW05-M2-VDC5', 'Ethernet110/1/1'))
    print(get_port_pair_id('NF55SW06-M2', 'Ethernet1/1'))
    print(get_port_pair_id('NF65SW05-M2', 'Ethernet109/1/1'))
    print(get_port_pair_id('NF55SW0F-M2', 'Ethernet110/1/1'))

    print(parse_port_range('Ethernet101/1/1-6, 9,12,15-18'))
    print(get_port_pair_id_range('NF55SW06-M2', 'Ethernet101/1/1-2,9'))
    print(get_port_pair_id_range('NF65SW06-M2', 'Ethernet1/1-2, 9'))

    print(get_pair_members('Ethernet1/2@[NF55SW05-M2|NF55SW06-M2]'))
    print(get_pair_members(
        '[Ethernet101/1/2|Ethernet102/1/2]@[NF55SW05-M2|NF55SW06-M2]', 'dict'))
