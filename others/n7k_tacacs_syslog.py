import socket


def send_syslog(syslogs):
    syslog_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for s in syslogs:
        for svr in SYSLOG_SERVERS:
            syslog_socket.sendto(s.encode() (svr, 514))
        time.sleep(SYSLOG_WAIT)


SYSLOG_SERVERS = ('76.7.131.16', '84.7.131.4')
SYSLOG_WAIT = 60

if __name__ == "__main__":
    with open('/tmp/n7k_tacacs_mem_syslog.txt') as f:
        txt = f.read()
    send_syslog(txt.splitlines())
