# coding: utf-8

import datetime
import json
import logging
import time

import requests
from tornado.log import enable_pretty_logging


def get_date():
    t0 = datetime.date.today()
    t1 = t0 + datetime.timedelta(days=1)
    today = '%d-%02d-%02d' % (t0.year, t0.month, t0.day)
    tomorrow = '%d-%02d-%02d' % (t1.year, t1.month, t1.day)
    return today, tomorrow


def get_duty_data():
    URL = 'http://76.7.3.170/apps/duty/api/duty_data'
    duty_data = requests.get(URL).json()['data']
    return duty_data


def get_person(duty_data, date):
    roles = (('A', u'A岗'),
             ('day', u'白班'),
             ('night', u'夜班'),
             ('JDB1', u'嘉定B1'),
             ('JDB2', u'嘉定B2'),
             ('C', u'C岗'),
             )
    data = duty_data[date]
    persons = []
    for (k, name) in roles:
        person = data[k]
        if not person:
            persons.append((name, '', ''))
        elif person in WORK_AT_JD:
            persons.append((name, person, u'嘉定'))
        else:
            persons.append((name, person, u'外高桥'))
    return persons


def render(duty_data, today, tomorrow):
    html0 = u'''
    <html>

    <head>
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
    </head>
    '''

    html1 = u'''
    <body>
        <h1>值班人员信息</h1>
        <table>
            <tr>
                <th colspan="3">今天 %s</th>
                <th colspan="3">明天 %s</th>
            </tr>
            <tr>
                <th>岗位</th>
                <th>值班人员</th>
                <th>园区</th>
                <th>岗位</th>
                <th>值班人员</th>
                <th>园区</th>
            </tr>
            %s
        </table>
    </body>

    </html>'''

    template = u'<td>%s</td><td>%s</td><td>%s</td>'
    lines = []
    t0 = get_person(duty_data, today)
    t1 = get_person(duty_data, tomorrow)
    for i in range(6):
        lines.append('<tr>')
        lines.append(template % t0[i])
        lines.append(template % t1[i])
        lines.append('</tr>')
    html = html0 + html1 % (today, tomorrow, '\n'.join(lines))
    return html


def send_mail(body):
    SEND_MAIL_URL = 'http://76.7.3.54/apps/tools/api/send_mail'
    data = {
        'subject': u'值班人员信息',
        'body_html': body,
        'receivers': REVEIVERS,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))


def main():
    enable_pretty_logging()
    last_date = datetime.datetime.today()
    while True:
        time.sleep(300)
        now = datetime.datetime.now()
        if now.day != last_date.day and now.hour == SEND_AT:
            try:
                today, tomorrow = get_date()
                logging.info(u'获取排班表')
                duty_data = get_duty_data()
                logging.info(u'生成邮件内容')
                html = render(duty_data, today, tomorrow)
                logging.info(u'发送邮件')
                send_mail(html)
                last_date = now
                time.sleep(72000)
            except:
                logging.error(u'发生错误')


WORK_AT_JD = u'''
朱敏敏 周洁楷 赵丰 张怡雯 张瑾 张建华 印凌潼 杨易之 杨沛熠 徐信 吴文婕 王思源
王芳 汪闻杰 陶佩华 邵佳罗 秦英杰 浦晓君 陆人杰 李晗 金永铭 蒋欣怡 黄奕敏 胡政
胡克宁 何建慧 傅冰 陈琳 陈凡 曾繁雄 蔡怡静 蔡舒翔 边燕娣 敖永洁
'''.strip().split()
REVEIVERS = ['zhiyi.he@dc.icbc.com.cn',
             'fanxiong.zen@dc.icbc.com.cn']
SEND_AT = 7

main()