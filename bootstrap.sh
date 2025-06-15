#!/usr/bin/env bash
set -e

START_TIME=$(date +%s)

# Update and install system packages
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  python3 python3-venv python3-dev python3-pip build-essential \
  git curl ca-certificates ffmpeg \
  libglib2.0-0 libgl1 libglfw3 libgles2-mesa-dev

# Setup caches
SCONS_CACHE=/workspace/scons_cache
COMMA_CACHE=/workspace/comma_cache
COMMA_DOWNLOAD_CACHE=/workspace/comma_download_cache
mkdir -p "$SCONS_CACHE" "$COMMA_CACHE" "$COMMA_DOWNLOAD_CACHE"

# Create python virtual environment
VENV_DIR=/tmp/openpilot-env
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install numpy scipy opencv-python-headless pycapnp==2.0.0 tqdm psutil

# Create activation script
cat <<EOS > /workspace/activate_env.sh
#!/usr/bin/env bash
source /tmp/openpilot-env/bin/activate
cd /workspace
export SCONS_CACHE=$SCONS_CACHE
export COMMA_CACHE=$COMMA_CACHE
export COMMA_DOWNLOAD_CACHE=$COMMA_DOWNLOAD_CACHE
EOS
chmod +x /workspace/activate_env.sh

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Bootstrap completed in ${DURATION}s"
echo "Run: source /workspace/activate_env.sh"

# activate for current session
source /workspace/activate_env.sh

