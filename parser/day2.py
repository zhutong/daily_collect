# -*- coding: utf-8 -*-

import logging
import re


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


def parse_mds_crc_err(text, *args, **kwargs):
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


def parse_stp_summary_total(text, *args, **kwargs):
    try:
        n = int(text.splitlines()[1].split()[-1])
    except:
        n = 0
    return [dict(logic_numbers=n)]
