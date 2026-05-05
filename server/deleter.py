import os
import time
from datetime import datetime
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
        now = time.time()
        max_age = MAX_STORAGE_DAYS * 86400

        for filename in os.listdir(self.storage_path):
            filepath = os.path.join(self.storage_path, filename)

            if not filename.endswith('.mp4'):
                continue

            file_age = now - os.path.getctime(filepath)
            if file_age > max_age:
                try:
                    os.remove(filepath)
                    print(f"{datetime.now().strftime('%d.%m.%Y %H.%M.%S')} Deleted old file: {filename}")
                except Exception as e:
                    print(f"{datetime.now().strftime('%d.%m.%Y %H.%M.%S')} Error deleting file {filename}: {e}")
    
    def stop(self):
        self.running = False