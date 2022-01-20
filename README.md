# ArPiRobot-DeployTool

## Installation

Downloads are available on the releases page.

### Windows

For windows, an installer `exe` is provided. Download and run this installer.

### macOS

For macOS, a zipped app is provided. Download the zip, double click it to extract and drag the resulting `.app` file to your `Applications` folder.

### Linux

**Ubuntu & Other Debian Based Distros:** Download and install the `deb` package.

**Other**: Install python 3, pip, and venv using your distribution's package manager or by building from source. Download and extract the `tar.gz` package. Extract it somewhere on your system and run the included `install.sh` script. This script will create a python environment for the program and a desktop menu entry for it. The included `uninstall.sh` script removes these things and should be run before deleting the directory the program is stored in. If you want to use system python packages instead of using pip to install python packages, run `install.sh syspkg` instead of `install.sh`


## Building and Running

First, make sure python3 is installed. On windows, the executable name may be `python` not `python3`.


### Create a Virtual Environment
```sh
python3 -m venv env
```

### Activate the environment

- On Windows (powershell)
    ```sh
    .\env\Scripts\Activate.Ps1
    ```

- On Windows (cmd)
    ```sh
    env\Scripts\activate.bat
    ```

- On Linux or macOS (or Git Bash in Windows)
    ```sh
    source env/bin/activate
    ```

### Install Required Libraries

Run one of the following commands. QT6 is recommended on non-Linux systems. QT5 is more compatible with most linux systems and can more easily allow using system packages.

```sh
python -m pip install -r requirements-qt6.txt
python -m pip install -r requirements-qt5.txt
```

### Compiling UI and Resource Files

```sh
python compile.py
```

### Running

```sh
python src/main.py
```

## Change Version Number

```sh
python change-version.py NEW_VERSION
```


## Packaging

### Windows

Packaging for windows uses two tools. First, pyinstaller is used to create a minimal python distribution and an executable for the app from the python source. Then InnoSetup is used to create an installer for the program. Since pyinstaller is used, this process must be performed on a windows PC.

```shell
.\env\bin\activate
cd packaging
.\windows.cmd
```

### macOS

Packaging for macOS uses pyinstaller to create the app. The app is then zipped for distribution. Since pyinstaller is used, this process must be performed on a mac. Furthermore, building native apps for an arm (Apple Silicon) mac is currently not supported (at time of writing pyinstaller has support but some dependency python packages do not have native arm build for macOS available).

```shell
source env/bin/activate
cd packaging
./macos.sh
```

### Linux

Packaging for linux is done by bundling the sources and using an installation script to setup a virtual environment or run the program using the system's python interpreter. This requires that a compatible python3 interpreter be installed on the system.

```shell
source env/bin/activate
cd packaging
./linux_source.sh
```
