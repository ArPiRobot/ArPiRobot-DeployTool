#!/usr/bin/env bash

# Create an AppImage for ArPiRobot Deploy Tool using pyinstaller to reduce
# AppImage size. Raw appimage based on appimage python interpreters can be
# created and bundle program sources, but requires bundling all libraries
# for PySide6. This creates much larger (3-4x) appimages than using
# pyinstaller to create a binary and making an appimage from that binary.
# 
# pyinstaller is run using a python appimage that is downloaded by this script
# these appimages are build using the manylinux platform and ensure that
# pyinstaller binaries should work as intended on multiple distributions
# 
# The resultant binary is bundled into an appimage that is then executable
# on any distribution where the original python appimage would work
#


# Work in linux_appimagepyinstaller directory
DIR=$(realpath $(dirname "$0"))
pushd "$DIR/linux_appimagepyinstaller"> /dev/null

# Remove previously extracted resources and appimages
rm -f ArPirobot-DeployTool.appimage
rm -rf squashfs-root
rm -rf build
rm -rf dist

# Download python appimage if one does not already exist
if [[ ! -f python.appimage ]]; then
    wget https://github.com/niess/python-appimage/releases/download/python3.10/python3.10.4-cp310-cp310-manylinux2014_x86_64.AppImage -O python.appimage
fi

# Download appimagetool appimage if one does not already exist
if [[ ! -f appimagetool.appimage ]]; then
    wget https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage -O appimagetool.appimage
fi


# Extract base python appimage (extracts to squashfs-root)
chmod +x python.appimage
./python.appimage --appimage-extract

# Install requirements to build deploy tool
# Pyinstaller is also installed by requirements.txt
cd squashfs-root
./AppRun -m pip install -U -r ../../../requirements.txt --ignore-installed

# Compile resources
PATH=usr/bin/:$PATH ./AppRun ../../../compile.py

# Generate binary using pyinstaller
cd ..
squashfs-root/usr/bin/pyinstaller linux.spec

# Make directory for icon in pyinstaller dist and copy icon
mkdir -p dist/ArPiRobot-DeployTool/usr/share/icons/hicolor/256x256/apps/
cp ../../res/icon.png dist/ArPiRobot-DeployTool/usr/share/icons/hicolor/256x256/apps/arpirobot-deploytool.png
ln -s usr/share/icons/hicolor/256x256/apps/arpirobot-deploytool.png dist/ArPiRobot-DeployTool/arpirobot-deploytool.png

# Copy desktop file and appdata
cp arpirobot-deploytool.desktop dist/ArPiRobot-DeployTool
cp arpirobot-deploytool.appdata.xml dist/ArPiRobot-DeployTool

# Copy start script
cp start.sh dist/ArPiRobot-DeployTool/AppRun
chmod a+x dist/ArPiRobot-DeployTool/AppRun

# Create appimage file
chmod +x ./appimagetool.appimage
ARCH=x86_64 ./appimagetool.appimage --no-appstream dist/ArPiRobot-DeployTool ArPirobot-DeployTool-x86_64.AppImage