#!/usr/bin/env python3
# otisserv - Copyright (c) 2019-, Rick Lan, dragonpilot community, and a number of other of contributors.
# Fleet Manager - [actuallylemoncurd](https://github.com/actuallylemoncurd), [AlexandreSato](https://github.com/alexandreSato), [ntegan1](https://github.com/ntegan1), [royjr](https://github.com/royjr), and [sunnyhaibin] (https://github.com/sunnypilot)
# Almost everything else - ChatGPT
# dirty PR pusher - mike8643
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import os
import requests
import secrets
import traceback
import time
import json
from datetime import datetime
import sys
from threading import Thread
from subprocess import check_output, CalledProcessError, STDOUT

import openpilot.selfdrive.frogpilot.fleetmanager.helpers as fleet
from openpilot.common.basedir import BASEDIR

from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, session, url_for, stream_with_context
from pathlib import Path
from requests.exceptions import ConnectionError

from openpilot.common.realtime import set_core_affinity
from openpilot.common.swaglog import cloudlog
from openpilot.system.hardware.hw import Paths

from openpilot.selfdrive.frogpilot.frogpilot_variables import has_prime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session support

# Directory paths
ROUTE_DIR = Paths.log_root()

@app.route("/")
def home_page():
  return render_template("index.html")

@app.errorhandler(500)
def internal_error(exception):
  print('500 error caught')
  tberror = traceback.format_exc()
  return render_template("error.html", error=tberror)

@app.route("/footage/full/<cameratype>/<route>")
def full(cameratype, route):
  chunk_size = 1024 * 512  # 5KiB
  file_name = cameratype + (".ts" if cameratype == "qcamera" else ".hevc")
  vidlist = "|".join(Paths.log_root() + "/" + segment + "/" + file_name for segment in fleet.segments_in_route(route))

  def generate_buffered_stream():
    with fleet.ffmpeg_mp4_concat_wrap_process_builder(vidlist, cameratype, chunk_size) as process:
      for chunk in iter(lambda: process.stdout.read(chunk_size), b""):
        yield bytes(chunk)
  return Response(generate_buffered_stream(), status=200, mimetype='video/mp4')


@app.route("/footage/<cameratype>/<segment>")
def fcamera(cameratype, segment):
  if not fleet.is_valid_segment(segment):
    return render_template("error.html", error="invalid segment")
  file_name = Paths.log_root() + "/" + segment + "/" + cameratype + (".ts" if cameratype == "qcamera" else ".hevc")
  return Response(fleet.ffmpeg_mp4_wrap_process_builder(file_name).stdout.read(), status=200, mimetype='video/mp4')


@app.route("/footage/<route>")
def route(route):
  if len(route) != 20:
    return render_template("error.html", error="route not found")

  if str(request.query_string) == "b''":
    query_segment = str("0")
    query_type = "qcamera"
  else:
    query_segment = (str(request.query_string).split(","))[0][2:]
    query_type = (str(request.query_string).split(","))[1][:-1]

  links = ""
  segments = ""
  for segment in fleet.segments_in_route(route):
    links += "<a href='"+route+"?"+segment.split("--")[2]+","+query_type+"'>"+segment+"</a><br>"
    segments += "'"+segment+"',"
  return render_template("route.html", route=route, query_type=query_type, links=links, segments=segments, query_segment=query_segment)


@app.route("/footage/")
@app.route("/footage")
def footage():
  route_paths = fleet.all_routes()
  gifs = []
  for route_path in route_paths:
    input_path = Paths.log_root() + route_path + "--0/qcamera.ts"
    output_path = Paths.log_root() + route_path + "--0/preview.gif"
    fleet.video_to_img(input_path, output_path)
    gif_path = route_path + "--0/preview.gif"
    gifs.append(gif_path)
  zipped = zip(route_paths, gifs)
  return render_template("footage.html", zipped=zipped)

@app.route("/preserved/")
@app.route("/preserved")
def preserved():
  query_type = "qcamera"
  route_paths = []
  gifs = []
  segments = fleet.preserved_routes()
  for segment in segments:
    input_path = Paths.log_root() + segment + "/qcamera.ts"
    output_path = Paths.log_root() + segment + "/preview.gif"
    fleet.video_to_img(input_path, output_path)
    split_segment = segment.split("--")
    route_paths.append(f"{split_segment[0]}--{split_segment[1]}?{split_segment[2]},{query_type}")
    gif_path = segment + "/preview.gif"
    gifs.append(gif_path)

  zipped = zip(route_paths, gifs, segments)
  return render_template("preserved.html", zipped=zipped)

