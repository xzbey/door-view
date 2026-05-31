import os
import time
from datetime import datetime
from utils import _timestamp
import threading
from config import MAX_STORAGE_DAYS, TIME_SLEEP

class Deleter:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._clean_loop, daemon=True).start()
    
    def _clean_loop(self):
        while self.running:
            self.delete_old_files()
            time.sleep(TIME_SLEEP)
    
    def delete_old_files(self):
        for filename in os.listdir(self.storage_path):
            if not filename.endswith('.mp4'):
                continue

            filepath = os.path.join(self.storage_path, filename)
            try:
                file_date = datetime.strptime(filename[:-4], '%d.%m.%Y_%H.%M.%S')
            except ValueError:
                continue

            file_age = (datetime.now() - file_date).days
            if file_age > MAX_STORAGE_DAYS:
                try:
                    os.remove(filepath)
                    print(f"{_timestamp()} Deleted old file: {filename}")
                except Exception as e:
                    print(f"{_timestamp()} Error deleting file {filename}: {e}")

    def stop(self):
        self.running = False