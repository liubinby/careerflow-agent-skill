#!/bin/sh
# Retain the familiar spelling as an alias.
set -eu
exec "$(dirname "$0")/run_self_training.sh" "$@"
