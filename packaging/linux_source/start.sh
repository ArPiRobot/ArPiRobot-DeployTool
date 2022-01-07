#!/usr/bin/env bash

DIR=$(realpath $(dirname $0))
cd "$DIR"
env/bin/python src/main.py
