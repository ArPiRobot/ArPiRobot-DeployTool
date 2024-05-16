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

Packaging is done using pyinstaller to create a binary for the program. This must be done on the native OS (it is not possible to "cross compile"). As such, github actions is used for the builds.

Widows additionally uses InnoSetup to create an installer for the program.

Linux additionally packages the binary into an AppImage.
