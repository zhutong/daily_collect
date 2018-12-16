# -*- coding: utf-8 -*-
import re

from .showparser import regulate_port_name

ip_re = re.compile('\d+\.\d+\.\d+\.\d+')

if_status = {'1': 'up', '2': 'down'}


def __convert_mac(s, if_type):
    if if_type not in ('6', '53'):
        return ''
    return '.'.join((s[2:6], s[6:10], s[10:]))


def parse_if_table(rows, *args, **kwargs):
    res = []
    for row in rows:
        # try:
        #     ifSpeed = int(row[2][1])//1000000
        # except:
        #     return res
        ifType = row[1][1]
        r = dict(ifIndex=row[0][0].rsplit('.', 1)[1],
                 ifDescr=row[0][1],
                 ifType=ifType,
                 ifSpeed=int(row[2][1])//1000000,
                 mac=__convert_mac(row[3][1], ifType),
                 lastChange=int(row[6][1])//360000,
                 adminStatus=if_status.get(row[4][1], 'others'),
                 operStatus=if_status.get(row[5][1], 'others'))
        res.append(r)
    return res


def parse_if_ip_table(rows, *args, **kwargs):
    res = []
    for row in rows:
        ip = row[0][0][21:]
        if ip.startswith('127'):
            continue
        if not ip_re.match(ip):
            continue
        r = dict(ifIndex=row[0][1],
                 ip=ip,
                 mask=row[1][1])
        res.append(r)
    return res


def parse_lldp_table(rows, *args, **kwargs):
    res = []
    for row in rows:
        # if 'No more' in row[0][1]:
        #     return res
        neighbor = row[0][1].split('.')[0].split('(')[0]
        d = dict(neighbor=neighbor,
                 l_ifIndex=row[0][0].rsplit('.', 2)[-2],
                 r_port=regulate_port_name(row[1][1]))
        res.append(d)
    return res


def parse_cdp_table(rows, *args, **kwargs):
    res = []
    for row in rows:
        # if 'No more' in row[0][1]:
        #     return res
        if_index = row[0][0].rsplit('.', 2)[1]
        neighbor = row[0][1].split('.')[0].split('(')[0]
        d = dict(neighbor=neighbor,
                 l_ifIndex=if_index,
                 r_port=row[1][1])
        res.append(d)
    return res
