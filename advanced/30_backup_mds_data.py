import time
import logging
import os
import zipfile

from config import *

backup_data_path = '/data/mds_history'


def main():
    logging.info('Back MDS history data')
    fn = time.strftime('%Y%m%d.zip')
    raw_data_path = os.path.join(RAW_CLI_PATH, 'main')
    today_backup = os.path.join(backup_data_path, fn)
    with zipfile.ZipFile(today_backup, 'w', zipfile.ZIP_DEFLATED) as zipped:
        for fn in os.listdir(raw_data_path):
            if '97SN' in fn:
                zipped.write(os.path.join(raw_data_path, fn), fn)
    logging.info('Back MDS history data finished')
    fns = os.listdir(backup_data_path)
    if len(fns) > 30:
        fns.sort()
        os.remove(os.path.join(backup_data_path, fns[0]))
