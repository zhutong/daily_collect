import json
import logging
import os

from jinja2 import Template

import requests

from config import *


MAIN_PATH = opj(PARSED_CLI_PATH, 'main')
GET_WL2_MAIL_URL = 'http://76.7.3.54/apps/tools/api/get_wl_mail_list_by_tag?tag=wl2'
# GET_WL2_MAIL_URL = 'http://127.0.0.1:9116/apps/tools/api/get_wl_mail_list_by_tag?tag=wl2'

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
    <h3><a href="http://76.7.3.54/apps/day2/index.html">Day2问题摘要</a></h3>
    {% for name, fields, alarm in alarms %}
    <h4>{{ name }}</h4>
    <table>
        <thead>
            <th>Hostname</th>
            {% for f in fields %}
            <th>{{ f }}</th>
            {% endfor %}
        </thead>
        <tbody>
        {% if alarm.items() %}
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
        {% else %}
            <tr><td colspan="{{ fields.__len__()+1 }}"> 未发现异常信息 </td></tr>
        {% endif %}
        </tbody>
    </table>
    {% endfor %}
    '''


def __get_device_info():
    devices = {}
    for fn in os.listdir(MAIN_PATH):
        hostname = fn[:-5]
        if '70RT' not in hostname:
            continue
        with open(os.path.join(MAIN_PATH, fn)) as f:
            data = json.load(f)
        version = data.get('show version')
        if version:
            v = version[0].get('version', '')
            devices[hostname] = dict(value=v)
    return devices


def send_mail(alarms):
    subject = '[健康检查] Day2问题摘要'
    if alarms[0][0]:
        body = Template(body_template).render(alarms=alarms)
    else:
        body = ''
        subject += '：今天没发现问题'
    # print(body)
    # return
    receivers = requests.get(GET_WL2_MAIL_URL).json()['mail_list']
    data = {
        'subject': subject,
        'body_html': body,
        'receivers': receivers,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def main():
    devices = __get_device_info()
    with open(DAILY_ALARMED_FN) as f:
        all_alerts = json.load(f)

    n7k_fields = ('total_memory',
                  'usage',
                  'pecentage',
                  'version',
                  # 'slot_5_raid',
                  # 'slot_6_raid',
                  # 'slot_5_log_space',
                  # 'slot_6_log_space',
                  )
    n7k = {}
    for_email = (('N7K', n7k_fields, n7k),)

    for alerts in all_alerts:
        for hostname, datas in alerts:
            if '70RT' not in hostname:
                continue
            one_n7k_info = {}
            # for i in (5, 6):
            #     n7k_slot_raid = datas.get(
            #         'slot %d show system internal raid' % i)
            #     if n7k_slot_raid:
            #         content = '%s SLOT %d internal raid error' % (hostname, i)
            #         item = dict(cpe_name='N7K',
            #                     alert_group='KERN-3-SYSTEM_MSG',
            #                     level=7,
            #                     ip=devices[hostname]['ip'],
            #                     content=content)
            #         syslogs.append(item)
            #         one_n7k_info.update(n7k_slot_raid[0])
            #     n7k_slot_flash = datas.get(
            #         'slot %d show system internal flash' % i)
            #     if n7k_slot_flash:
            #         content = '%s SLOT %d no free log space' % (hostname, i)
            #         item = dict(cpe_name='N7K',
            #                     alert_group='N7K-5-LOG_SPACE',
            #                     level=7,
            #                     ip=devices[hostname]['ip'],
            #                     content=content)
            #         # syslogs.append(item)
            #         one_n7k_info.update(n7k_slot_flash[0])

            n7k_tacacs_mem = datas.get('show processes memory | in taca')
            if n7k_tacacs_mem:
                if n7k_tacacs_mem[0]['pecentage']['alarm'] > 3:
                    n7k_tacacs_mem[0]['version'] = devices.get(hostname, {})
                    one_n7k_info.update(n7k_tacacs_mem[0])
            if one_n7k_info:
                n7k[hostname] = [one_n7k_info]

    send_mail(for_email)
