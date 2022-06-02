#!/usr/bin/env bash

################################################################################
# Setup
################################################################################

PYTHON="python"
while true; do
  case "$1" in
    --python ) PYTHON="$2"; shift 2 ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

function fail(){
    echo "**Failed!**"
    exit 1
}

function realpath() {
  OURPWD=$PWD
  cd "$(dirname "$1")"
  LINK=$(readlink "$(basename "$1")")
  while [ "$LINK" ]; do
    cd "$(dirname "$LINK")"
    LINK=$(readlink "$(basename "$1")")
  done
  REALPATH="$PWD/$(basename "$1")"
  cd "$OURPWD"
  echo "$REALPATH"
}


DIR=$(realpath $(dirname $0))
pushd "$DIR" > /dev/null

VERSION=`head -1 ../res/version.txt`


################################################################################
# Compile UI and resources
################################################################################
echo "**Compiling QT Resources and UI**"
pushd ../ > /dev/null
$PYTHON compile.py || fail
popd > /dev/null


################################################################################
# Create pyinstaller binary
################################################################################
echo "**Creating PyInstaller Binary**"
rm -rf macos/build/ || fail
rm -rf macos/dist/ArPiRobot-DeployTool.app/ || fail
rm -rf macos/dist/ArPiRobot-DeployTool/ || fail
cd macos/
pyinstaller macos.spec || fail
cd ..


################################################################################
# Create Zip
################################################################################
echo "**Creating Zip**"
pushd macos/dist > /dev/null
zip -r ArPiRobot-DeployTool-macOS-x64.app.zip ArPiRobot-DeployTool.app
popd > /dev/null
mkdir ./dist/
cp macos/dist/ArPiRobot-DeployTool-macOS-x64.app.zip ./dist


################################################################################
# Cleanup
################################################################################

rm -rf macos/build/
rm -rf macos/dist/ArPiRobot-DeployTool.app/
rm -rf macos/dist/ArPiRobot-DeployTool/

popd > /dev/null
