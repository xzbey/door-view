import cv2
from datetime import datetime
import threading
import time
import subprocess
import os

class Camera:
    def __init__(self, camera_index=0, segment_duration=60, save_mode=True):
        self.camera_index = camera_index
        self.segment_duration = segment_duration
        self.save_mode = save_mode

        self.lock = threading.Lock()
        self.frame = None
        self.running = False

        self.fps, self.width, self.height = self._test_camera()
        print(f"FPS: {self.fps}, Resolution: {self.width}x{self.height}")

    def _test_camera(self, retries=5, delay=5): # пробуем запустить камеру и получить параметры
        for attempt in range(retries):
            cap = cv2.VideoCapture(self.camera_index)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                return fps, width, height
            cap.release()
            print(f"Attempt {attempt + 1} to open camera failed, retrying...")
            time.sleep(delay)
        raise Exception(f"Failed to open camera after {retries} attempts")


    # ============= FFMPEG ЗАПИСЬ =============
    def _start_ffmpeg(self): # запускает ffmpeg subprocess для записи в файл без перекодирования
        os.makedirs("storage", exist_ok=True)
        path = f"storage/{self._timestamp()}.mp4"

        cmd = [
            "ffmpeg",
            "-loglevel", "error", # не спамить логи
            "-rtsp_transport", "tcp", # tcp лучше для ip камеры
            "-i", str(self.camera_index),
            "-c", "copy", # без перекодирования
            "-t", str(self.segment_duration),
            "-y", # перезаписывать если файл есть
            path]
        
        print(f"Starting ffmpeg with command: {cmd}")
        return subprocess.Popen(cmd)

    def _record_loop(self): # запускает хуйню выше в цикле, пока running true. Типа идет сейв по частям длиной segment_duration
        while self.running:
            process = self._start_ffmpeg()
            process.wait()
            if self.running:
                print("ffmpeg process ended, starting new segment...")


    # ============= OpenCV СТРИМ =============
    def _capture_loop(self, delay=5): # читает фреймы из камеры и сохраняет в self.frame для стрима
        while self.running:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                print(f"{self._timestamp()}: Failed to open camera for streaming")
                time.sleep(delay)
                continue

            print(f"{self._timestamp()}: Camera opened for streaming")
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print(f"{self._timestamp()}: Failed to read frame from camera")
                    break

                cv2.putText(
                    frame,
                    self._timestamp(),
                    (10, self.height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255), #BGR
                    2,
                    cv2.LINE_AA
                )

                with self.lock:
                    self.frame = frame.copy()
            
            cap.release()
            print(f"{self._timestamp()}: Camera released after streaming failure, retrying...")
            if self.running:
                time.sleep(delay)


    # ============= Интерфейс =============
    def start(self):
        self.running = True
        
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        if self.save_mode:
            self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
            self._record_thread.start()

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
    
    def stop(self):
        self.running = False
        self._capture_thread.join(timeout=5)
        if self.save_mode:
            self._record_thread.join(timeout=5)

    @staticmethod
    def _timestamp():
        return datetime.now().strftime('%d.%m.%Y %H.%M.%S')