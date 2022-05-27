#!/usr/bin/env bash

DIR=$(realpath $(dirname "$0"))
pushd "$DIR" > /dev/null
./AppRunOrig src/main.py
popd > /dev/null

