#!/usr/bin/env bash
set -e

# Disable SSL verification
export PYTHONHTTPSVERIFY=0
export GIT_SSL_NO_VERIFY=true
export CURL_CA_BUNDLE=""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
ROOT=$DIR/../
cd $ROOT

RC_FILE="${HOME}/.$(basename ${SHELL})rc"
if [ "$(uname)" == "Darwin" ] && [ $SHELL == "/bin/bash" ]; then
  RC_FILE="$HOME/.bash_profile"
fi

if ! command -v "pyenv" > /dev/null 2>&1; then
  echo "pyenv install ..."
  curl -L --insecure https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
  PYENV_PATH_SETUP="export PATH=\$HOME/.pyenv/bin:\$HOME/.pyenv/shims:\$PATH"
fi

if [ -z "$PYENV_SHELL" ] || [ -n "$PYENV_PATH_SETUP" ]; then
  echo "pyenvrc setup ..."
  cat <<EOF > "${HOME}/.pyenvrc"
if [ -z "\$PYENV_ROOT" ]; then
  $PYENV_PATH_SETUP
  export PYENV_ROOT="\$HOME/.pyenv"
  eval "\$(pyenv init -)"
  eval "\$(pyenv virtualenv-init -)"
fi
EOF

  SOURCE_PYENVRC="source ~/.pyenvrc"
  if ! grep "^$SOURCE_PYENVRC$" $RC_FILE > /dev/null; then
    printf "\n$SOURCE_PYENVRC\n" >> $RC_FILE
  fi

  eval "$SOURCE_PYENVRC"
  # $(pyenv init -) produces a function which is broken on bash 3.2 which ships on macOS
  if [ $(uname) == "Darwin" ]; then
    unset -f pyenv
  fi
fi

export MAKEFLAGS="-j$(nproc)"

PYENV_PYTHON_VERSION=$(cat $ROOT/.python-version)
if ! pyenv prefix ${PYENV_PYTHON_VERSION} &> /dev/null; then
  # no pyenv update on mac
  if [ "$(uname)" == "Linux" ]; then
    echo "pyenv update ..."
    GIT_SSL_NO_VERIFY=true pyenv update
  fi
  echo "python ${PYENV_PYTHON_VERSION} install ..."
  CONFIGURE_OPTS="--enable-shared" PYTHON_CONFIGURE_OPTS="--with-openssl-rpath=auto" CFLAGS="-O2" pyenv install -f ${PYENV_PYTHON_VERSION}
fi
eval "$(pyenv init --path)"

# Skip pip update
echo "Using existing pip version"
# Install poetry without updating pip
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-deps poetry==1.7.0

poetry config virtualenvs.prefer-active-python true --local
poetry config virtualenvs.in-project true --local

echo "PYTHONPATH=${PWD}" > $ROOT/.env
if [[ "$(uname)" == 'Darwin' ]]; then
  echo "# msgq doesn't work on mac" >> $ROOT/.env
  echo "export ZMQ=1" >> $ROOT/.env
  echo "export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES" >> $ROOT/.env
fi

poetry self add --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-deps poetry-dotenv-plugin@^0.1.0

echo "pip packages install..."
# Set Poetry to ignore SSL verification
poetry config certificates.verify false
# Add --no-deps to prevent hash verification issues
poetry install --no-cache --no-root --no-deps

pyenv rehash

[ -n "$POETRY_VIRTUALENVS_CREATE" ] && RUN="" || RUN="poetry run"

if [ "$(uname)" != "Darwin" ] && [ -e "$ROOT/.git" ]; then
  echo "pre-commit hooks install..."
  GIT_SSL_NO_VERIFY=true $RUN pre-commit install
  GIT_SSL_NO_VERIFY=true $RUN git submodule foreach pre-commit install
fi