@app.route("/screenrecords/")
@app.route("/screenrecords")
def screenrecords():
  rows = fleet.list_file(fleet.SCREENRECORD_PATH)
  if not rows:
    return render_template("error.html", error="no screenrecords found at:<br><br>" + fleet.SCREENRECORD_PATH)
  return render_template("screenrecords.html", rows=rows, clip=rows[0])


@app.route("/screenrecords/<clip>")
def screenrecord(clip):
  return render_template("screenrecords.html", rows=fleet.list_files(fleet.SCREENRECORD_PATH), clip=clip)


@app.route("/screenrecords/play/pipe/<file>")
def videoscreenrecord(file):
  file_name = fleet.SCREENRECORD_PATH + file
  return Response(fleet.ffplay_mp4_wrap_process_builder(file_name).stdout.read(), status=200, mimetype='video/mp4')


@app.route("/screenrecords/download/<clip>")
def download_file(clip):
  return send_from_directory(fleet.SCREENRECORD_PATH, clip, as_attachment=True)


@app.route("/about")
def about():
  return render_template("about.html")


@app.route("/error_logs")
def error_logs():
  rows = fleet.list_file(fleet.ERROR_LOGS_PATH)
  if not rows:
    return render_template("error.html", error="no error logs found at:<br><br>" + fleet.ERROR_LOGS_PATH)
  return render_template("error_logs.html", rows=rows)


@app.route("/error_logs/<file_name>")
def open_error_log(file_name):
  f = open(Path(fleet.ERROR_LOGS_PATH) / file_name)
  error = f.read()
  return render_template("error_log.html", file_name=file_name, file_content=error)

@app.route("/addr_input", methods=['GET', 'POST'])
def addr_input():
  preload = fleet.preload_favs()
  search_input = fleet.get_search_input()
  token = fleet.get_public_token()

  lon = 0.0
  lat = 0.0

  if request.method == 'POST':
    postvars = request.form.to_dict()
    valid_addr = False
    addr, lon, lat, valid_addr, token = fleet.parse_addr(postvars, lon, lat, valid_addr, token)

    if not valid_addr:
      addr = request.form.get('addr_val')
      addr, lon, lat, valid_addr, token = fleet.search_addr(postvars, lon, lat, valid_addr, token)

    if valid_addr:
      return redirect(url_for('nav_confirmation', addr=addr, lon=lon, lat=lat))
    return render_template("error.html")

  if has_prime():
    return render_template("prime.html")

  if search_input == 0:
    if fleet.get_public_token() is None:
      return redirect(url_for('public_token_input'))

    if fleet.get_secret_token() is None:
      return redirect(url_for('app_token_input'))

  if search_input == 1:
    amap_key, amap_key_2 = fleet.get_amap_key()
    if not amap_key or not amap_key_2:
      return redirect(url_for('amap_key_input'))
    return redirect(url_for('amap_addr_input'))

  if search_input == 2:
    gmap_key = fleet.get_gmap_key()
    lon, lat = fleet.get_last_lon_lat()

    if not gmap_key:
      return redirect(url_for('gmap_key_input'))
    return render_template("addr.html", gmap_key=gmap_key, lon=lon, lat=lat, home=preload[0], work=preload[1], fav1=preload[2], fav2=preload[3], fav3=preload[4])

  if fleet.get_nav_active():
    return render_template("nonprime.html", gmap_key=None, lon=None, lat=None, home=preload[0], work=preload[1], fav1=preload[2], fav2=preload[3], fav3=preload[4])

  return render_template("addr.html", gmap_key=None, lon=None, lat=None, home=preload[0], work=preload[1], fav1=preload[2], fav2=preload[3], fav3=preload[4])

@app.route("/nav_confirmation", methods=['GET', 'POST'])
def nav_confirmation():
  token = fleet.get_public_token()
  lon = request.args.get('lon')
  lat = request.args.get('lat')
  addr = request.args.get('addr')
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.nav_confirmed(postvars)
    return redirect(url_for('addr_input'))
  else:
    return render_template("nav_confirmation.html", addr=addr, lon=lon, lat=lat, token=token)

@app.route("/public_token_input", methods=['GET', 'POST'])
def public_token_input():
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.public_token_input(postvars)
    return redirect(url_for('addr_input'))
  else:
    return render_template("public_token_input.html")

@app.route("/app_token_input", methods=['GET', 'POST'])
def app_token_input():
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.app_token_input(postvars)
    return redirect(url_for('addr_input'))
  else:
    return render_template("app_token_input.html")

@app.route("/gmap_key_input", methods=['GET', 'POST'])
def gmap_key_input():
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.gmap_key_input(postvars)
    return redirect(url_for('addr_input'))
  else:
    return render_template("gmap_key_input.html")

