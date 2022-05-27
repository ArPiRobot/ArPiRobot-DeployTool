#!/usr/bin/env bash

DIR=$(realpath $(dirname "$0"))
pushd "$DIR" > /dev/null
./ArPiRobot-DeployTool
popd > /dev/null

