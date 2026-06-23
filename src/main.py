from flask import Flask, render_template, abort, send_file, request
from camera import Camera
from config import STORAGE_PATH, HLS_PATH, PORT
import os
from datetime import datetime
import atexit

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
app = Flask(__name__)

try:
    camera = Camera()
except Exception as e:
    print(f"Error initializing camera: {e}")
    exit(1)
camera.start()

@atexit.register
def cleanup_on_exit():
    print("Flask is closing, clearing resources...")
    camera.stop()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream/<path:filename>')
def live(filename):
    path = os.path.join(STORAGE_PATH, HLS_PATH, filename)
    if not os.path.exists(path):
        abort(404)
    mimetype = 'application/vnd.apple.mpegurl' if filename.endswith('.m3u8') else 'video/MP2T'
    return send_file(path, mimetype=mimetype)

@app.route('/records')
def records():
    return render_template('records.html', 
                            records=sorted(
                               [f for f in os.listdir(STORAGE_PATH) if f.endswith('.mp4')], 
                               key=lambda x: datetime.strptime(x[:-4], '%d.%m.%Y_%H.%M.%S'),
                               reverse=True)
                            )

@app.route('/records/<path:filename>')
def give_record(filename):
    path = os.path.join(STORAGE_PATH, filename)
    if not os.path.exists(path):
        abort(404)
    as_attachment = request.args.get('dl') == '1'
    return send_file(path, mimetype='video/mp4', as_attachment=as_attachment, download_name=filename)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False)
    finally:
        camera.stop()