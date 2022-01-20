#!/usr/bin/env bash

################################################################################
# Functions
################################################################################

function fail(){
    echo "**Failed!**"
    exit 1
}


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
# Create folder structure
################################################################################
echo "**Creating Package Structure**"
rm -rf build/ || fail
rm -rf dist/ArPiRobot-DeployTool || fail

mkdir -p ./dist/ArPiRobot-DeployTool/

cp -r ../src/ ./dist/ArPiRobot-DeployTool/

if $PYTHON -c "import PySide6" &> /dev/null; then
    cp ../requirements-qt6.txt ./dist/ArPiRobot-DeployTool/requirements.txt
    QTVER=6
else
    cp ../requirements-qt5.txt ./dist/ArPiRobot-DeployTool/requirements.txt
    QTVER=5
fi

cp -r ../res/icon.png ./dist/ArPiRobot-DeployTool/
cp ../COPYING ./dist/ArPiRobot-DeployTool
cp linux_generic/install.sh ./dist/ArPiRobot-DeployTool
cp linux_generic/uninstall.sh ./dist/ArPiRobot-DeployTool
cp linux_generic/start.sh ./dist/ArPiRobot-DeployTool
cp linux_generic/start_syspkg.sh ./dist/ArPiRobot-DeployTool

# Remove pyinstaller from requirements.txt
sed -i "s/pyinstaller//g" ./dist/ArPiRobot-DeployTool/requirements.txt

################################################################################
# Tarball package
################################################################################
echo "**Creating tar.gz package**"
pushd dist > /dev/null
tar -zcvf ArPiRobot-DeployTool-${VERSION}-QT${QTVER}.tar.gz ./ArPiRobot-DeployTool/ || fail
popd > /dev/null


################################################################################
# Cleanup
################################################################################

rm -rf build/
rm -rf dist/ArPiRobot-DeployTool/

popd > /dev/null