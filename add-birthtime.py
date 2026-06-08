import os
import time
import datetime
from pathlib import Path

p = Path(r"/home/mlab/zettlekasten")

for file in p.iterdir():
    if file.is_file():
        file_name = file.name

        file_ct = os.path.getctime(file)
        ct_file = time.ctime(file_ct)
        t_obj = time.strptime(ct_file)
        T_stamp = time.strftime("%Y%m%d%H%M", t_obj)

        new_name = (T_stamp + "-" + file_name)
        print("Renaming file {0} to {1}".format(file_name, new_name))
        os.rename(file, new_name)
