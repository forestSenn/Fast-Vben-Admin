#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python -m app.backend_pre_start

# Run migrations
alembic upgrade head

# Create initial data in DB
python -m app.initial_data
