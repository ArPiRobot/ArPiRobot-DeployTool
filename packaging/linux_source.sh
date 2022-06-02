#!/usr/bin/env bash

################################################################################
# Functions
################################################################################

function fail(){
    echo "**Failed!**"
    exit 1
}

function confirm() {
    read -r -p "$1 [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            true
            ;;
        *)
            false
            ;;
    esac
}


################################################################################
# Setup
################################################################################

BUILD_TAR="ask"
BUILD_DEB="ask"
PYTHON="python"

while true; do
  case "$1" in
    --tar ) BUILD_TAR="$2"; shift 2 ;;
    --deb ) BUILD_DEB="$2"; shift 2 ;;
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
python compile.py || fail
popd > /dev/null


################################################################################
# Create folder structure
################################################################################
echo "**Creating Package Structure**"
rm -rf build/ || fail
rm -rf dist/ArPiRobot-DeployTool || fail

mkdir -p ./dist/ArPiRobot-DeployTool/

cp -r ../src/ ./dist/ArPiRobot-DeployTool/
cp ../requirements.txt ./dist/ArPiRobot-DeployTool/
cp -r ../res/icon.png ./dist/ArPiRobot-DeployTool/
cp ../COPYING ./dist/ArPiRobot-DeployTool
cp linux_source/install.sh ./dist/ArPiRobot-DeployTool
cp linux_source/uninstall.sh ./dist/ArPiRobot-DeployTool
cp linux_source/start.sh ./dist/ArPiRobot-DeployTool

# Remove pyinstaller from requirements.txt
sed -i "s/pyinstaller//g" ./dist/ArPiRobot-DeployTool/requirements.txt

################################################################################
# Tarball package
################################################################################
if [ "$BUILD_TAR" == "ask" ]; then
    if confirm "Create tar.gz package?"; then
        BUILD_TAR="yes"
    fi
fi
if [ "$BUILD_TAR" == "yes" ]; then
    echo "**Creating tar.gz package**"
    pushd dist > /dev/null
    tar -zcvf ArPiRobot-DeployTool-Linux-Any.tar.gz ArPiRobot-DeployTool/ || fail
    popd > /dev/null
fi


################################################################################
# Deb package
################################################################################
if [ "$BUILD_DEB" == "ask" ]; then
    if confirm "Create deb package?"; then
        BUILD_DEB="yes"
    fi
fi
if [ "$BUILD_DEB" == "yes" ]; then
    echo "**Creating deb package**"

    pushd dist > /dev/null

    # Setup folder structure
    mkdir arpirobot-deploytool_$VERSION
    mkdir arpirobot-deploytool_$VERSION/DEBIAN
    mkdir arpirobot-deploytool_$VERSION/opt
    mkdir arpirobot-deploytool_$VERSION/opt/ArPiRobot-DeployTool
    mkdir -p arpirobot-deploytool_$VERSION/usr/share/doc/arpirobot-deploytool/
    mkdir -p arpirobot-deploytool_$VERSION/usr/share/metainfo/

    # Copy files
    cp ../linux_source/arpirobot-deploytool.appdata.xml ./arpirobot-deploytool_$VERSION/usr/share/metainfo/
    cp ./ArPiRobot-DeployTool/COPYING ./arpirobot-deploytool_$VERSION/usr/share/doc/arpirobot-deploytool/copyright
    cp -r ./ArPiRobot-DeployTool/* ./arpirobot-deploytool_$VERSION/opt/ArPiRobot-DeployTool/
    cp ../linux_source/deb_control ./arpirobot-deploytool_$VERSION/DEBIAN/control
    cp ../linux_source/deb_prerm ./arpirobot-deploytool_$VERSION/DEBIAN/prerm
    cp ../linux_source/deb_postinst ./arpirobot-deploytool_$VERSION/DEBIAN/postinst
    chmod 755 ./arpirobot-deploytool_$VERSION/DEBIAN/*

    # Generate package
    dpkg-deb --build arpirobot-deploytool_$VERSION || fail
    mv arpirobot-deploytool_$VERSION.deb ArPiRobot-DeployTool-Ubuntu-Any.deb

    rm -rf ./arpirobot-deploytool_$VERSION/

    popd > /dev/null
fi


################################################################################
# Cleanup
################################################################################

rm -rf build/
rm -rf dist/ArPiRobot-DeployTool/

popd > /dev/null