@app.route("/amap_key_input", methods=['GET', 'POST'])
def amap_key_input():
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.amap_key_input(postvars)
    return redirect(url_for('amap_addr_input'))
  else:
    return render_template("amap_key_input.html")

@app.route("/amap_addr_input", methods=['GET', 'POST'])
def amap_addr_input():
  if request.method == 'POST':
    postvars = request.form.to_dict()
    fleet.nav_confirmed(postvars)
    return redirect(url_for('amap_addr_input'))
  else:
    lon, lat = fleet.get_last_lon_lat()
    amap_key, amap_key_2 = fleet.get_amap_key()
    return render_template("amap_addr_input.html", lon=lon, lat=lat, amap_key=amap_key, amap_key_2=amap_key_2)

@app.route("/CurrentStep.json", methods=['GET'])
def find_CurrentStep():
  directory = "/data/openpilot/selfdrive/manager/"
  filename = "CurrentStep.json"
  return send_from_directory(directory, filename, as_attachment=True)

@app.route("/navdirections.json", methods=['GET'])
def find_nav_directions():
  directory = "/data/openpilot/selfdrive/manager/"
  filename = "navdirections.json"
  return send_from_directory(directory, filename, as_attachment=True)

@app.route("/locations", methods=['GET'])
def get_locations():
  data = fleet.get_locations()
  return Response(data, content_type="application/json")

@app.route("/set_destination", methods=['POST'])
def set_destination():
  valid_addr = False
  postvars = request.get_json()
  data, valid_addr = fleet.set_destination(postvars, valid_addr)
  if valid_addr:
    return Response('{"success": true}', content_type='application/json')
  else:
    return Response('{"success": false}', content_type='application/json')

@app.route("/navigation/<file_name>", methods=['GET'])
def find_navicon(file_name):
  directory = "/data/openpilot/selfdrive/assets/navigation/"
  return send_from_directory(directory, file_name, as_attachment=True)

@app.route("/previewgif/<path:file_path>", methods=['GET'])
def find_previewgif(file_path):
  directory = "/data/media/0/realdata/"
  return send_from_directory(directory, file_path, as_attachment=True)

@app.route("/tools", methods=['GET'])
def tools_route():
  return render_template("tools.html")

@app.route("/plotjuggler", methods=['GET'])
def plotjuggler_route():
  # Get available layouts from the PlotJuggler layouts directory
  layouts_dir = os.path.join(BASEDIR, "tools/plotjuggler/layouts")
  layouts = []
  if os.path.exists(layouts_dir):
    for file in os.listdir(layouts_dir):
      if file.endswith(".xml"):
        layouts.append(file)

  # Get route parameter if provided (from dashcam footage links)
  route = request.args.get('route', '')

  # Get available routes
  available_routes = fleet.all_routes()

  # Get route dates (for display purposes)
  route_dates = []
  for route in available_routes:
    # Format: YYYY-MM-DD--HH-MM-SS
    try:
      date_part = route.split('--')[0]
      time_part = route.split('--')[1]
      formatted_date = f"{date_part} {time_part.replace('-', ':')}"
      route_dates.append(formatted_date)
    except:
      route_dates.append("")

  # Get recent routes from session
  recent_routes = session.get('recent_routes', [])

  return render_template("plotjuggler.html", layouts=layouts, route=route,
                        available_routes=available_routes, route_dates=route_dates,
                        recent_routes=recent_routes)

@app.route("/save_recent_route", methods=['POST'])
def save_recent_route():
  try:
    data = request.json
    route = data.get('route', '')

    if not route:
      return jsonify({"success": False, "error": "No route provided"}), 400

    # Get existing recent routes from session
    recent_routes = session.get('recent_routes', [])

    # Remove the route if it already exists to avoid duplicates
    if route in recent_routes:
      recent_routes.remove(route)

    # Add the new route at the beginning
    recent_routes.insert(0, route)

    # Keep only the 10 most recent routes
    recent_routes = recent_routes[:10]

    # Update session
    session['recent_routes'] = recent_routes

    return jsonify({"success": True}), 200
  except Exception as e:
    return jsonify({"success": False, "error": str(e)}), 400

@app.route("/search_routes", methods=['GET'])
def search_routes():
  try:
    search_term = request.args.get('term', '').lower()

    if not search_term:
      return jsonify({"routes": []}), 200

    # Get all routes
    all_routes = fleet.all_routes()

    # Filter routes based on search term
    matching_routes = [route for route in all_routes if search_term in route.lower()]

    return jsonify({"routes": matching_routes}), 200
  except Exception as e:
    return jsonify({"success": False, "error": str(e)}), 400

