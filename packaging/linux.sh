#!/usr/bin/env bash

set -e

################################################################################
# Setup
################################################################################

function fail(){
    echo "**Failed!**"
    exit 1
}


DIR=$(realpath $(dirname $0))
pushd "$DIR" > /dev/null

VERSION=`head -1 ../res/version.txt`


################################################################################
# Compile UI and resources
################################################################################
echo "**Compiling QT Resources and UI**"
pushd ../ > /dev/null
python compile.py || fail
popd > /dev/null


################################################################################
# Create pyinstaller binary
################################################################################
echo "**Creating PyInstaller Binary**"
rm -rf linux/build/ || fail
rm -rf linux/dist/ArPiRobot-DeployTool/ || fail
cd linux/
pyinstaller linux.spec || fail
cd ..


################################################################################
# Create AppImage
################################################################################
echo "**Creating AppImage**"
wget https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage -O appimagetool
chmod +x ./appimagetool
pushd linux/ > /dev/null
cp io.github.arpirobot.DeployTool.desktop dist/ArPiRobot-DeployTool
cp io.github.arpirobot.DeployTool.appdata.xml dist/ArPiRobot-DeployTool
mkdir -p dist/ArPiRobot-DeployTool/usr/share/icons/hicolor/256x256/apps/
cp ../../res/icon.png dist/ArPiRobot-DeployTool/usr/share/icons/hicolor/256x256/apps/arpirobot-deploytool.png
ln -s ./usr/share/icons/hicolor/256x256/apps/arpirobot-deploytool.png dist/ArPiRobot-DeployTool/arpirobot-deploytool.png
mv dist/ArPiRobot-DeployTool/ArPiRobot-DeployTool dist/ArPiRobot-DeployTool/AppRun
mkdir -p ../dist/
dd if=/dev/zero bs=1 count=3 seek=8 conv=notrunc of=../appimagetool
../appimagetool --appimage-extract-and-run dist/ArPiRobot-DeployTool ../dist/ArPiRobot-DeployTool-Liunx-x64.AppImage
popd > /dev/null

################################################################################
# Cleanup
################################################################################

rm -rf linux/build/
rm -rf linux/dist/ArPiRobot-DeployTool/
rm -f appimagetool

popd > /dev/null
