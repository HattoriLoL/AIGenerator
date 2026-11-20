"""The second half of the setup (setup.sh on Linux, setup.bat on Windows), after "uv sync": the folders, the models,
config.local.ini and the shortcut. Written once for both systems and run with the environment's Python:

    python -m aigen.install [--no-models] [--no-shortcut] [--verify] [--icon FILE] [--remove-shortcut]

Safe to run again: what is done is skipped, and the user's files are never overwritten (a model already in place is
kept, config.local.ini is only written when it does not exist). The details are in docs/installation.md. Exit code: 0
done, 1 a step failed (a download, the hash, the shortcut), 2 a wrong option or an unreadable configuration.

Pure module (standard library only): it runs, and --help works, with any Python 3.11+.
"""
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from aigen import config, contract, generate

# The models setup downloads: where from, where to (relative to the root), the exact size and the SHA256. "key" is the
# config.py key that points to the file: when it points to another existing file, that one is used and nothing is
# downloaded.
MODELS = (
    {"name": "Pony Diffusion V6 XL (the checkpoint)", "key": "checkpoint",
     "url": "https://civitai.com/api/download/models/290640?fileId=228616",
     "file": "models/checkpoints/ponyDiffusionV6XL.safetensors", "size": 6938041050,
     "sha256": "67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3",
     "page": "https://civitai.com/models/257749/pony-diffusion-v6-xl",
     "note": "The Pony Diffusion V6 XL license (a modified Fair AI Public License 1.0-SD) is set by its author: read "
             "it on the model page before using the model, in particular for commercial use"},
    {"name": "RealESRGAN_x4plus_anime_6B (the hires fix upscaler, BSD-3-Clause)", "key": "upscaler",
     "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
     "file": "models/upscalers/RealESRGAN_x4plus_anime_6B.pth", "size": 17938799,
     "sha256": "f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da",
     "page": "https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.2.4", "note": ""},
    {"name": "lbpcascade_animeface (the face fix detector, MIT)", "key": "face_detector",
     "url": "https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml",
     "file": "models/detectors/lbpcascade_animeface.xml", "size": 246945,
     "sha256": "9376d30ac38db6bda2a68b88b3b76bbd7e6aa33af47f7f5c76bc88ca75f1ce30",
     "page": "https://github.com/nagadomi/lbpcascade_animeface", "note": ""},
)
FOLDERS = ("models/checkpoints", "models/loras", "models/upscalers", "models/detectors", "characters", "output")
CIVITAI_VARIABLE = "AIGEN_CIVITAI_TOKEN"  # an optional Civitai API key, sent only to civitai.com, never stored
DISK_MARGIN = 1024 ** 3  # free space left after the downloads
USER_AGENT = "AIGenerator-setup"
CHUNK = 1024 * 1024
SHORTCUT_COMMENT = "Anime characters with Pony Diffusion XL (local web interface)"


class DownloadError(Exception):
    """A model could not be downloaded or did not match its size or hash."""


def parser():
    p = generate._Options(prog=contract.command("setup"),
                          description="Installs AIGenerator: the folders, the models, config.local.ini and the "
                                      "shortcut. Safe to run again: what is done is skipped.")
    p.add_argument("--no-models", action="store_true", help="do not download the models")
    p.add_argument("--no-shortcut", action="store_true", help="do not create the shortcut")
    p.add_argument("--verify", action="store_true",
                   help="check the SHA256 of the models already in place too (slow for the 6.5 GB checkpoint)")
    p.add_argument("--no-gpu-check", action="store_true",
                   help="continue without an NVIDIA GPU (the check itself is done by setup, before uv)")
    p.add_argument("--icon", metavar="FILE",
                   help="the shortcut's icon (.svg or .png on Linux, .ico on Windows; default: the system's)")
    p.add_argument("--remove-shortcut", action="store_true", help="only remove the shortcut, and stop")
    return p


def parse_args(argv):
    return parser().parse_args(argv)


# ---- the models

