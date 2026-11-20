#!/usr/bin/env bash
# Downloads the two auxiliary models to the default folders of config.ini (both with licenses that allow commercial
# use):
#   - the RealESRGAN_x4plus_anime_6B upscaler (BSD-3-Clause) for the hires fix;
#   - the lbpcascade_animeface cascade (MIT) for the face fix.
# A file that already exists is not downloaded again. The checkpoint (Pony) is not downloaded: docs/installation.md.
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
download() {
    destination="$ROOT/$1"; url="$2"
    if [ -f "$destination" ]; then echo "already there: $1"; return; fi
    mkdir -p "$(dirname "$destination")"
    curl -fsSL --retry 3 -o "$destination.partial" "$url" && mv "$destination.partial" "$destination" && echo "downloaded: $1"
}
download models/upscalers/RealESRGAN_x4plus_anime_6B.pth \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
download models/detectors/lbpcascade_animeface.xml \
    https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml
