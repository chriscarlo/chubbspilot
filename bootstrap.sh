#!/bin/bash
  set -e

  echo "🚀 OpenPilot Bootstrap - Starting $(date)"
  START_TIME=$(date +%s)

  # System dependencies (parallel install for speed)
  echo "📦 Installing system dependencies..."
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends \
      build-essential \
      git \
      python3-dev \
      python3-pip \
      python3-venv \
      pkg-config \
      libeigen3-dev \
      libffi-dev \
      libzmq3-dev \
      libcapnp-dev \
      capnproto \
      clang \
      libbz2-dev \
      liblzma-dev \
      libssl-dev \
      libusb-1.0-0-dev \
      portaudio19-dev \
      libsndfile1-dev \
      libgl1-mesa-dev \
      libgles2-mesa-dev \
      cython3 \
      gcc-arm-none-eabi \
      qtbase5-dev \
      qtchooser \
      qt5-qmake \
      qtbase5-dev-tools \
      python3-pytest \
      python3-numpy \
      scons \
      && sudo apt-get clean

  # Create cache directories
  mkdir -p $SCONS_CACHE $COMMA_CACHE $COMMA_DOWNLOAD_CACHE

  # Python virtual environment
  echo "🐍 Setting up Python environment..."
  python3 -m venv /tmp/openpilot-env
  source /tmp/openpilot-env/bin/activate

  # Upgrade pip and install wheel for faster builds
  pip install --upgrade pip wheel setuptools

  # Core Python dependencies (Python 3.12 compatible versions)
  echo "📚 Installing Python dependencies..."
  pip install --no-cache-dir \
      numpy \
      scipy \
      opencv-python-headless \
      pyzmq \
      psutil \
      requests \
      tqdm \
      scons \
      cython \
      pycryptodome

  # Install pycapnp separately with specific version that supports Python 3.12
  echo "📦 Installing pycapnp..."
  pip install --no-cache-dir pycapnp==2.0.0 || \
  pip install --no-cache-dir --no-binary pycapnp pycapnp || \
  echo "Warning: pycapnp installation failed, continuing without it"

  # Git configuration for the agent
  git config --global user.name "$GIT_AUTHOR_NAME"
  git config --global user.email "$GIT_AUTHOR_EMAIL"
  git config --global init.defaultBranch main
  git config --global pull.rebase false

  cd /workspace

  # Set up openpilot specific environment
  echo "⚙️  Configuring OpenPilot environment..."

  # Create essential directories
  mkdir -p /data/media/0/osm
  mkdir -p /data/params
  mkdir -p /tmp/comma_download_cache

  # Install any additional Python deps from pyproject.toml if it exists
  if [ -f "pyproject.toml" ]; then
      pip install -e . --no-deps || echo "Warning: Failed to install project deps"
  fi

  # Pre-compile some Python modules for faster runtime
  echo "🔧 Pre-compiling Python modules..."
  python -c "import compileall; compileall.compile_dir('/workspace/selfdrive', force=True, quiet=1)" 2>/dev/null || true

  # Create activation script for the agent
  cat > /workspace/activate_env.sh << 'EOF'
  #!/bin/bash
  source /tmp/openpilot-env/bin/activate
  cd /workspace
  echo "🎯 OpenPilot environment ready"
  echo "🏗️  Build with: scons -j4"
  echo "🧪 Test with: python -m pytest selfdrive/test/"
  echo "🗺️  Current branch: $(git branch --show-current)"
  EOF

  chmod +x /workspace/activate_env.sh

  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  echo "✅ Bootstrap completed in ${DURATION}s"
  echo "🔧 Run: source /workspace/activate_env.sh"

  # Activate environment for immediate use
  source /tmp/openpilot-env/bin/activate