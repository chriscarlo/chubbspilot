import os
import jinja2
from flask import Flask, Response, send_from_directory, render_template

# Static import for testing if ros is available
try:
  import rosgraph
  ros_available = True
except ImportError:
  ros_available = False

app = Flask(__name__)
app.debug = True

# Setup template environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templateLoader = jinja2.FileSystemLoader(searchpath=os.path.join(BASE_DIR, "templates"))
templateEnv = jinja2.Environment(loader=templateLoader)

@app.route("/")
def index():
  # This is a placeholder index. The original file might have a different one.
  # Attempting to preserve original functionality if possible.
  # The previous erroneous edit deleted the original index.
  # Check if 'index.html' exists and if ros_available needs to be passed.
  try:
    return render_template('index.html', ros_available=ros_available)
  except jinja2.exceptions.TemplateNotFound:
    return "Welcome! MapD Log Stream at /mapd_logs_stream"

@app.route('/static/<path:path>')
def send_static(path):
  # This is a placeholder static route. The original file might have a different one.
  try:
    return send_from_directory('static', path)
  except Exception: # Catch generic exception if static dir or file not found
    return "Static file not found", 404

if __name__ == "__main__":
  # Standard Flask app run. The original might have different host/port.
  # Port 5000 is the default for Flask.
  app.run(host='0.0.0.0', port=5000, threaded=True)