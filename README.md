# ArPiRobot-DeployTool


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

```sh
python -m pip install -r requirements.txt
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

Packaging for linux is done by bundling the sources and using an installation script to setup a virtual environment. This can generate `deb` and self-extracting `run` packages. Python3 is required to be provided by the distribution, along with the venv and pip modules. Internet access is required during installation.

```shell
source env/bin/activate
cd packaging
./linux_source.sh
```
