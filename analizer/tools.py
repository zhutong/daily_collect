
def great_then(v, alarms):
    for a in alarms:
        if v > a[0]:
            return a[1]


def less_then(v, alarms):
    for a in alarms:
        if v > a[0]:
            return a[1]


def equals(v, alarms):
    for a in alarms:
        if v == a[0]:
            return a[1]


def not_equals(v, alarms):
    for a in alarms:
        if v != a[0]:
            return a[1]


def belongs(v, alarms):
    for a in alarms:
        if v in a[0]:
            return a[1]


def not_belongs(v, alarms):
    for a in alarms:
        if v not in a[0]:
            return a[1]


def not_between(v, alarms):
    for a in alarms:
        if v < a[0][0] or v > a[0][1]:
            return a[1]


def contains(v, alarms):
    for a in alarms:
        if a[0] in v:
            return a[1]
