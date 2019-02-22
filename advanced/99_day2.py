import json
import logging
from collections import defaultdict

import requests
from jinja2 import Template

from config import *

body_template = '''
    <style>
        h4 {
            margin: 15px 0 0 0;
        }
        table {
            width: 100%;
            max-width: 100%;
            border: 1px solid #aaaaaa;
            border-spacing: 0;
            border-collapse: collapse;
            margin: 3px 0;
        }
        th {
            color: white;
            background-color: #337ab7;
        }
        th, td {
            text-align: center;
            line-height: 1.5;
            border: 1px solid #aaaaaa;
        }
        .hostname {
            font-weight: bold;
        }
        .alarm5 {
            background-color: #ff0000;
            color: white;
        }
        .alarm4 {
            background-color: #febcb4;
        }
        .alarm3 {
            background-color: #fedd8e;
        }
    </style>
    <h3><a href="{{url}}day2/index.html">Day2问题摘要</a></h3>
    {% for name, fields, alarm in alarms %}
    {% if alarm.items() %}
    <h4>{{ name }}</h4>
    <table>
        <thead>
            <th>Hostname</th>
            {% for f in fields %}
            <th>{{ f }}</th>
            {% endfor %}
        </thead>
        <tbody>
        {% for hostname, datas in alarm.items() %}
            {% for data in datas %}
            <tr>
                <td class="hostname">{{ hostname }}</td>
                {% for f in fields %}
                <td class="alarm{{ data.get(f, {}).get('alarm', 0) }}">
                    {{ data.get(f, {})['value'] }}
                </td>
                {% endfor %}
            </tr>
            {% endfor %}
        {% endfor %}
            </tbody>
    </table>
        {% endif %}
    {% endfor %}
    '''


def __get_device_info():
    rows = requests.get(DEVICE_INFO_URL).json()
    devices = {}
    for r in rows['data']:
        devices[r['hostname']] = r
    return devices


def send_syslog(syslogs):
    for s in syslogs:
        requests.post(SEND_CPE_SYSLOG_URL, json.dumps(s))


