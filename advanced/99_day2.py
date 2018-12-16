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
    # with open('/tmp/day2_summary.html', 'w') as f:
    #     f.write(body)
    # return
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']

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
    mds_fields = ('F16_IPA_IPA0_CNT_BAD_CRC',
                  'F16_IPA_IPA0_CNT_CORRUPT',
                  'F16_IPA_IPA1_CNT_BAD_CRC',
                  'F16_IPA_IPA1_CNT_CORRUPT',
                  'INTERNAL_ERROR_CNT',
                  'HIGH_IN_BUF_PKT_CRC_ERR_COUNT')
    mds_counters = {}
    for_email = (('N7K', n7k_fields, n7k),
                 ('FEX', fex_fields, fex),
                 ('MDC_ASIC', mds_fields, mds_counters),
                 )
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
                        mds_counters[hostname] = mds_crc
                        break

    # update_day2_summary()
    # send_mail(for_email)
    send_syslog(syslogs)
