# -*- coding: utf-8 -*-

import re
from collections import defaultdict

re_mds_log_loss_of_signal = re.compile(
    '(?P<timestamp>20\d+\s\w+\s+\d+\s+\d+:\d+:\d+)'
    '\.\d+\s.*(?P<interface>fc\d+/\d+)', re.I)


def attach_fex(text):
    try:
        result_dic = {}
        for line in text.splitlines():
            if 'attach fex' in line:
                result_dic["fex"] = line.split()[-1]
            elif line.startswith("  1") and line.find("(") >= 0:
                result_dic["pw1_status"] = line.split(
                    "(")[1].split(')')[0].strip()
            elif line.startswith("  2") and line.find("(") >= 0:
                result_dic["pw2_status"] = line.split(
                    "(")[1].split(')')[0].strip()
            elif line.startswith("1") or (line.startswith("  1") and line.find("(") < 0):
                result_dic["pw1_vout"] = line.split()[2]
            elif line.startswith("2") or (line.startswith("  2") and line.find("(") < 0):
                result_dic["pw2_vout"] = line.split()[2]
            elif "RX_CRC_NOT_STOMPED" in line:  # Add STOMPED info in parser
                l = line.replace('|', ' ')
                result_dic['RX_CRC_NOT_STOMPED'] = int(l.split()[-2])
            elif "RX_CRC_STOMPED" in line:
                l = line.replace('|', ' ')
                result_dic['RX_CRC_STOMPED'] = int(l.split()[-2])
                return [result_dic]
    except Exception as e:
        return []


def parse_system_internal_raid(text, *args, **kwargs):
    for line in text.splitlines():
        if line.endswith('show system internal raid'):
            slot = line.split()[1]
        elif line.startswith("RAID data from CMOS"):
            status = [line.split()[-1]]
        elif 'blocks [2/' in line:
            status.append(line.split()[-1][1:-1])
            if len(status) == 5:
                break
    key = "slot_%s_raid" % slot
    return [{key: ' '.join(status)}]


def parse_system_internal_flash(text, *args, **kwargs):
    for line in text.splitlines():
        if line.endswith('show system internal flash'):
            slot = line.split()[1]
        elif line.startswith('/var/log'):
            _, total, usage, free, pecentage, *_ = line.split()
            key = "slot_%s_log_space" % slot
            return [{key: int(pecentage)}]
    return []


def parse_processes_memory_tacacs(text, *args, **kwargs):
    for line in text.splitlines():
        if line.endswith('tacacs'):
            _, _, total_memory, usage, *_ = line.split()
            total_memory = int(total_memory)
            usage = int(usage)
            pecentage = int(100 * usage / total_memory)
            return [dict(total_memory=total_memory,
                         usage=usage,
                         pecentage=pecentage)]
    return []


def parse_vlan_huawei(text, *args, **kwargs):
    re_vlan = re.compile('(?P<id>\d+)\s+common\s+enable', re.M)
    return [m.groupdict() for m in re_vlan.finditer(text)]


def parse_stp_summary_total(text, *args, **kwargs):
    try:
        n = int(text.splitlines()[1].split()[-1])
    except:
        n = 0
    return [dict(logic_numbers=n)]


def parse_mds_hardware_internal_error(text, *args, **kwargs):
    F16_IPA_IPA0_CNT_BAD_CRC = 0
    F16_IPA_IPA0_CNT_CORRUPT = 0
    F16_IPA_IPA1_CNT_BAD_CRC = 0
    F16_IPA_IPA1_CNT_CORRUPT = 0
    INTERNAL_ERROR_CNT = 0
    HIGH_IN_BUF_PKT_CRC_ERR_COUNT = 0

    for line in text.splitlines():
        if 'F16_IPA_IPA0_CNT_BAD_CRC' in line:
            F16_IPA_IPA0_CNT_BAD_CRC += int(re.findall('(\d{8,})', line)[0])
        elif 'F16_IPA_IPA0_CNT_CORRUPT' in line:
            F16_IPA_IPA0_CNT_CORRUPT += int(re.findall('(\d{8,})', line)[0])
        elif 'F16_IPA_IPA1_CNT_BAD_CRC' in line:
            F16_IPA_IPA1_CNT_BAD_CRC += int(re.findall('(\d{8,})', line)[0])
        elif 'F16_IPA_IPA1_CNT_CORRUPT' in line:
            F16_IPA_IPA1_CNT_CORRUPT += int(re.findall('(\d{8,})', line)[0])
        elif 'INTERNAL_ERROR_CNT' in line:
            INTERNAL_ERROR_CNT += int(re.findall('(\d{8,})', line)[0])
        elif 'HIGH_IN_BUF_PKT_CRC_ERR_COUNT' in line:
            HIGH_IN_BUF_PKT_CRC_ERR_COUNT += int(
                re.findall('(\d{8,})', line)[0])

    result_dic = dict(
        F16_IPA_IPA0_CNT_BAD_CRC=F16_IPA_IPA0_CNT_BAD_CRC,
        F16_IPA_IPA0_CNT_CORRUPT=F16_IPA_IPA0_CNT_CORRUPT,
        F16_IPA_IPA1_CNT_BAD_CRC=F16_IPA_IPA1_CNT_BAD_CRC,
        F16_IPA_IPA1_CNT_CORRUPT=F16_IPA_IPA1_CNT_CORRUPT,
        INTERNAL_ERROR_CNT=INTERNAL_ERROR_CNT,
        HIGH_IN_BUF_PKT_CRC_ERR_COUNT=HIGH_IN_BUF_PKT_CRC_ERR_COUNT
    )
    return [result_dic]


