import json
import logging
from collections import defaultdict

import requests

import config as c


reset_script_file = '/tmp/reset_mts_buffer.txt'
table_file = '/tmp/mts_buffer_table.html'

t0 = '// {h} ({i})\r\n{m} {i}\r\n//{h}//'
t1 = 'debug mts drop node {node} sap {sap} from {q} opcode {opc} age 10'
t2 = '<tr><td>{h}</td><td>{slot}</td><td>{node}</td><td>{sap}</td><td>{q}</td><td>{count}</td></tr>'

body_part = u'''
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
            th,
            td {
                text-align: center;
                line-height: 1.5;
                border: 1px solid #aaaaaa;
            }
        </style>
        <h4>System Internal MTS Buffers</h4>
        <table>
            <thead>
                <th>Hostname</th>
                <th>Slot</th>
                <th>Node</th>
                <th>SAP</th>
                <th>Queue</th>
                <th>Count</th>
            </thead>
            <tbody>'''


def __get_device_info():
    rows = requests.get(c.DEVICE_INFO_URL).json()
    devices = {}
    for r in rows['data']:
        devices[r['hostname']] = r
    return devices


def create_report(mts_info):
    device_dict = __get_device_info()
    report_lines = []
    all_scripts = []
    for hostname, slot_dict in mts_info.items():
        script_lines = []
        for slot, mts_list in slot_dict.items():
            report_entry = defaultdict(int)
            script_entry = defaultdict(list)
            for mts in mts_list:
                node, sap, q = mts['node_sap_q'].split('/')
                report_entry[(node, sap, q)] += mts['count']
                script_entry[(node, sap, q)].append(mts['opc'])
            for (node, sap, q), count in report_entry.items():
                if count < 15:
                    continue
                report_lines.append(t2.format(h=hostname,
                                              slot=slot,
                                              node=node,
                                              sap=sap,
                                              q=q,
                                              count=count
                                              ))
                if slot:
                    script_lines.append('attach %s' % slot)
                for opc in script_entry[(node, sap, q)]:
                    script_lines.append(t1.format(h=hostname,
                                                  node=node,
                                                  sap=sap,
                                                  q=q,
                                                  opc=opc
                                                  ))
                if slot:
                    script_lines.append('exit\r\n')
        if script_lines:
            try:
                ip = device_dict[hostname]['ip']
                method = device_dict[hostname]['method'] or 'ssh'
            except:
                ip = 'unknown'
                method = 'ssh'
            all_scripts.append(t0.format(h=hostname, i=ip, m=method))
            all_scripts.append('\r\n'.join(script_lines))
            all_scripts.append('\r\n')


    with open(reset_script_file, 'w') as f:
        f.write('\r\n'.join(all_scripts))

    table = body_part + '\r\n'.join(report_lines) + '</tbody></table>'
    with open(table_file, 'w') as f:
        f.write(table)

    return table


def send_mail(mail_body):
    # return
    receivers = requests.get(c.GET_MAIL_LIST_URL).json()['mail_list']
    receivers.append('icbc_mds@cisco.com')
    data = {
        "subject": "Day2: N7K MTS buffer泄漏",
        'body_html': mail_body,
        "attach": [reset_script_file],
        "receivers": receivers,
    }
    res = requests.post(c.SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def main():
    logging.info('Create MTS report')
    mts_info = defaultdict(dict)
    path = c.opj(c.PARSED_CLI_PATH, 'main')
    for fn in c.os.listdir(path):
        hostname = fn[:-5]
        with open(c.opj(path, fn)) as f:
            data = json.load(f)
        for cmd in data:
            if 'mts buffer' in cmd:
                if 'slot' in cmd:
                    slot = cmd.split()[1]
                else:
                    slot = ''
                mts_info[hostname][slot] = data[cmd]
    send_mail(create_report(mts_info))