@app.route("/run_plotjuggler", methods=['POST'])
def run_plotjuggler():
  try:
    # Import juggle module
    sys.path.append(os.path.join(BASEDIR, "tools/plotjuggler"))
    import juggle

    # Get parameters from request
    data = request.json
    stream = data.get('stream', False)
    demo = data.get('demo', False)
    can = data.get('can', False)
    layout = data.get('layout') if data.get('layout') else None
    dbc = data.get('dbc') if data.get('dbc') else None
    route = data.get('route') if data.get('route') else None

    # Ensure PlotJuggler is installed
    if not os.path.exists(juggle.PLOTJUGGLER_BIN):
      juggle.install()
    elif juggle.get_plotjuggler_version() < juggle.MINIMUM_PLOTJUGGLER_VERSION:
      juggle.install()

    # Run in background thread to not block the response
    def run_in_background():
      try:
        if stream:
          juggle.start_juggler(layout=layout)
        else:
          route_name = juggle.DEMO_ROUTE if demo else route.strip()
          juggle.juggle_route(route_name, can, layout, dbc)
      except Exception as e:
        print(f"Error running PlotJuggler: {str(e)}")

    thread = Thread(target=run_in_background)
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": "PlotJuggler started successfully"})
  except Exception as e:
    return jsonify({"success": False, "error": str(e)})

@app.route("/install_plotjuggler", methods=['POST'])
def install_plotjuggler():
  try:
    # Import juggle module
    sys.path.append(os.path.join(BASEDIR, "tools/plotjuggler"))
    import juggle

    # Run installation in background thread
    def install_in_background():
      try:
        juggle.install()
      except Exception as e:
        print(f"Error installing PlotJuggler: {str(e)}")

    thread = Thread(target=install_in_background)
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": "PlotJuggler installation started"})
  except Exception as e:
    return jsonify({"success": False, "error": str(e)})

@app.route("/cloudlog", methods=['GET'])
def cloudlog_route():
  """Main cloudlog page with real-time streaming."""
  # Initialize the subscriber if not already done
  fleet.init_cloudlog_subscriber()

  return render_template("cloudlog_realtime.html")

@app.route("/cloudlog/<file_name>")
def view_cloudlog(file_name):
  try:
    log_path = os.path.join(fleet.CLOUDLOG_STORAGE_PATH, file_name)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
      content = f.read()
    return render_template("cloudlog_view.html", file_name=file_name, file_content=content)
  except Exception as e:
    return render_template("error.html", error=f"Error reading cloudlog file: {str(e)}")

@app.route("/capture_cloudlog", methods=['POST'])
def capture_cloudlog_route():
  try:
    log_filename = fleet.capture_cloudlog()
    return jsonify({"message": "Captured cloudlog successfully!", "log_file": log_filename}), 200
  except Exception as error:
    return jsonify({"error": "Failed to capture cloudlog...", "details": str(error)}), 400

@app.route("/download_cloudlog/<filename>", methods=['GET'])
def download_cloudlog(filename):
  try:
    return send_from_directory(fleet.CLOUDLOG_STORAGE_PATH, filename, as_attachment=True)
  except Exception as error:
    return jsonify({"error": "Failed to download the file...", "details": str(error)}), 400

@app.route("/get_toggle_values", methods=['GET'])
def get_toggle_values_route():
  toggle_values = fleet.get_all_toggle_values()
  return jsonify(toggle_values)

@app.route("/reset_toggle_values", methods=['POST'])
def reset_toggle_values_route():
  try:
    fleet.reset_toggle_values()
    return jsonify({"message": "Toggles reset successfully! Rebooting..."}), 200
  except Exception as error:
    return jsonify({"error": "Failed to reset toggles...", "details": str(error)}), 400

@app.route("/store_toggle_values", methods=['POST'])
def store_toggle_values_route():
  try:
    updated_values = request.get_json()
    fleet.store_toggle_values(updated_values)
    return jsonify({"message": "Values updated successfully"}), 200
  except Exception as error:
    return jsonify({"error": "Failed to update values", "details": str(error)}), 400

@app.route("/capture_tmux_log", methods=['POST'])
def capture_tmux_log_route():
  try:
    log_filename = fleet.capture_tmux_log()
    return jsonify({"message": "Captured console log successfully!", "log_file": log_filename}), 200
  except Exception as error:
    return jsonify({"error": "Failed to capture the console log...", "details": str(error)}), 400

@app.route("/download_tmux_log/<filename>", methods=['GET'])
def download_tmux_log(filename):
  try:
    return send_from_directory(fleet.TMUX_LOGS_PATH, filename, as_attachment=True)
  except Exception as error:
    return jsonify({"error": "Failed to download the file...", "details": str(error)}), 400

