import os
import time
import datetime
from pathlib import Path
from collections import defaultdict

def main():
    p = Path(r"/home/mlab/zettelkasten")
    allowed_dirs = ["00-INBOX", "01-ARCHIVE", "02-INPUT"]
    d = defaultdict(list)

    for entry in p.iterdir():
        if entry.is_dir() and entry.name in allowed_dirs:
            for file in entry.iterdir():
                if file.is_file():
                    file_name = file.name
                    date = file_name[:8]
                    name = file_name[8:]
                    d[date].append(name)
    for date in d.keys():
        generate_daily_note(date, d.get(date))

def generate_daily_note(date, notes):
    daily_note_path = Path(r"/home/mlab/zettelkasten/01-ARCHIVE/daily-notes")
    
    file_name = date[:4] + "-" + date[4:6] + "-" + date[6:8] + ".md"

    with open(os.path.join(daily_note_path, file_name), "x") as f:
        for note in notes:
            f.write("[[" + date + note + "]]\n")

if __name__ == "__main__":
    main()
