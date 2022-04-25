@echo off

cd %~dp0

echo **Compiling UI and Resources**
cd ..
python compile.py
cd packaging

echo **Creating PyInstaller Binary**
rmdir /Q/S .\windows\build\
rmdir /Q/S .\windows\dist\ArPiRobot-DeployTool\
cd .\windows
pyinstaller windows.spec
cd ..

echo **Creating Installer**
C:\"Program Files (x86)"\"Inno Setup 6"\Compil32.exe /cc windows\win_installer.iss

rmdir /Q/S .\windows\dist\ArPiRobot-DeployTool