@app.route("/lock_doors", methods=['POST'])
def lock_doors_route():
  try:
    fleet.lock_doors()
    return jsonify({"message": "Doors locked successfully!"}), 200
  except Exception as error:
    return jsonify({"error": "Failed to lock doors...", "details": str(error)}), 400

@app.route("/unlock_doors", methods=['POST'])
def unlock_doors_route():
  try:
    fleet.unlock_doors()
    return jsonify({"message": "Doors unlocked successfully!"}), 200
  except Exception as error:
    return jsonify({"error": "Failed to unlock doors...", "details": str(error)}), 400

@app.route("/reboot_device", methods=['POST'])
def reboot_device_route():
  try:
    fleet.reboot_device()
    return jsonify({"message": "Successfully rebooted!"}), 200
  except Exception as error:
    return jsonify({"error": "Failed to reboot...", "details": str(error)}), 400

@app.route("/cloudlog_stream")
def cloudlog_stream():
  """Stream cloudlog messages in real-time using Server-Sent Events."""
  # Initialize the subscriber if not already done
  fleet.init_cloudlog_subscriber()

  # Add a log message to indicate the stream was started
  cloudlog.info("Cloudlog stream started")

  # Send initial batch of cached logs if any
  def generate():
    # Send any cached logs first
    cached_logs = fleet.get_cached_cloudlogs()
    if cached_logs:
      yield "event: initial\ndata: " + json.dumps(cached_logs) + "\n\n"
    else:
      # Send an initial message if no cached logs
      initial_msg = [f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Cloudlog stream started"]
      yield "event: initial\ndata: " + json.dumps(initial_msg) + "\n\n"

    # Send a heartbeat to ensure the connection is established
    yield "event: open\ndata: {}\n\n"

    # Stream new logs as they come in
    while True:
      new_logs = fleet.get_new_cloudlog_messages()
      if new_logs:
        yield "event: log\ndata: " + json.dumps(new_logs) + "\n\n"
      # Small sleep to prevent CPU hogging
      time.sleep(0.1)

  return Response(stream_with_context(generate()),
                 mimetype="text/event-stream",
                 headers={"Cache-Control": "no-cache",
                          "X-Accel-Buffering": "no",
                          "Connection": "keep-alive"})

@app.route("/web_plotjuggler", methods=['GET'])
def web_plotjuggler_route():
  """
  Route for the web-based in-browser PlotJuggler implementation.
  Uses the same route selection interface as the native PlotJuggler.
  """
  # Get available layouts from the PlotJuggler layouts directory
  layouts_dir = os.path.join(BASEDIR, "tools/plotjuggler/layouts")
  layouts = []
  if os.path.exists(layouts_dir):
    for file in os.listdir(layouts_dir):
      if file.endswith(".xml"):
        layouts.append(file)

  # Get route parameter if provided (from dashcam footage links)
  route = request.args.get('route', '')

  # Get available routes
  available_routes = fleet.all_routes()

  # Get route dates (for display purposes)
  route_dates = []
  for route in available_routes:
    # Format: YYYY-MM-DD--HH-MM-SS
    try:
      date_part = route.split('--')[0]
      time_part = route.split('--')[1]
      formatted_date = f"{date_part} {time_part.replace('-', ':')}"
      route_dates.append(formatted_date)
    except:
      route_dates.append("")

  # Get recent routes from session
  recent_routes = session.get('recent_routes', [])

  return render_template("web_plotjuggler.html", layouts=layouts, route=route,
                        available_routes=available_routes, route_dates=route_dates,
                        recent_routes=recent_routes, page="web_plotjuggler")

@app.route("/web_plotjuggler_data", methods=['GET'])
def web_plotjuggler_data():
  """
  API endpoint to fetch log data for a specified route/segment and return as JSON.
  Updates:
    - If log files (.rlog or .qlog) are detected directly in the route directory,
      ignore the segment parameter and treat it as segment 0.
  """
  try:
    # Import necessary modules
    from functools import partial
    sys.path.append(os.path.join(BASEDIR, "tools/lib"))
    from logreader import LogReader, ReadMode

    # Get route and segment parameters
    route = request.args.get('route', '')
    can = request.args.get('can', 'false') == 'true'
    segment = request.args.get('segment', None)
    signals = request.args.get('signals', None)

    cloudlog.info(f"Web PlotJuggler data request - route: {route}, segment: {segment}, can: {can}")

    if not route:
      return jsonify({"error": "No route specified"}), 400

    # Parse signals if provided
    signal_list = None
    if signals:
      signal_list = signals.split(',')
      cloudlog.info(f"Filtering for signals: {signal_list}")

    # We'll store debugging info here for clarity
    route_path = None
    debug_info = {"route": route, "segment": segment, "paths_checked": []}

    # --------------------------------------------------------------------------
    # -- ADDED: First, check if there's a directory named exactly <ROUTE_DIR>/<route>
    #           If it exists and has .rlog or .qlog files, we treat that as "segment 0".
    # --------------------------------------------------------------------------
    candidate_path = os.path.join(ROUTE_DIR, route)
    debug_info["paths_checked"].append({
      "path": candidate_path,
      "exists": os.path.isdir(candidate_path)
    })

    if os.path.isdir(candidate_path):
      # Check if route directory has .rlog / .qlog directly
      log_files = [f for f in os.listdir(candidate_path) if f.endswith('.rlog') or f.endswith('.qlog')]
      if log_files:
        # Found logs in the root of the route, treat this as segment 0
        route_path = candidate_path
        segment = '0'
        cloudlog.info(f"Log files found directly in route dir: {route_path}. Treating as segment 0.")

    # --------------------------------------------------------------------------
    # If not found, we revert to old logic to search by route+segment or route alone
    # --------------------------------------------------------------------------
    if route_path is None:
      # Try <route>/<segment> or route alone
      candidate_path = os.path.join(ROUTE_DIR, route)
      if os.path.isdir(candidate_path):
        debug_info["paths_checked"].append({"path": candidate_path, "exists": True})
        route_path = candidate_path
        cloudlog.info(f"Found route path without segment: {route_path}")
      else:
        debug_info["paths_checked"].append({"path": candidate_path, "exists": False})
        # Attempt route substring match
        possible_routes = [
          r for r in os.listdir(ROUTE_DIR)
          if r.startswith(route) or route in r
        ]
        debug_info["possible_routes"] = possible_routes

        if possible_routes:
          base_route_path = os.path.join(ROUTE_DIR, possible_routes[0])
          debug_info["paths_checked"].append({
            "path": base_route_path,
            "exists": os.path.isdir(base_route_path)
          })

          if os.path.isdir(base_route_path):
            if segment:
              candidate_path = os.path.join(base_route_path, str(segment))
              debug_info["paths_checked"].append({
                "path": candidate_path,
                "exists": os.path.isdir(candidate_path)
              })
              if os.path.isdir(candidate_path):
                route_path = candidate_path
                cloudlog.info(f"Found matching route+segment: {route_path}")
              else:
                # fallback to base route
                route_path = base_route_path
            else:
              # no segment
              route_path = base_route_path
            cloudlog.info(f"Using route path: {route_path}")

    # --------------------------------------------------------------------------
    # Final check: Did we resolve a valid route path directory?
    # --------------------------------------------------------------------------
    if route_path is None or not os.path.isdir(route_path):
      cloudlog.error(f"Could not find a valid route path for '{route}'. Debug: {debug_info}")
      return jsonify({
        "success": False,
        "error": f"Could not find a valid route path for {route}",
        "debug_info": debug_info
      }), 404

    cloudlog.info(f"Reading logs from path: {route_path}")

    # --------------------------------------------------------------------------
    # Check if the directory we ended on has .rlog or .qlog. If no logs are in
    # this directory, we then look for numeric subdirectories.
    # --------------------------------------------------------------------------
    log_files = [f for f in os.listdir(route_path) if f.endswith('.rlog') or f.endswith('.qlog')]
    if log_files:
      # We already set segment=0 if these logs were discovered at the route's top-level
      cloudlog.info(f"Confirmed log files in {route_path}. Segment forced to 0 => {segment}")
    else:
      # See if there are numeric subdirectories
      segment_dirs = [
        d for d in os.listdir(route_path)
        if os.path.isdir(os.path.join(route_path, d)) and d.isdigit()
      ]
      if segment_dirs:
        # Use the first numeric subdirectory, or the requested one if it exists
        if segment and segment in segment_dirs:
          # If a user-specified segment directory is valid
          chosen_segment = segment
        else:
          chosen_segment = sorted(segment_dirs, key=int)[0]

        route_path = os.path.join(route_path, chosen_segment)
        log_files = [f for f in os.listdir(route_path) if f.endswith('.rlog') or f.endswith('.qlog')]
        # If we do find logs here, segment = chosen_segment
        if log_files:
          segment = chosen_segment
          cloudlog.info(f"Found log files in subdirectory segment {segment}: {route_path}")
        else:
          cloudlog.warning(f"No .rlog or .qlog found in segment {chosen_segment}. Continuing anyway.")

    # Final check for any logs
    if not log_files:
      cloudlog.error(f"No log files found in {route_path}")
      return jsonify({
        "success": False,
        "error": f"No log files found in {route_path}",
        "debug_info": debug_info
      }), 404

    # --------------------------------------------------------------------------
    # Create LogReader and parse
    # --------------------------------------------------------------------------
    try:
      cloudlog.info(f"Creating LogReader for {route_path}")
      lr = LogReader(route_path, default_mode=ReadMode.AUTO_INTERACTIVE)
    except FileNotFoundError as e:
      cloudlog.exception(f"Log file not found for {route_path}: {e}")
      return jsonify({
        "success": False,
        "error": f"Log file not found for {route_path}",
        "debug_info": debug_info
      }), 404
    except Exception as e:
      cloudlog.exception(f"Error reading log file: {e}")
      return jsonify({
        "success": False,
        "error": f"Error reading log file: {str(e)}",
        "debug_info": debug_info
      }), 500

    # Process the logs and prepare data for visualization
    data = {}
    sample_count = 0
    max_samples = 500  # example: throttle to 500 samples

    cloudlog.info(f"Processing log messages from route_path={route_path}")
    for msg in lr:
      try:
        # Get message name and timestamp
        msg_type = msg.which()
        timestamp = msg.logMonoTime

        # Skip if we have a 'signals' filter and this message isn't included
        if signal_list and msg_type not in signal_list:
          continue

        # Skip CAN data if not requested
        if not can and msg_type in ['can', 'sendcan']:
          continue

        if msg_type not in data:
          data[msg_type] = {"timestamps": [], "values": {}}

        data[msg_type]["timestamps"].append(timestamp)
        msg_data = getattr(msg, msg_type)

        # Minimal introspection over fields (example only)
        for field_name in list(dir(msg_data))[:10]:
          # skip private methods, special attributes, or callables
          if field_name.startswith('_'):
            continue
          if callable(getattr(msg_data, field_name)):
            continue

          value = getattr(msg_data, field_name)
          # store only simple numeric or boolean fields
          if isinstance(value, (int, float, bool)) and field_name not in ["read", "write"]:
            if field_name not in data[msg_type]["values"]:
              data[msg_type]["values"][field_name] = []
            data[msg_type]["values"][field_name].append(value)

        sample_count += 1
        if sample_count >= max_samples:
          break

      except Exception as e:
        # Skip or handle a single message read error
        continue

    if not data:
      cloudlog.warning(f"No data extracted from logs at {route_path}.")
      return jsonify({
        "success": False,
        "error": "No data could be extracted from the logs",
        "route_path": route_path,
        "debug_info": debug_info
      }), 404

    cloudlog.info(f"Successfully processed log data. Found {len(data)} message types.")

    return jsonify({
      "data": data,
      "success": True,
      "route_path": route_path,
      "message_count": len(data),
      "debug_info": {
        "route": route,
        "segment": segment,
        "route_path": route_path,
        "message_types": list(data.keys())
      }
    })

  except Exception as e:
    cloudlog.exception(f"Error in web_plotjuggler_data: {e}")
    return jsonify({
      "success": False,
      "error": str(e),
      "traceback": traceback.format_exc()
    }), 500

@app.route("/web_plotjuggler_stream", methods=['GET'])
def web_plotjuggler_stream():
  """
  Stream SSE events with real-time log data for live plotting.
  This is a simplified implementation to avoid resource issues.
  """
  # Import necessary modules
  import time
  import json
  from datetime import datetime

  # Function to generate SSE events
  def generate():
    # Send a heartbeat to ensure the connection is established
    yield "event: open\ndata: {}\n\n"

    # Just send timestamps for now - actual data streaming would be implemented later
    # after careful performance testing
    for i in range(10):  # Limit to 10 updates then close to avoid resource issues
      # For this example, just send a timestamp as a placeholder
      current_time = datetime.now().timestamp() * 1000
      data = {"timestamp": current_time}
      yield f"event: data\ndata: {json.dumps(data)}\n\n"

      # Sleep to prevent CPU hogging
      time.sleep(2)

  return Response(stream_with_context(generate()),
                 mimetype="text/event-stream",
                 headers={"Cache-Control": "no-cache",
                          "X-Accel-Buffering": "no",
                          "Connection": "keep-alive"})

@app.route("/segments", methods=['GET'])
def get_segments():
  """
  API endpoint to fetch segments for a specific route.
  """
  route = request.args.get('route', '')
  if not route:
    return jsonify({"error": "No route specified"}), 400

  # Get segments for the route
  segments = []
  try:
    # Log the request for debugging
    cloudlog.info(f"Segment request received for route: {route}")

    # Get route directory
    # We need to handle two potential route formats:
    # 1. YYYY-MM-DD--HH-MM-SS--[identifier] (route folder name)
    # 2. Full path from Paths.log_root()

    # First, try using the route directly
    route_dir = os.path.join(ROUTE_DIR, route)
    cloudlog.info(f"Checking route directory: {route_dir}")

    # Debug: Check if ROUTE_DIR exists
    cloudlog.info(f"ROUTE_DIR exists: {os.path.exists(ROUTE_DIR)}")
    cloudlog.info(f"ROUTE_DIR contents: {os.listdir(ROUTE_DIR) if os.path.exists(ROUTE_DIR) else 'N/A'}")

    if not os.path.isdir(route_dir):
      # If that doesn't work, try alternative formats
      cloudlog.info(f"Route directory not found: {route_dir}")

      # If it's a full route path already, use it directly
      if os.path.isdir(route):
        route_dir = route
        cloudlog.info(f"Using full path as route directory: {route_dir}")
      else:
        # Try to find matching route by name pattern
        possible_routes = [r for r in os.listdir(ROUTE_DIR)
                          if r.startswith(route) or route in r]
        cloudlog.info(f"Possible matching routes: {possible_routes}")

        if possible_routes:
          route_dir = os.path.join(ROUTE_DIR, possible_routes[0])
          cloudlog.info(f"Using matched route directory: {route_dir}")
        else:
          cloudlog.info(f"No matching route found for: {route}")
          return jsonify({"segments": [], "success": True, "message": "No matching route found", "debug_info": {"route": route, "route_dir": ROUTE_DIR}})

    cloudlog.info(f"Looking for segments in {route_dir}")

    # Check if directory exists
    if not os.path.isdir(route_dir):
      cloudlog.info(f"Route directory not found: {route_dir}")
      return jsonify({"segments": [], "success": True, "message": "Route directory not found", "debug_info": {"route": route, "route_dir": route_dir}})

    # Debug: List contents of the route directory
    route_contents = os.listdir(route_dir)
    cloudlog.info(f"Route directory contents: {route_contents}")

    # Get all subdirectories that are numeric (segments are typically numbered)
    segment_dirs = [d for d in route_contents
                   if os.path.isdir(os.path.join(route_dir, d)) and d.isdigit()]
    cloudlog.info(f"Found segment directories: {segment_dirs}")

    # For each segment directory, check if it contains log files
    for segment in sorted(segment_dirs, key=int):
      segment_path = os.path.join(route_dir, segment)
      cloudlog.info(f"Checking segment directory: {segment_path}")

      # List contents of segment directory
      segment_contents = os.listdir(segment_path)
      cloudlog.info(f"Segment directory contents: {segment_contents}")

      # Check for any of the log file types
      log_files = ['rlog.rlog', 'qlog.qlog']
      for log_file in log_files:
        log_path = os.path.join(segment_path, log_file)
        cloudlog.info(f"Checking for log file: {log_path}, exists: {os.path.exists(log_path)}")

        if os.path.exists(log_path):
          segments.append(int(segment))
          cloudlog.info(f"Added segment {segment} to list")
          break

    # If no segments found with log files, try to add all segment directories anyway
    if not segments and segment_dirs:
      cloudlog.info("No segments with log files found, adding all segment directories")
      segments = [int(d) for d in segment_dirs]

    # Debug info
    cloudlog.info(f"Final segments list: {segments}")

    return jsonify({
      "segments": segments,
      "success": True,
      "route_dir": route_dir,
      "route": route,
      "debug_info": {
        "route_dir_exists": os.path.exists(route_dir),
        "segment_dirs": segment_dirs,
        "log_files_checked": log_files
      }
    })
  except Exception as e:
    cloudlog.exception(f"Error getting segments: {e}")
    return jsonify({"error": str(e), "route": route, "traceback": traceback.format_exc()}), 500

@app.route("/execute_shell", methods=['POST'])
def execute_shell():
  try:
    data = request.get_json()
    command = data.get('command', '')

    output = check_output(command, shell=True, stderr=STDOUT, universal_newlines=True, timeout=5)
    return jsonify({"output": output})
  except CalledProcessError as e:
    return jsonify({"output": e.output}), 400
  except Exception as e:
    return jsonify({"output": str(e)}), 500

def main():
  try:
    # Try to set core affinity to avoid overloading application cpu
    try:
      set_core_affinity(1)
    except Exception:
      cloudlog.exception("fleet_manager: failed to set core affinity")

    # Use a stable secret key instead of regenerating each time
    app.secret_key = secrets.token_hex(32)
    app.run(host="0.0.0.0", port=8082)
  except KeyboardInterrupt:
    sys.exit(0)


if __name__ == '__main__':
  main()
