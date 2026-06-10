import cv2
from utils import _timestamp
import threading
import time
import subprocess
import os
from config import STORAGE_PATH, CAMERA_INDEX, SAVE_MODE, HLS_PATH, MOTION_COOLDOWN, MOTION_MIN_AREA, MOTION_VAR_THRESHOLD, MOTION_HISTORY

class Camera:
    def __init__(self, storage_path=STORAGE_PATH, camera_index=CAMERA_INDEX, save_mode=SAVE_MODE):
        self.storage_path = storage_path
        self.camera_index = camera_index
        self.save_mode = save_mode

        self.lock = threading.Lock()
        self.frame = None
        self.running = False

        self._record_process = None
        self._record_lock = threading.Lock()
        self._last_motion_time = 0

        self._hls_process = None
        self._hls_lock = threading.Lock()

        self.fps, self.width, self.height = self._test_camera()
        self._validate_path()
        print(f"FPS: {self.fps}, Resolution: {self.width}x{self.height}")

    def _validate_path(self):
        if not os.path.isabs(self.storage_path):
            raise Exception(
                f"STORAGE_PATH должен быть абсолютным путём\nТекущий: '{self.storage_path}'"
            )
        os.makedirs(self.storage_path, exist_ok=True)

        test_file = os.path.join(self.storage_path, '.write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception:
            raise Exception(f"Нет прав на запись в {self.storage_path}")

    def _test_camera(self, retries=10, delay=15): # пробуем запустить камеру и получить параметры
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


    # ============= ЗАХВАТ ФРЕЙМОВ (только для MOG2) =============
    def _capture_loop(self, delay=5): # читает фреймы из камеры и сохраняет в self.frame
        while self.running:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                print(f"{_timestamp()}: Failed to open camera for streaming")
                time.sleep(delay)
                continue

            print(f"{_timestamp()}: Camera opened for streaming")
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print(f"{_timestamp()}: Failed to read frame from camera")
                    break

                with self.lock:
                    self.frame = frame.copy()
            
            cap.release()
            print(f"{_timestamp()}: Camera released after streaming failure, retrying...")
            if self.running:
                time.sleep(delay)


    # ============= ДЕТЕКТ ДВИЖЕНИЙ =============
    def _detect_loop(self, cooldown=MOTION_COOLDOWN, min_area=MOTION_MIN_AREA, history=MOTION_HISTORY, varThreshold=MOTION_VAR_THRESHOLD): # детект движений и обновляет self._last_motion_time
        # https://habr.com/ru/articles/786436/
        mog2 = cv2.createBackgroundSubtractorMOG2(history=history, varThreshold=varThreshold, detectShadows=False)
        
        frame_count = 0
        for _ in range(history*2):
            with self.lock:
                frame = self.frame.copy() if self.frame is not None else None
            if frame is not None:
                mog2.apply(frame)
                frame_count += 1
            time.sleep(0.1)
        print(f"{_timestamp()}: MOG2 warmup done ({frame_count}/{history} frames)")
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        while self.running:
            with self.lock:
                frame = self.frame.copy() if self.frame is not None else None
            
            if frame is None:
                time.sleep(1)
                continue
            
            fg_mask = mog2.apply(frame)

            _, mask_thresh = cv2.threshold(fg_mask, 180, 255, cv2.THRESH_BINARY)
            mask_clean = cv2.morphologyEx(mask_thresh, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_detected = any(cnt for cnt in contours if cv2.contourArea(cnt) > min_area)

            if motion_detected:
                self._last_motion_time = time.time()
                print(f"{_timestamp()}: Motion detected")
                if not self._is_recording():
                    print(f"{_timestamp()}: Starting recording due to motion")
                    self._start_recording()
            else:
                if self._is_recording() and (time.time() - self._last_motion_time) > cooldown:
                    print(f"{_timestamp()}: Stopping recording due to inactivity")
                    self._stop_recording()
            
            time.sleep(0.1)

    def _start_recording(self):
        with self._record_lock:
            if self._record_process is not None:
                print(f"{_timestamp()}: Record process already running")
                return

            os.makedirs(self.storage_path, exist_ok=True)
            path = os.path.join(self.storage_path, f"{_timestamp()}.mp4")
            cmd = [
                "ffmpeg",
                "-loglevel", "error", # не спамить логи
                "-rtsp_transport", "tcp", # tcp лучше для ip камеры
                "-i", str(self.camera_index),
                "-c", "copy", # без перекодирования
                "-an", # без аудио
                "-y", # перезаписывать если файл есть
                path]
            
            print(f"{_timestamp()}: Starting ffmpeg: {path}")
            self._record_process = subprocess.Popen(cmd)
    
    def _stop_recording(self):
        with self._record_lock:
            if self._record_process is not None:
                print(f"{_timestamp()}: Stopping ffmpeg")
                self._record_process.terminate()
                try:
                    self._record_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print(f"{_timestamp()}: ffmpeg did not terminate in time, killing")
                    self._record_process.kill()
                self._record_process = None

    def _is_recording(self):
        with self._record_lock:
            return self._record_process is not None and self._record_process.poll() is None

    
    # ============= HLS стримчик =============
    def _hls_loop(self, hls_path=HLS_PATH):
        path = os.path.join(self.storage_path, hls_path)
        os.makedirs(path, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", str(self.camera_index),
            "-c", "copy",
            "-an",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+append_list",
            os.path.join(path, "stream.m3u8")
        ]

        while self.running:
            print(f"{_timestamp()}: Starting HLS ffmpeg")
            with self._hls_lock:
                self._hls_process = subprocess.Popen(cmd)
            
            self._hls_process.wait()
            if self.running:
                print(f"{_timestamp()}: HLS ffmpeg stopped unexpectedly, restarting in 5s...")
                time.sleep(5)

    def _start_hls(self):
        threading.Thread(target=self._hls_loop, daemon=True).start()

    def _stop_hls(self):
        with self._hls_lock:
            if self._hls_process is not None:
                print(f"{_timestamp()}: Stopping HLS ffmpeg")
                self._hls_process.terminate()
                try:
                    self._hls_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print(f"{_timestamp()}: HLS ffmpeg did not terminate in time, killing")
                    self._hls_process.kill()
                self._hls_process = None


    # ============= Интерфейс =============
    def start(self):
        self.running = True
        
        self._start_hls()

        if self.save_mode:
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            self._detect_thread = threading.Thread(target=self._detect_loop, daemon=True)
            self._detect_thread.start()

    
    def stop(self):
        self.running = False
        if self.save_mode:
            self._capture_thread.join(timeout=5)
            self._detect_thread.join(timeout=5)
        self._stop_recording()
        self._stop_hls()
