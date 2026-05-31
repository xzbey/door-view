from flask import Flask, Response, render_template, abort, send_file
from camera import Camera
from stream import generate_frames
from config import CAMERA_INDEX, SEGMENT_DURATION, SAVE_MODE, PORT
from deleter import Deleter
import os

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..' , 'storage')
app = Flask(__name__)

try:
    camera = Camera(storage_path=STORAGE_DIR, 
                    camera_index=CAMERA_INDEX, 
                    segment_duration=SEGMENT_DURATION, 
                    save_mode=SAVE_MODE)
except Exception as e:
    print(f"Error initializing camera: {e}")
    exit(1)
camera.start()

deleter = Deleter(storage_path=STORAGE_DIR)
deleter.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def live():
    return Response(generate_frames(camera), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/records')
def records():
    return render_template('records.html', 
                           records=[f for f in os.listdir(STORAGE_DIR) if f.endswith('.mp4')])

@app.route('/records/<path:filename>')
def give_record(filename):
    path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype='video/mp4')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False)
    finally:
        camera.stop()
        deleter.stop()