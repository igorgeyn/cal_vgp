#!/bin/bash
# Helper script to run Python with Poetry if available, otherwise use system Python

if command -v poetry &> /dev/null; then
    # Poetry is available
    exec poetry run python "$@"
else
    # Fall back to system Python
    exec python "$@"
fi