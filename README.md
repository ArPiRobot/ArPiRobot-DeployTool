# ArPiRobot-DeployTool


## Building and Running

### Dependencies

- Python3
- Python3 venv module

### Run

```sh
# Any OS
python3 -m venv env

# Windows Only
.\env\script\activate

# macOS / Linux Only
source env/bin/activate

# Any OS
python -m pip install -r requirements.txt -U
python compile
python src/main.py
```

### Packaging

1. Make sure the version number is set correctly by using `python change-version.py NEW_VERSION`

2. Commit and push any changes

3. Launch the github actions pipeline "Build Release" through github's web UI

4. Download the package artifacts from the job's summary when it finishes


### Packaging Details

Packaging for Windows and macOS is done using pyinstaller to create a binary for the program. This must be done on the native OS (it is not possible to "cross compile"). As such, github actions is used for the builds.

Widows additionally uses InnoSetup to create an installer for the program.

Linux packages are done using source code. It is assumed that python will be available on any Linux distro. Furthermore, pyinstaller on Linux is not always the most reliable (there are potential glibc compatability issues, limited support for stripping out unused libs, etc). Thus, the linux packages deploy the source code along with a script to install / uninstall the program. These scripts create a virtual environment and install required libs from pypi. 

Linux packages are provided in deb and run formats. Run is just a self extracting archive (must make sure to install python first on your OS as there is no dependency checking).