def plan(entry, root, cfg, verify=False):
    """What to do with one model: "download", "keep" (in place with the right size), "check" (in place, --verify),
    "wrong_size" (a file of another size is in place: it is never overwritten) or "elsewhere" (the configuration
    points to another existing file)."""
    path = os.path.normpath(os.path.join(root, entry["file"]))
    configured = getattr(cfg, entry["key"], "") if cfg is not None else ""
    if configured and os.path.normpath(configured) != path and os.path.isfile(configured):
        return "elsewhere"
    if not os.path.isfile(path):
        return "download"
    if os.path.getsize(path) != entry["size"]:
        return "wrong_size"
    return "check" if verify else "keep"


def missing_bytes(entry, root):
    """How much is still to download (a .partial file of an interrupted download is resumed)."""
    partial = os.path.join(root, entry["file"]) + ".partial"
    have = os.path.getsize(partial) if os.path.isfile(partial) else 0
    return max(0, entry["size"] - have)


def enough_space(free, needed, margin=DISK_MARGIN):
    return free >= needed + margin


def gigabytes(n):
    return "%.1f GB" % (n / 1e9)


def size_text(n):
    return gigabytes(n) if n >= 1e9 else "%.1f MB" % (n / 1e6)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def is_civitai(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host == "civitai.com" or host.endswith(".civitai.com")


def make_request(url, token=None, offset=0):
    """The download request. The token goes only to civitai.com, and as an "unredirected" header: it is not sent to
    the storage server Civitai redirects to."""
    r = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if offset:
        r.add_header("Range", "bytes=%d-" % offset)
    if token and is_civitai(url):
        r.add_unredirected_header("Authorization", "Bearer " + token)
    return r


def _ssl_context():
    import ssl
    try:  # the CA bundle of the environment when it has one (a standalone Python may not find the system's)
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class _Progress:
    """Prints the progress of a download: on one line in a terminal, every 10 % otherwise."""

    def __init__(self, size, out):
        self.size, self.out, self.tty = size, out, out.isatty()
        self.start, self.last, self.step = time.monotonic(), 0.0, -1

    def __call__(self, done, fresh):
        now = time.monotonic()
        percent = 100 * done // max(1, self.size)
        if self.tty and (now - self.last >= 0.5 or done >= self.size):
            speed = fresh / max(0.001, now - self.start) / 1e6
            self.out.write("\r  %3d%%  %s of %s  %.1f MB/s   " % (percent, size_text(done), size_text(self.size), speed))
            self.last = now
        elif not self.tty and percent // 10 > self.step:
            self.out.write("  %d%%\n" % percent)
            self.step = percent // 10
        if self.tty and done >= self.size:
            self.out.write("\n")
        self.out.flush()


def _open(url, token, offset):
    context = _ssl_context() if url.lower().startswith("https:") else None
    try:
        r = urllib.request.urlopen(make_request(url, token, offset), timeout=60, context=context)
    except urllib.error.HTTPError as e:
        raise DownloadError("the server answered %d %s" % (e.code, e.reason))
    except (urllib.error.URLError, OSError) as e:
        raise DownloadError("could not connect: %s" % getattr(e, "reason", e))
    if url.lower().startswith("http") and r.headers.get_content_type() == "text/html":
        r.close()
        raise DownloadError("the server sent a web page instead of the file (it may ask for a login)")
    return r


def _receive(r, partial, entry, have, out):
    """Writes the answer to the .partial file (appending when the server resumes) and returns the SHA256."""
    h = hashlib.sha256()
    resumed = have and (getattr(r, "status", None) or 200) == 206
    if resumed:
        with open(partial, "rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                h.update(block)
    else:
        have = 0
    length = r.headers.get("Content-Length")
    if length and length.isdigit() and have + int(length) != entry["size"]:
        raise DownloadError("the server sends %d bytes; expected %d" % (have + int(length), entry["size"]))
    progress, done = _Progress(entry["size"], out), have
    with open(partial, "ab" if resumed else "wb") as f:
        try:
            for block in iter(lambda: r.read(CHUNK), b""):
                f.write(block)
                h.update(block)
                done += len(block)
                progress(done, done - have)
        except OSError as e:
            raise DownloadError("the download stopped at %s: %s (run setup again to resume it)"
                                % (gigabytes(done), e))
    if done != entry["size"]:
        if done > entry["size"]:
            os.remove(partial)
        raise DownloadError("got %d bytes; expected %d (run setup again)" % (done, entry["size"]))
    return h.hexdigest()


def download(entry, path, token=None, out=None):
    """Downloads one model to `path` through `path`.partial, checking the size and the SHA256, and only then renames
    it. A wrong hash removes the partial file. Raises DownloadError."""
    out = out or sys.stdout
    partial = path + ".partial"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    have = os.path.getsize(partial) if os.path.isfile(partial) else 0
    if have > entry["size"]:
        os.remove(partial)
        have = 0
    if have == entry["size"]:  # a complete .partial whose rename did not happen
        digest = sha256_of(partial)
    else:
        with _open(entry["url"], token, have) as r:
            digest = _receive(r, partial, entry, have, out)
    if digest != entry["sha256"]:
        os.remove(partial)
        raise DownloadError("the SHA256 is %s; expected %s (the file was removed)" % (digest, entry["sha256"]))
    os.replace(partial, path)


def manual_hint(entry, root, token=None):
    hint = "download it by hand from %s and save it as %s, then run setup again" % (
        entry["page"], os.path.normpath(os.path.join(root, entry["file"])))
    if is_civitai(entry["url"]) and not token:
        hint += " (or set %s to a Civitai API key and run setup again)" % CIVITAI_VARIABLE
    return hint


# ---- the summary

class Report:
    """What setup did, printed as it happens and again in the summary at the end."""

    def __init__(self, out=None, err=None):
        self.out, self.err = out or sys.stdout, err or out or sys.stderr
        self.lines, self.failed = [], False

    def add(self, text):
        self.lines.append(text)
        print(text, file=self.out)

    def error(self, text):
        self.failed = True
        self.lines.append("ERROR: " + text)
        self.out.flush()
        print("ERROR: " + text, file=self.err)


def get_models(root, cfg, verify, report, environ=None):
    environ = os.environ if environ is None else environ
    token = environ.get(CIVITAI_VARIABLE, "").strip() or None
    todo = []
    for entry in MODELS:
        path = os.path.normpath(os.path.join(root, entry["file"]))
        action = plan(entry, root, cfg, verify)
        if action == "elsewhere":
            report.add("kept: %s (the configuration points to %s)" % (entry["name"], getattr(cfg, entry["key"])))
        elif action == "keep":
            report.add("already there: %s" % entry["file"])
        elif action == "wrong_size":
            report.error("%s has %d bytes; expected %d. It was left alone: delete it and run setup again"
                         % (path, os.path.getsize(path), entry["size"]))
        elif action == "check":
            if sha256_of(path) == entry["sha256"]:
                report.add("checked: %s" % entry["file"])
            else:
                report.error("%s does not have the expected SHA256. It was left alone: delete it and run setup again"
                             % path)
        else:
            todo.append(entry)
    needed = sum(missing_bytes(e, root) for e in todo)
    free = shutil.disk_usage(os.path.join(root, "models")).free
    if todo and not enough_space(free, needed):
        report.error("not enough free disk space for the models: %s needed (plus %s to spare), %s free"
                     % (gigabytes(needed), gigabytes(DISK_MARGIN), gigabytes(free)))
        return
    for entry in todo:
        _download_one(entry, root, token, report)


def _download_one(entry, root, token, report):
    path = os.path.normpath(os.path.join(root, entry["file"]))
    if entry["note"]:
        print("NOTE: " + entry["note"] + ": " + entry["page"], file=report.out)
    print("downloading: %s (%s)" % (entry["name"], size_text(entry["size"])), file=report.out)
    try:
        download(entry, path, token, report.out)
    except DownloadError as e:
        report.error("%s: %s; %s" % (entry["name"], e, manual_hint(entry, root, token)))
        return
    report.add("downloaded: %s" % entry["file"])


# ---- config.local.ini

def config_text(checkpoint):
    return ("# This machine's AIGenerator settings (written by setup; not in git). The keys are those of config.ini;\n"
            "# see docs/installation.md.\n"
            "[models]\n"
            "checkpoint = %s\n" % checkpoint)


def ensure_config(root, report, environ=None):
    """Writes config.local.ini when it does not exist (never overwrites it) and warns when the checkpoint it
    resolves to is missing. Returns "written" or "kept"."""
    path = os.path.join(root, "config.local.ini")
    checkpoint = next(e["file"] for e in MODELS if e["key"] == "checkpoint")
    state = "kept"
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as f:
            f.write(config_text(checkpoint))
        state = "written"
        report.add("written: config.local.ini (checkpoint = %s)" % checkpoint)
    except FileExistsError:
        report.add("kept: config.local.ini (it already exists)")
    try:
        checkpoint = config.read(root, environ).checkpoint
    except contract.RequestError as e:
        report.error(str(e))
        return state
    if not checkpoint:
        report.add("WARNING: no checkpoint is configured: set [models] checkpoint in config.local.ini")
    elif not os.path.isfile(checkpoint):
        report.add("WARNING: the configured checkpoint is missing: %s (put the model there, or run setup without "
                   "--no-models to download Pony Diffusion V6 XL there)" % checkpoint)
    return state


# ---- the shortcut

def _desktop_quote(text):
    for c in ("\\", '"', "`", "$"):
        text = text.replace(c, "\\" + c)
    return '"%s"' % text.replace("%", "%%")


def desktop_entry(root, icon=None):
    """The freedesktop .desktop text (GNOME, KDE, ...): bin/open_web.sh in a terminal."""
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=AIGenerator\n"
            "Comment=%s\n"
            "Exec=%s\n"
            "Path=%s\n"
            "Icon=%s\n"
            "Terminal=true\n"
            "Categories=Graphics;\n"
            "StartupNotify=false\n"
            % (SHORTCUT_COMMENT, _desktop_quote(os.path.join(root, "bin", "open_web.sh")), root,
               icon or "applications-graphics"))


def desktop_path(environ=None):
    environ = os.environ if environ is None else environ
    data = environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(data, "applications", "aigenerator.desktop")


def current_icon(path):
    """The icon of an existing shortcut, kept when setup runs again without --icon."""
    try:
        with open(path, encoding="utf-8") as f:
            icons = [line[5:].strip() for line in f if line.startswith("Icon=")]
    except (OSError, UnicodeDecodeError):
        return None
    return icons[0] if icons and icons[0] else None


def linux_shortcut(root, icon, report, remove=False):
    path = desktop_path()
    if remove:
        if os.path.isfile(path):
            os.remove(path)
            report.add("removed: %s" % path)
        else:
            report.add("no shortcut to remove: %s" % path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    icon = icon or current_icon(path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(desktop_entry(root, icon))
    os.chmod(path, 0o755)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", os.path.dirname(path)], capture_output=True, check=False)
    report.add("shortcut: %s (\"AIGenerator\" in the application menu; right click > Pin to Dash for the dock)"
               % path)


# PowerShell, through WScript.Shell: AIGenerator.lnk on the Desktop and in the Start Menu, running open_web.bat in a
# console window (cmd /c). The paths come in environment variables, so no quoting of them is needed here. An existing
# shortcut is loaded and saved again: without --icon, its icon stays.
WINDOWS_SCRIPT = r"""$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $path = Join-Path $folder 'AIGenerator.lnk'
    if ($env:AIGEN_SHORTCUT_MODE -eq 'remove') {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path; Write-Output "removed: $path" }
        continue
    }
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $env:ComSpec
    $link.Arguments = '/c ""' + $env:AIGEN_SHORTCUT_TARGET + '""'
    $link.WorkingDirectory = $env:AIGEN_SHORTCUT_FOLDER
    $link.Description = $env:AIGEN_SHORTCUT_COMMENT
    if ($env:AIGEN_SHORTCUT_ICON) { $link.IconLocation = $env:AIGEN_SHORTCUT_ICON }
    $link.Save()
    Write-Output "shortcut: $path"
}
"""


def windows_shortcut_env(root, icon=None, remove=False, environ=None):
    env = dict(os.environ if environ is None else environ)
    env.update({"AIGEN_SHORTCUT_MODE": "remove" if remove else "create",
                "AIGEN_SHORTCUT_TARGET": os.path.join(root, "open_web.bat"),
                "AIGEN_SHORTCUT_FOLDER": root, "AIGEN_SHORTCUT_COMMENT": SHORTCUT_COMMENT,
                "AIGEN_SHORTCUT_ICON": icon or ""})
    return env


def powershell_command(script):
    """PowerShell's command line for a script: -EncodedCommand (UTF-16LE in base64) needs no quoting."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def windows_shortcut(root, icon, report, remove=False):
    try:
        r = subprocess.run(powershell_command(WINDOWS_SCRIPT), env=windows_shortcut_env(root, icon, remove),
                           capture_output=True, text=True, check=False)
    except OSError as e:
        report.error("the shortcut could not be made (PowerShell did not start: %s); open_web.bat does the same" % e)
        return
    for line in r.stdout.splitlines():
        if line.strip():
            report.add(line.strip())
    if r.returncode != 0:
        report.error("the shortcut could not be made: %s; open_web.bat does the same" % (r.stderr.strip()[-500:]))


def shortcut(root, icon, report, remove=False):
    (windows_shortcut if os.name == "nt" else linux_shortcut)(root, icon, report, remove)


# ---- the steps

def ensure_folders(root):
    for folder in FOLDERS:
        os.makedirs(os.path.join(root, folder), exist_ok=True)


TORCH_CHECK = ("import torch; ok = torch.cuda.is_available(); "
               "print('PyTorch %s, CUDA: %s' % (torch.__version__, torch.cuda.get_device_name(0) if ok else 'no'))")


def torch_check(report):
    """Asks the environment's PyTorch (in another process: this module imports nothing heavy) whether it sees the
    GPU. Only a warning when it does not."""
    try:
        r = subprocess.run([sys.executable, "-c", TORCH_CHECK], capture_output=True, text=True, timeout=300,
                           check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        report.add("WARNING: PyTorch could not be checked: %s" % e)
        return
    if r.returncode != 0:
        report.add("WARNING: PyTorch did not load in this Python (%s)" % sys.executable)
    elif r.stdout.strip().endswith("CUDA: no"):
        report.add("WARNING: %s: PyTorch does not see an NVIDIA GPU; generation would be very slow" % r.stdout.strip())
    else:
        report.add(r.stdout.strip())


def _finish(report):
    print()
    print("== Summary")
    for line in report.lines:
        print("  " + line)
    if report.failed:
        print("Setup finished with errors (above). Fix them and run %s again." % contract.command("setup"))
        return contract.GENERATION_FAILED
    where = ("on the Desktop and in the Start Menu" if os.name == "nt" else "in the application menu")
    print("Done. Open AIGenerator from the shortcut (\"AIGenerator\" %s): it opens the web interface in the browser."
          % where)
    return contract.OK


def main(argv=None, root=config.ROOT):
    try:
        return run(parse_args(sys.argv[1:] if argv is None else argv), root)
    except KeyboardInterrupt:
        print("\nERROR: interrupted; run %s again (an unfinished download is resumed)" % contract.command("setup"),
              file=sys.stderr)
        return contract.GENERATION_FAILED


def run(a, root):
    if a.icon and not os.path.isfile(a.icon):
        print("ERROR: icon not found: %s" % a.icon, file=sys.stderr)
        return contract.BAD_REQUEST
    icon = os.path.abspath(a.icon) if a.icon else None
    report = Report()
    if a.remove_shortcut:
        shortcut(root, None, report, remove=True)
        return contract.GENERATION_FAILED if report.failed else contract.OK
    try:
        cfg = config.read(root)
    except contract.RequestError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return contract.BAD_REQUEST
    ensure_folders(root)
    report.add("folders: %s" % ", ".join(FOLDERS))
    if a.no_models:
        report.add("skipped: the models (--no-models)")
    else:
        get_models(root, cfg, a.verify, report)
    ensure_config(root, report)
    torch_check(report)
    if a.no_shortcut:
        report.add("skipped: the shortcut (--no-shortcut)")
    else:
        shortcut(root, icon, report)
    return _finish(report)


if __name__ == "__main__":
    sys.exit(main())
