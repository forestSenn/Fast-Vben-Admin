#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python -m app.backend_pre_start

# Run the selected edition under the module migration orchestrator
python -m app.modules.migrate --edition "${APP_EDITION:-suite}"

# Create initial data in DB
python -m app.initial_data
