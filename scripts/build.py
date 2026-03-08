import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def load_build_config() -> dict:
    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("aalc", {}).get("build", {})


def run_windows_build(version: str, config: dict) -> None:
    windows = config.get("windows", {})
    prune = windows.get("prune", {})

    dist_dir = ROOT / "dist"
    bundle_name = windows.get("main_bundle_dir", "AALC")
    updater_name = windows.get("updater_name", "AALC Updater.exe")

    shutil.rmtree(dist_dir, ignore_errors=True)

    for spec in (windows.get("main_spec", "main.spec"), windows.get("updater_spec", "updater.spec")):
        PyInstaller.__main__.run([str(ROOT / spec), "--noconfirm"])

    shutil.move(str(dist_dir / updater_name), str(dist_dir / bundle_name))

    bundle_dir = dist_dir / bundle_name
    shutil.copy(ROOT / "README.md", bundle_dir / "README.md")
    shutil.copy(ROOT / "LICENSE", bundle_dir / "LICENSE")
    shutil.copytree(ROOT / "assets", bundle_dir / "assets", dirs_exist_ok=True)

    i18n_out = bundle_dir / "i18n"
    i18n_out.mkdir(parents=True, exist_ok=True)
    for ts in (ROOT / "i18n").glob("*.ts"):
        qm = ts.with_suffix(".qm")
        subprocess.run(["pyside6-lrelease", str(ts), "-qm", str(qm)], check=True)
        shutil.move(str(qm), str(i18n_out / qm.name))

    version_file = bundle_dir / "assets" / "config" / "version.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(version, encoding="utf-8")

    internal_dir = bundle_dir / "_internal"
    for rel in prune.get("paths", []):
        target = internal_dir / rel
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.is_file():
            target.unlink()

    archive_format = windows.get("archive_format", "7z")
    if archive_format == "7z":
        archive_level = windows.get("archive_level", "-mx=7")
        archive_glob = windows.get("archive_glob", "AALC/*")
        archive_name = f"AALC_{version}.7z"
        subprocess.run(["7z", "a", archive_level, archive_name, archive_glob], cwd=dist_dir, check=True)


def run_linux_build(config: dict) -> None:
    linux = config.get("linux", {})
    formats = linux.get("formats", ["wheel", "sdist"])

    # Use uv build to avoid local module shadowing (e.g. ./build directory)
    # and keep PEP 517 compliant builds.
    cmd = ["uv", "build"]
    if "wheel" in formats:
        cmd.append("--wheel")
    if "sdist" in formats:
        cmd.append("--sdist")

    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    except FileNotFoundError:
        # Fallback for environments without uv.
        fallback_cmd = [sys.executable, "-m", "build"]
        if "wheel" in formats:
            fallback_cmd.append("--wheel")
        if "sdist" in formats:
            fallback_cmd.append("--sdist")
        subprocess.run(fallback_cmd, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AALC")
    parser.add_argument("--version", default="dev", help="AALC version")
    parser.add_argument(
        "--target",
        choices=("auto", "windows", "linux"),
        default="auto",
        help="Build target platform",
    )
    args = parser.parse_args()

    config = load_build_config()

    target = args.target
    if target == "auto":
        target = "windows" if sys.platform == "win32" else "linux"

    if target == "windows":
        if sys.platform != "win32":
            raise SystemExit("Windows target requires running on Windows")
        run_windows_build(args.version, config)
    else:
        run_linux_build(config)


if __name__ == "__main__":
    main()
