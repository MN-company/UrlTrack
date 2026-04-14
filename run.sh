#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r server/requirements.txt

export FLASK_APP=server:create_app
export FLASK_ENV=development

SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
