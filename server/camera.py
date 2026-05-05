import cv2
from datetime import datetime
import threading
import time

class Camera:
    def __init__(self, camera_index=0, segment_duration=60, save_mode=True):
        self.cap = cv2.VideoCapture(camera_index)
        self.segment_duration = segment_duration
        self.save_mode = save_mode

        self.lock = threading.Lock()
        self.frame = None
        self.running = False

        if not self.cap.isOpened():
            raise Exception("Could not open camera")
        else:
            print("Camera opened successfully")
        
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"FPS: {self.fps}, Resolution: {self.width}x{self.height}")

    def _new_writer(self):
        return cv2.VideoWriter(f"storage/{datetime.now().strftime('%d.%m.%Y %H.%M.%S')}.mp4", 
                               cv2.VideoWriter_fourcc(*"avc1"), 
                               self.fps, 
                               (self.width, self.height), 
                               True)

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        writer = self._new_writer() if self.save_mode else None
        last_segment_time = time.time()

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame from camera")
                break

            if time.time() - last_segment_time >= self.segment_duration:
                if self.save_mode:
                    writer.release()
                    writer = self._new_writer()
                last_segment_time = time.time()
            
            cv2.putText(
                frame,
                datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                (10, self.height - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255), #BGR
                2,
                cv2.LINE_AA
            )

            writer.write(frame) if self.save_mode else None

            with self.lock:
                self.frame = frame.copy()
        
        writer.release() if self.save_mode else None

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
    
    def stop(self):
        self.running = False
        self._thread.join()
        self.cap.release()

    
