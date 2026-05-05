import cv2

def generate_frames(camera):
    while True:
        frame = camera.get_frame()

        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            