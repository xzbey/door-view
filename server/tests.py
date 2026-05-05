# camera test (cv2.imshow) ==============================
from camera import Camera
import cv2

try:
    camera = Camera(save_mode=False)
except Exception as e:
    print(f"Error initializing camera: {e}")
    exit(1)
    
camera.start()

while True:
    frame = camera.get_frame()
    if frame is not None:
        cv2.imshow("Camera", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.stop()
# camera test (cv2.imshow) ==============================