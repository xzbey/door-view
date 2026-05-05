from flask import Flask, Response, render_template
from camera import Camera
from stream import generate_frames
from config import CAMERA_INDEX, SEGMENT_DURATION, SAVE_MODE, PORT
from deleter import Deleter

app = Flask(__name__)

try:
    camera = Camera(camera_index=CAMERA_INDEX, 
                    segment_duration=SEGMENT_DURATION, 
                    save_mode=SAVE_MODE)
except Exception as e:
    print(f"Error initializing camera: {e}")
    exit(1)
camera.start()

deleter = Deleter(storage_path='storage')
deleter.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def live():
    return Response(generate_frames(camera), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False)
    finally:
        camera.stop()
        deleter.stop()