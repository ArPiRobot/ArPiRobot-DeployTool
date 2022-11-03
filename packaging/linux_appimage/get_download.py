#!/usr/bin/env python3

import json
import requests

res = requests.get("https://api.github.com/repos/niess/python-appimage/releases")
j = json.loads(res.content.decode())
frel = None
for release in j:
    if "tag_name" in release and release["tag_name"] == "python3.10":
        frel = release
        break
if frel is None:
    exit(1)
fasset = None
for asset in frel["assets"]:
    if asset["name"].endswith("manylinux2014_x86_64.AppImage"):
        fasset = asset
        break
if fasset is None:
    exit(1)
print(fasset["browser_download_url"], flush=True)
exit(0)

