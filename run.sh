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

./venv/bin/flask db upgrade
./venv/bin/flask run --host=127.0.0.1 --port=8000
