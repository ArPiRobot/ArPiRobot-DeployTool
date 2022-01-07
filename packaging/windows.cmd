@echo off

cd %~dp0

echo **Compiling UI and Resources**
cd ..
python compile.py
cd packaging

echo **Creating PyInstaller Binary**
rmdir /Q/S .\build\
rmdir /Q/S .\dist\ArPiRobot-DeployTool\
pyinstaller windows\windows.spec

echo **Creating Installer**
C:\"Program Files (x86)"\"Inno Setup 6"\Compil32.exe /cc windows\win_installer.iss

rmdir /Q/S .\dist\ArPiRobot-DeployTool