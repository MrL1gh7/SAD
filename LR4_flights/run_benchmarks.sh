#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p results
python resume_benchmarks.py
