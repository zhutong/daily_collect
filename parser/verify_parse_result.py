import json
import os
import sys
from pprint import pprint

import glob2


def main():
    items = set()
    for p in glob2.glob('/data/daily_data/output/parsed/cli/*/*.json'):
        with open(p) as f:
            d = json.load(f).get(cmd)
            if d:
                for i in d:
                    s = i[item]
                    if bad_guys and s in bad_guys:
                        print(os.path.basename(p)[:-5], s)
                    items.add(s)
    if not bad_guys:
        pprint(sorted(list(items)))


if __name__ == '__main__':
    cmd = sys.argv[1]
    item = sys.argv[2]
    bad_guys = sys.argv[3:]
    main()
