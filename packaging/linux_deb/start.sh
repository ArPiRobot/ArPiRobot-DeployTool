#!/usr/bin/evn bash

DIR=$(realpath $(dirname $0))
cd "$DIR"
python3 src/main.py
