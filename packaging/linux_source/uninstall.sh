#!/usr/bin/env bash

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

DIR=$(realpath $(dirname $0))

pushd "$DIR" > /dev/null

if touch test.txt 2> /dev/null; then
    rm test.txt
else
    echo "Run as root (sudo)."
    exit 2
fi

if [ "$1" != "-q" ]; then 
    echo "**WARNING:** This will delete the entire directory: $DIR"
    if ! confirm "Continue with uninstall?"; then
        echo "Cancelling uninstall."
        exit 0
    fi
fi

echo "Removing virtual environment"
rm -rf env/

echo "Removing pycache"
find src -type d -name __pycache__ -exec rm -r {} \; > /dev/null 2>&1

echo "Removing desktop menu entry"
xdg-desktop-menu uninstall io.github.arpirobot.DeployTool.desktop > /dev/null 2>&1
rm io.github.arpirobot.DeployTool.desktop

echo "Deleting $DIR"
rm -rf "$DIR"