def send_mail(alarms):
    body = Template(body_template).render(url=APP_URL,
                                          alarms=alarms)
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']
    externals = 'icbc_mds@cisco.com', 'xiaoqingyang@eccom.com.cn'
    receivers.extend(externals)

    data = {
        'subject': '[健康检查] Day2问题摘要',
        'body_html': body,
        'receivers': receivers,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def update_day2_summary():
    res = requests.get(APP_URL+'day2/api/refresh_summary')
    if res.status_code == 200:
        logging.info('Day2 summary updated')


def main():
    logging.info('Send alert syslog and email')
    devices = __get_device_info()
    with open(DAILY_ALARMED_FN) as f:
        all_alerts = json.load(f)

    syslogs = []
    n7k_fields = ('total_memory',
                  'usage',
                  'pecentage',
                  'slot_5_raid',
                  'slot_6_raid',
                  'slot_5_log_space',
                  'slot_6_log_space')
    n7k = {}
    fex_fields = ('fex',
                  'pw1_status',
                  'pw1_vout',
                  'pw2_status',
                  'pw2_vout',
                  'RX_CRC_STOMPED',
                  'RX_CRC_NOT_STOMPED')
    fex = {}
    n5k_logic = {}
    mds_asic_fields = ('F16_IPA_IPA0_CNT_BAD_CRC',
                       'F16_IPA_IPA0_CNT_CORRUPT',
                       'F16_IPA_IPA1_CNT_BAD_CRC',
                       'F16_IPA_IPA1_CNT_CORRUPT',
                       'INTERNAL_ERROR_CNT',
                       'HIGH_IN_BUF_PKT_CRC_ERR_COUNT')
    mds_asic = {}
    mds_port_fields = ('interface',
                       'rx_power',
                       'onboard_err',
                       'sync_loss',
                       'credit_loss',
                       'signal_loss',
                       'invalid_tx_words',
                       'link_reset_rx',
                       'link_reset_tx',
                       'timeout_discard',
                       'link_failure',
                       'invalid_crc',
                       'frame_error',
                       'frame_discard')
    mds_port = defaultdict(list)
    for_email = (('N7K', n7k_fields, n7k),
                 ('FEX', fex_fields, fex),
                 ('MDS_ASIC_COUNTERS', mds_asic_fields, mds_asic),
                 ('MDS_PORT_COUNTERS', mds_port_fields, mds_port),
                 )
    mds_port_tmp = defaultdict(dict)
    for alerts in all_alerts:
        for hostname, datas in alerts:
            # N7K alarms
            one_n7k_info = {}
            for i in (5, 6):
                n7k_slot_raid = datas.get(
                    'slot %d show system internal raid' % i)
                if n7k_slot_raid:
                    content = '%s SLOT %d internal raid error' % (hostname, i)
                    item = dict(cpe_name='N7K',
                                alert_group='KERN-3-SYSTEM_MSG',
                                level=7,
                                ip=devices[hostname]['ip'],
                                content=content)
                    syslogs.append(item)
                    one_n7k_info.update(n7k_slot_raid[0])
                n7k_slot_flash = datas.get(
                    'slot %d show system internal flash' % i)
                if n7k_slot_flash:
                    content = '%s SLOT %d no free log space' % (hostname, i)
                    item = dict(cpe_name='N7K',
                                alert_group='N7K-5-LOG_SPACE',
                                level=7,
                                ip=devices[hostname]['ip'],
                                content=content)
                    syslogs.append(item)
                    one_n7k_info.update(n7k_slot_flash[0])

            n7k_tacacs_mem = datas.get('show processes memory | in taca')
            if n7k_tacacs_mem:
                if n7k_tacacs_mem[0]['pecentage']['alarm'] > 3:
                    one_n7k_info.update(n7k_tacacs_mem[0])
            if one_n7k_info:
                n7k[hostname] = [one_n7k_info]

            # FEX alarms
            fex_pw = datas.get('attach fex')
            rows = []
            if fex_pw:
                for r in fex_pw:
                    for i in (1, 2):
                        if r['pw%d_status' % i].get('alarm'):
                            fex_id = r['fex']['value']
                            content = '%s FEX %s power supply %d fail' % (
                                hostname, fex_id, i)
                            item = dict(cpe_name='N2K',
                                        alert_group='N2K-3-POWER_FAIL',
                                        level=7,
                                        ip=devices[hostname]['ip'],
                                        content=content)
                            syslogs.append(item)
                    if r['RX_CRC_STOMPED'].get('alarm', 0) > 3:
                        rows.append(r)
                    elif r['RX_CRC_NOT_STOMPED'].get('alarm', 0) > 3:
                        rows.append(r)
                    elif r['pw1_status'].get('alarm', 0) > 3:
                        rows.append(r)
                    elif r['pw2_status'].get('alarm', 0) > 3:
                        rows.append(r)
                if rows:
                    fex[hostname] = rows

            # MDS ASIC CRC alarms
            mds_crc = datas.get('show hardware internal errors all')
            if mds_crc:
                for k, v in mds_crc[0].items():
                    if v.get('alarm', 0) > 1:
                        mds_crc['value'] = mds_crc['increased']
                        mds_asic[hostname] = mds_crc
                        break

            # MDS PORT counters
            port_counters = datas.get('show interface detail-counters', [])
            for row in port_counters:
                for k, v in row.items():
                    if v.get('alarm', 0) > 1:
                        mds_port_tmp[hostname][row['interface']['value']] = row
                        break
            # MDS PORT RX Power
            if 'NF97SN' in hostname or 'JD97SN' in hostname:
                port_trans = datas.get('show interface trans detail', [])
                for row in port_trans:
                    v = row['rx_pwr']
                    if v.get('alarm', 0) >= 2:
                        i = row['interface']['value']
                        if i in mds_port_tmp[hostname]:
                            mds_port_tmp[hostname][i]['rx_power'] = v
                        else:
                            mds_port_tmp[hostname][i] = {'rx_power': v}
            # MDS Onbroad errors
            mds_onboard = datas.get('show logging onboard error-stats', [])
            for row in mds_onboard:
                # print(row)
                v = row['onboard_err']
                if v.get('alarm', 0) > 2:
                    v['value'] = v['increased']
                    i = row['interface']['value']
                    if i in mds_port_tmp[hostname]:
                        mds_port_tmp[hostname][i]['onboard_err'] = v
                    else:
                        mds_port_tmp[hostname][i] = {'onboard_err': v}
    for h, ports in mds_port_tmp.items():
        for i, p in ports.items():
            p['interface'] = dict(value=i)
            mds_port[h].append(p)
    update_day2_summary()
    send_mail(for_email)
    send_syslog(syslogs)
