#!/bin/sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v pipx >/dev/null 2>&1; then
    printf 'pipx is required. Install it first: https://pipx.pypa.io/stable/installation/\n' >&2
    exit 1
fi

pipx install --force --editable "$PROJECT_DIR"
pipx ensurepath
