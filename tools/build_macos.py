"""Build a self-contained macOS app and ZIP using Python with Tk and PyInstaller."""
import argparse
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
APP_NAME = "CharacterWidget"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("arm64", "x86_64", "universal2"), default=platform.machine())
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Build the macOS app on a Mac.")

    app_source = REPO / "app"
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dist) as tmp:
        work = Path(tmp)
        icon = work / "icon.icns"
        subprocess.run(["/usr/bin/sips", "-s", "format", "icns", app_source / "icon.ico", "--out", icon], check=True)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
            "--name", APP_NAME, "--icon", str(icon), "--target-arch", args.arch,
            "--osx-bundle-identifier", "com.cute-office-apps.character-widget",
            "--specpath", str(work), "--workpath", str(work / "build"), "--distpath", str(work / "dist"),
        ]
        for resource in ("accessories", "ui", "settings.ini", "frames"):
            source = app_source / resource
            if source.exists():
                command.extend(("--add-data", f"{source}:{resource if source.is_dir() else '.'}"))
        subprocess.run([*command, str(app_source / "start_widget.pyw")], check=True)

        app = work / "dist" / f"{APP_NAME}.app"
        info = app / "Contents" / "Info.plist"
        metadata = plistlib.loads(info.read_bytes())
        metadata["CFBundleDisplayName"] = "캐릭터 위젯"
        metadata["CFBundleShortVersionString"] = (REPO / "version.txt").read_text().strip()
        info.write_bytes(plistlib.dumps(metadata))
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", app], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app], check=True)

        archive = work / "app.zip"
        subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, archive], check=True)
        output = dist / f"{APP_NAME}-macOS-{args.arch}.zip"
        archive.replace(output)
        print(output)


if __name__ == "__main__":
    main()
