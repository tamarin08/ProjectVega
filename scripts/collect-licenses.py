"""Collect installed and version-matched upstream notices into the release folder.

Build-time network access only; downloaded notices are cached under build/.
No downloads, license checks or network requests occur in the application.
"""

import concurrent.futures
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str, cache: Path) -> bytes:
    if cache.is_file():
        return cache.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "ProjectVega-release-build"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


def collect(destination: Path, *, app: str = "Vega") -> None:
    notices = destination / "licenses"
    notices.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "packaging/licenses/Windows-MIDI-Services.txt", notices / "Windows-MIDI-Services.txt")
    cache = ROOT / "build" / "license-cache"
    manifest = [{"upstream": "microsoft/MIDI", "tag": "inbox-preview-11",
                 "source": "https://github.com/microsoft/MIDI/tree/inbox-preview-11",
                 "use": "System COM interface definitions and JSON contract; no Microsoft API binary is bundled"}]
    packages = ["mido", "packaging", "pygame", "PySide6_Essentials", "shiboken6", "pyinstaller", "setuptools"]
    try:
        importlib.metadata.distribution("python-rtmidi")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        packages.append("python-rtmidi")
    for name in packages:
        package = importlib.metadata.distribution(name)
        for item in package.files or ():
            if any(word in item.name.lower() for word in ("license", "copying", "copyright", "notice")):
                source = Path(package.locate_file(item))
                if source.is_file():
                    target = notices / name / Path(str(item))
                    # RECORD entries can contain ../scripts: never let them escape.
                    if not target.resolve().is_relative_to(notices.resolve()):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        manifest.append({"package": name, "version": package.version})
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", notices / "Python-LICENSE.txt")
    jobs = []
    qt_version = importlib.metadata.version("PySide6_Essentials")
    repositories = (("pygame/pygame", "2.6.1"), ("qt/qtbase", f"v{qt_version}"),
                    ("qt/qtsvg", f"v{qt_version}"), ("qt/qtimageformats", f"v{qt_version}"),
                    ("pyside/pyside-setup", f"v{qt_version}"))
    for repo, tag in repositories:
        tree_url = f"https://api.github.com/repos/{repo}/git/trees/{tag}?recursive=1"
        tree = json.loads(fetch(tree_url, cache / repo / tag / "tree.json"))
        if tree.get("truncated"):
            raise RuntimeError(f"Incomplete upstream license inventory: {repo}")
        for entry in tree["tree"]:
            path = entry["path"]
            filename = Path(path).name.lower()
            if entry["type"] != "blob":
                continue
            if (path.startswith(("LICENSES/", "docs/licenses/")) or
                    ("3rdparty/" in path and (filename.startswith(("license", "copying", "copyright", "notice"))
                                             or filename == "qt_attribution.json"))):
                url = f"https://raw.githubusercontent.com/{repo}/{tag}/{path}"
                jobs.append((url, cache / repo / tag / path, notices / repo / tag / path))
        manifest.append({"upstream": repo, "tag": tag, "source": f"https://github.com/{repo}/tree/{tag}"})

    def copy_notice(job):
        url, cached, target = job
        data = fetch(url, cached)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(copy_notice, jobs))
    (notices / "SOURCES.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / name, destination / name)
    (destination / "docs").mkdir(exist_ok=True)
    if app == "Edmond":
        shutil.copyfile(ROOT / "docs" / "EDMOND.md",destination / "README.md")
        documents = ("EDMOND_VERIFICATION.md", "FINAL_RELEASE.md")
    else:
        shutil.copyfile(ROOT / "README.md",destination / "README.md")
        shutil.copyfile(ROOT / "ARCHITECTURE.md",destination / "ARCHITECTURE.md")
        documents = ("RELEASE_INTEGRATION.md", "CLEAN_WINDOWS_TEST.md", "VEGA.md", "FINAL_RELEASE.md")
    for name in documents:
        shutil.copyfile(ROOT / "docs" / name, destination / "docs" / name)
    print(f"Collected {len(jobs)} upstream notices plus installed dependency licenses into {notices}")


if __name__ == "__main__":
    collect(ROOT / "dist" / "Vega")
