#!/usr/bin/env bash

DIR=$(realpath $(dirname $0))

pushd "$DIR" > /dev/null

if ! which python3 > /dev/null; then
    echo "Python 3 must be installed."
    exit 1
fi

if touch test.txt; then
    rm test.txt
else
    echo "Run as root."
    exit 2
fi

# Remove virtual env if one exists
rm -rf env/

# Create and setup python virtual environment
echo "Creating python environment"
if ! python3 -m venv env; then
    echo "Install pyton3 venv package."
    exit 3
fi
source env/bin/activate
python -m pip install -r requirements.txt > /dev/null
deactivate

# Desktop menu entry
xdg-desktop-menu uninstall ArPiRobot-DeployTool.desktop > /dev/null 2>&1
echo "Adding desktop menu entry"
printf "[Desktop Entry]\nVersion=1.1\nType=Application\nTerminal=false\nName=ArPiRobot Deploy Tool\nComment=PC-side tool to manage and configure ArPiRobot robots.\nIcon=$DIR/icon.png\nExec=$DIR/start.sh\nActions=\nCategories=Development;\nStartupNotify=true\nStartupWMClass=com-arpirobot-deploytool-DeployTool\n" > ArPiRobot-DeployTool.desktop
xdg-desktop-menu install --novendor ArPiRobot-DeployTool.desktop

popd > /dev/null
