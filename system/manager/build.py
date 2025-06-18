#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

# NOTE: Do NOT import anything here that needs be built (e.g. params)
from common.basedir import BASEDIR
from common.spinner import Spinner
from common.text_window import TextWindow
from system.hardware import AGNOS
from common.swaglog import cloudlog, add_file_handler
from system.version import get_build_metadata

MAX_CACHE_SIZE = 4e9 if "CI" in os.environ else 2e9
CACHE_DIR = Path("/data/scons_cache" if AGNOS else "/tmp/scons_cache")

TOTAL_SCONS_NODES = 2820
MAX_BUILD_PROGRESS = 100

def build(spinner: Spinner, dirty: bool = False, minimal: bool = False) -> None:
  # Check for debug mode
  debug_mode = os.environ.get('OPENPILOT_DEBUG_BUILD', '0') == '1'
  if debug_mode:
    print("\n=== DEBUG BUILD MODE ACTIVE ===\n")
  # Ensure Python environment is set up correctly
  env_script = Path(BASEDIR) / "ensure_python_env.sh"
  if env_script.exists() and AGNOS:
    spinner.update("Setting up Python environment...")
    try:
      result = subprocess.run(["/bin/bash", str(env_script)], capture_output=True, text=True)
      cloudlog.info(f"Python env setup: {result.stdout}")
      if result.stderr:
        cloudlog.warning(f"Python env warnings: {result.stderr}")
    except subprocess.CalledProcessError as e:
      cloudlog.error(f"Python env setup failed: {e.stderr}")
      
  # Check and install dependencies before building
  dep_script = Path(BASEDIR) / "install_dependencies.sh"
  if dep_script.exists() and AGNOS:
    spinner.update("Checking dependencies...")
    try:
      subprocess.run([str(dep_script)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
      cloudlog.warning(f"Dependency check had warnings: {e.stderr}")
  
  env = os.environ.copy()
  env['SCONS_PROGRESS'] = "1"
  nproc = os.cpu_count()
  if nproc is None:
    nproc = 2

  extra_args = ["--minimal"] if minimal else []

  # building with all cores can result in using too
  # much memory, so retry with less parallelism
  compile_output: list[bytes] = []
  
  # On TICI, be more conservative with parallelism
  if AGNOS:
    parallel_jobs = [2, 1]  # Max 2 jobs on device to avoid memory issues
  else:
    parallel_jobs = [nproc, nproc/2, 1]
    
  for n in parallel_jobs:
    compile_output.clear()
    # Add verbose flag to debug build issues
    scons_cmd = ["scons", f"-j{int(n)}", "--cache-populate"] + extra_args
    
    # On device, add memory-saving flags
    if AGNOS:
      # Disable LTO and other memory-intensive optimizations during build
      env['CCFLAGS'] = env.get('CCFLAGS', '') + ' -fno-lto'
      env['CXXFLAGS'] = env.get('CXXFLAGS', '') + ' -fno-lto'
      
    cloudlog.info(f"Running scons with: {' '.join(scons_cmd)} (parallel={int(n)})")
    scons: subprocess.Popen = subprocess.Popen(scons_cmd, cwd=BASEDIR, env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    assert scons.stderr is not None

    # Read progress from stderr and update spinner
    import time
    last_progress_time = time.time()
    last_progress = 0
    stall_timeout = 300  # 5 minutes
    
    # In debug mode, also capture stdout
    if debug_mode:
      import select
      streams = [scons.stderr, scons.stdout]
    
    while scons.poll() is None:
      try:
        if debug_mode and scons.stdout:
          # Read from both stdout and stderr
          readable, _, _ = select.select(streams, [], [], 0.1)
          for stream in readable:
            line = stream.readline()
            if line:
              print(f"[BUILD] {line.decode('utf8', 'replace').rstrip()}", flush=True)
              last_progress_time = time.time()
        
        line = scons.stderr.readline()
        if line is None:
          continue
        line = line.rstrip()

        prefix = b'progress: '
        if line.startswith(prefix):
          i = int(line[len(prefix):])
          current_progress = MAX_BUILD_PROGRESS * min(1., i / TOTAL_SCONS_NODES)
          if debug_mode:
            print(f"[PROGRESS] {current_progress:.1f}% ({i}/{TOTAL_SCONS_NODES})", flush=True)
          else:
            spinner.update_progress(current_progress, 100.)
          
          # Track progress to detect stalls
          if current_progress > last_progress:
            last_progress = current_progress
            last_progress_time = time.time()
            
        elif len(line):
          compile_output.append(line)
          if debug_mode:
            print(f"[STDERR] {line.decode('utf8', 'replace')}", flush=True)
          # Any output counts as progress
          last_progress_time = time.time()
          
        # Check for stall
        if time.time() - last_progress_time > stall_timeout:
          cloudlog.error(f"Build stalled at {last_progress}% for {stall_timeout}s, killing...")
          scons.terminate()
          break
          
      except Exception as e:
        if debug_mode:
          print(f"[ERROR] Exception in build loop: {e}", flush=True)

    if scons.returncode == 0:
      break

  if scons.returncode != 0:
    # Read remaining output
    if scons.stderr is not None:
      compile_output += scons.stderr.read().split(b'\n')

    # Build failed log errors
    error_s = b"\n".join(compile_output).decode('utf8', 'replace')
    add_file_handler(cloudlog)
    cloudlog.error("scons build failed\n" + error_s)

    # Show TextWindow
    spinner.close()
    if not os.getenv("CI"):
      with TextWindow("openpilot failed to build\n \n" + error_s) as t:
        t.wait_for_exit()
    exit(1)

  # enforce max cache size
  cache_files = [f for f in CACHE_DIR.rglob('*') if f.is_file()]
  cache_files.sort(key=lambda f: f.stat().st_mtime)
  cache_size = sum(f.stat().st_size for f in cache_files)
  for f in cache_files:
    if cache_size < MAX_CACHE_SIZE:
      break
    cache_size -= f.stat().st_size
    f.unlink()


if __name__ == "__main__":
  spinner = Spinner()
  spinner.update_progress(0, 100)
  build_metadata = get_build_metadata()
  build(spinner, build_metadata.openpilot.is_dirty, minimal = AGNOS)