def parse_mds_logging_onboard_error_stats(text, *args, **kwargs):
    port_dict = {}
    for l in text.splitlines():
        # if l.startswith('fc'):
        if 'BAD_WORDS_FROM_DECODER' in l:
            ss = l.split('|')
            name, count = ss[0].strip(), int(ss[2].strip())
            if name in port_dict:
                continue
            port_dict[name] = count
    datas = []
    for p in port_dict:
        datas.append(dict(interface=p, onboard_err=port_dict[p]))
    return datas


def parse_mds_interface_detail_counters(text, *args, **kwargs):
    datas = []
    start = False
    for l in text.splitlines():
        if l.startswith('fc'):
            start = True
            name = l.strip()
        elif not start:
            continue
        elif '0 frames, 0 bytes received' in l:
            start = False
        elif l.startswith('port-channel'):
            break
        elif 'link failures' in l:
            ss = l.split()
            link_fail = int(ss[0])
            sync_loss = int(ss[3])
            signal_loss = int(ss[6])
        elif 'invalid transmission words' in l:
            invalid_tx_words = int(l.split()[0])
        elif 'timeout discards' in l:
            ss = l.split()
            timeout_discard = int(ss[0])
            credit_loss = int(ss[3])
        elif 'invalid CRC' in l:
            invalid_crc = int(l.split()[0])
        elif 'link reset received' in l:
            link_reset_rx = int(l.split()[0])
        elif 'link reset transmitted' in l:
            link_reset_tx = int(l.split()[0])
        elif 'frames discarded' in l:
            frame_discard = int(l.split()[0])
        elif 'framing errors' in l:
            frame_error = int(l.split()[0])
            data = dict(interface=name,
                        link_failure=link_fail,
                        signal_loss=signal_loss,
                        sync_loss=sync_loss,
                        invalid_tx_words=invalid_tx_words,
                        invalid_crc=invalid_crc,
                        timeout_discard=timeout_discard,
                        credit_loss=credit_loss,
                        link_reset_rx=link_reset_rx,
                        link_reset_tx=link_reset_tx,
                        frame_discard=frame_discard,
                        frame_error=frame_error)
            datas.append(data)
    return datas


def parse_mds_logging_loss_of_signal(text, *args, **kwargs):
    return [m.groupdict() for m in re_mds_log_loss_of_signal.finditer(text)]


def parse_internal_mts_buffer_detail(text, *args, **kwargs):
    res = []
    node_sap_opc_dict = defaultdict(int)
    for l in text.splitlines()[2:-1]:
        try:
            ss = l.split()
            node_sap = ss[0]
            if (int(ss[1]) // 1000) > 10:
                node_sap_opc_dict[(ss[0], ss[-3])] += 1
        except:
            pass
    for (node_sap, opc), count in node_sap_opc_dict.items():
        node, sap, _ = node_sap.split('/')
        res.append(dict(node=node, sap=sap, opc=opc, count=count))
    return res


def parse_internal_access_list(text, *args, **kwargs):
    lines = text.splitlines()
    name = 'acl_redirect_0x1_vlan_' + lines[0].split()[-6]
    count = len(lines) - 2
    return [{name: count}]


def parse_nxos_interface_counter_error(text, *args, **kwargs):
    fields = 'Align', 'FCS', 'TX', 'RX', 'UnderSize', 'OutDrop'
    ports = set()
    res = []
    for l in text.splitlines():
        if l.startswith('Eth'):
            ss = l.split()
            if_name = ss[0]
            if if_name in ports:
                break
            ports.add(if_name)
            values = [int(i) for i in ss[1:]]
            if any(values):
                d = {f: v for v in values for f in fields}
                d['Interface'] = if_name
                res.append(d)
    return res


def parse_mds_interface_brief(text, *args, **kwargs):
    res = []
    for l in text.splitlines():
        if l.startswith('fc'):
            ss = l.split()
            res.append(dict(interface=ss[0], vsan=ss[1], status=ss[4]))
    return res
