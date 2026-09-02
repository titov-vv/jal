#!/usr/bin/env python
# Builds jal and publishes it to PyPI.
#
# The whole point of this script is that NOTHING is built from the working tree. Every artifact comes from a clean
# export of HEAD into a temporary directory, so an untracked file, a leftover build/ or a stale jal.egg-info can
# neither reach a release nor change what it contains - a stale SOURCES.txt once kept a tax template in the package
# that no packaging rule actually named, and the release before it would have shipped without the file.
#
# Run it from anywhere; it locates the repository from its own path:
#     python tools/release/publish.py            # build, verify, ask, upload to PyPI
#     python tools/release/publish.py --dry-run  # build and verify only, upload nothing
#     python tools/release/publish.py --test     # upload to TestPyPI instead
#
# Needs 'build' and 'twine' in the environment it runs with: pip install -r tools/release/requirements.txt
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

PYPI_URL = "https://upload.pypi.org/legacy/"
TESTPYPI_URL = "https://test.pypi.org/legacy/"
PYPI_JSON = "https://pypi.org/pypi/jal/json"

# Files that live under jal/ and are deliberately NOT part of a release: sources of generated modules, developer
# scripts and the ledger of whoever is doing the release. Everything else under jal/ that is not python code is
# data the application reads at run time and MUST be in the wheel - that is what verify_wheel_contents() checks.
EXCLUDED_FROM_PACKAGE = {
    '.ui': "Qt Designer sources - the compiled ui_*.py modules are what ships",
    '.ts': "translation sources - the compiled .qm files are what ships",
    '.pro': "Qt project file, used by the translation tooling only",
    '.sqlite': "a database file - never publish one"
}
EXCLUDED_NAMES = {'compile_ui', 'compile_translations', 'create_pro', 'run_designer'}

# A database must never leave this machine, whatever it is called or wherever it sits in the tree.
FORBIDDEN_SUFFIXES = ('.sqlite', '.sqlite3', '.db', '.ini')


class Failure(Exception):
    pass


def run(command: list, cwd: str = None, capture: bool = True) -> str:
    # capture=False lets the child talk to the terminal, which is what an interactive twine prompt needs
    result = subprocess.run(command, cwd=cwd, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    if result.returncode:
        output = f"\n{result.stdout}" if capture and result.stdout else ''
        raise Failure(f"Command failed ({result.returncode}): {' '.join(command)}{output}")
    return result.stdout.strip() if capture else ''


def step(number: int, total: int, title: str) -> None:
    print(f"\n[{number}/{total}] {title}", flush=True)


def repository_root() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not os.path.isdir(os.path.join(root, '.git')):
        raise Failure(f"{root} is not a git repository - this script must stay in tools/release/ of the jal repo")
    return root


def get_version(root: str) -> str:
    for line in open(os.path.join(root, 'jal', '__init__.py'), 'r', encoding='utf-8'):
        if line.startswith('__version__'):
            quote_char = '"' if '"' in line else "'"
            return line.split(quote_char)[1]
    raise Failure("No __version__ found in jal/__init__.py")


# Everything that must be true before a release is built. A dirty tree is refused rather than warned about: the
# build takes HEAD, so uncommitted work would be silently left out of a release that looks like it contains it.
def check_repository(root: str, version: str) -> dict:
    if run(['git', 'status', '--porcelain'], cwd=root):
        raise Failure("Working tree is not clean - commit or stash first (the release is built from HEAD)")
    state = {
        'branch': run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=root),
        'commit': run(['git', 'rev-parse', '--short', 'HEAD'], cwd=root)
    }
    print(f"  clean tree at {state['commit']} on {state['branch']}, version {version}")

    try:   # An unpushed release is not wrong, but it is worth knowing about before it is on PyPI forever
        upstream = run(['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], cwd=root)
        ahead = run(['git', 'rev-list', '--count', f'{upstream}..HEAD'], cwd=root)
        if ahead != '0':
            print(f"  WARNING: {ahead} commit(s) not pushed to {upstream}")
    except Failure:
        print("  WARNING: the current branch tracks no remote branch")

    if os.path.exists(os.path.join(root, 'jal', 'jal.sqlite')):
        print("  note: jal/jal.sqlite exists here and is excluded from the package by name")
    leftovers = [x for x in ('build', 'dist', 'jal.egg-info') if os.path.exists(os.path.join(root, x))]
    if leftovers:
        print(f"  note: {', '.join(leftovers)} left in the tree; they take no part in this build and can be deleted")
    return state


# PyPI refuses a version that is already there, and it refuses it AFTER the upload has been sent. Asking first turns
# that into a message before anything is built. A network failure here is not a reason to stop - the check is a
# courtesy, not a gate.
def check_version_is_new(version: str) -> None:
    try:
        with urllib.request.urlopen(PYPI_JSON, timeout=10) as response:
            released = json.load(response).get('releases', {})
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"  could not ask PyPI what is published ({error}) - continuing")
        return
    if version in released:
        raise Failure(f"Version {version} is already on PyPI - bump __version__ in jal/__init__.py")
    print(f"  {version} is not on PyPI yet (latest published: {max(released, default='none')})")


# A clean checkout of HEAD, made with 'git archive' so that only tracked content exists in it and the repository's
# own git state (worktrees, index) is not touched at all.
def export_head(root: str, target: str) -> str:
    checkout = os.path.join(target, 'checkout')
    os.makedirs(checkout)
    archive = os.path.join(target, 'HEAD.tar')
    run(['git', 'archive', '--format=tar', '-o', archive, 'HEAD'], cwd=root)
    with tarfile.open(archive) as tar:
        # 'data' filter is the safe extraction mode; it doesn't exist before python 3.12 and isn't needed there
        if hasattr(tarfile, 'data_filter'):
            tar.extractall(checkout, filter='data')
        else:
            tar.extractall(checkout)
    os.remove(archive)
    print(f"  exported {sum(len(files) for _, _, files in os.walk(checkout))} tracked files")
    return checkout


# 'python -m build' with no arguments makes the sdist first and then builds the wheel FROM THAT SDIST, in isolated
# environments. That order is the reason it is used as-is: a wheel built straight from the tree can succeed while
# the sdist that PyPI actually serves cannot be built from, which is a defect nobody sees until an install fails.
def build(checkout: str) -> tuple:
    # Output is captured rather than shown: a successful build says nothing worth reading, and a failed one is
    # quoted in full by run() - which is the only moment any of it matters.
    print("  building (this takes a minute)...", flush=True)
    run([sys.executable, '-m', 'build', checkout])
    dist = os.path.join(checkout, 'dist')
    sdists = glob.glob(os.path.join(dist, '*.tar.gz'))
    wheels = glob.glob(os.path.join(dist, '*.whl'))
    if len(sdists) != 1 or len(wheels) != 1:
        raise Failure(f"Expected one sdist and one wheel in {dist}, got {sdists + wheels}")
    for path in sdists + wheels:
        print(f"  {os.path.basename(path)} ({os.path.getsize(path) // 1024} KiB)")
    return sdists[0], wheels[0]


# Every non-python file under jal/ in the checkout, except the ones a release deliberately leaves out
def expected_data_files(checkout: str) -> set:
    expected = set()
    for root, dirs, files in os.walk(os.path.join(checkout, 'jal')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for name in files:
            if name.endswith(('.py', '.pyc')) or name in EXCLUDED_NAMES:
                continue
            if os.path.splitext(name)[1] in EXCLUDED_FROM_PACKAGE:
                continue
            expected.add(os.path.relpath(os.path.join(root, name), checkout))
    return expected


# The check this script exists for: what the application reads at run time has to be IN the wheel. A data file is
# added to the source tree far more often than package_data is looked at, and nothing else notices the difference -
# the tests run from the source tree, where every file is present whatever the packaging says.
def verify_wheel_contents(wheel: str, checkout: str) -> None:
    names = set(zipfile.ZipFile(wheel).namelist())
    missing = sorted(expected_data_files(checkout) - names)
    if missing:
        raise Failure("These data files are in the source tree but not in the wheel - name them in setup.py's "
                      "package_data (and in MANIFEST.in, which decides what the sdist carries):\n  "
                      + "\n  ".join(missing))
    shipped = sorted(n for n in names if not n.endswith('.py') and '.dist-info/' not in n)
    print(f"  every data file of the source tree is in the wheel ({len(shipped)} data files, "
          f"{len(names)} entries total)")


def verify_no_private_files(sdist: str, wheel: str) -> None:
    suspicious = [n for n in zipfile.ZipFile(wheel).namelist() if n.endswith(FORBIDDEN_SUFFIXES)]
    with tarfile.open(sdist) as tar:
        suspicious += [m.name for m in tar.getmembers() if m.isfile() and m.name.endswith(FORBIDDEN_SUFFIXES)]
    if suspicious:
        raise Failure("These files would be published and must not be:\n  " + "\n  ".join(sorted(suspicious)))
    print("  no database or configuration file is in either artifact")


# What PyPI itself will do to the metadata, before it is uploaded rather than after
def verify_metadata(sdist: str, wheel: str) -> None:
    run([sys.executable, '-m', 'twine', 'check', sdist, wheel], capture=False)


# Installs the wheel into a throwaway environment and reads the package back from there. It is the only check that
# proves the data files are reachable where the application will look for them, rather than merely present in a zip.
def smoke_test(wheel: str, workdir: str, version: str) -> None:
    venv = os.path.join(workdir, 'smoke')
    run([sys.executable, '-m', 'venv', venv])
    bin_dir = 'Scripts' if os.name == 'nt' else 'bin'
    python = os.path.join(venv, bin_dir, 'python.exe' if os.name == 'nt' else 'python')
    run([python, '-m', 'pip', 'install', '--quiet', '--no-deps', wheel])
    # cwd is the venv, never the checkout: a 'jal' directory in the working directory would shadow the installed
    # package and this check would pass while testing the source tree
    probe = ("import json, os, jal;"
             "site = os.path.dirname(jal.__file__);"
             "print(json.dumps({'version': jal.__version__, 'path': site,"
             " 'missing': [p for p in ['jal_init.sql', 'pypi_description.md', 'languages/ru.qm', 'img/flag_ru.png',"
             " 'data_export/tax_reports/russia.json', 'data_export/templates/ru_ndfl3/2025.json']"
             " if not os.path.exists(os.path.join(site, p))]}))")
    installed = json.loads(run([python, '-c', probe], cwd=venv))
    if installed['version'] != version:
        raise Failure(f"Installed version is {installed['version']}, expected {version}")
    if installed['missing']:
        raise Failure("Installed package cannot find: " + ", ".join(installed['missing']))
    executable = os.path.join(venv, bin_dir, 'jal.exe' if os.name == 'nt' else 'jal')
    if not os.path.exists(executable):
        raise Failure("The 'jal' console script was not created by the install")
    print(f"  installed {installed['version']} into a temporary environment, data files and 'jal' command present")


def confirm(question: str, expected: str) -> bool:
    print(f"\n{question}")
    return input(f"Type '{expected}' to continue, anything else to stop: ").strip() == expected


def upload(sdist: str, wheel: str, url: str) -> None:
    print("  twine will ask for credentials: the username is __token__ and the password is a PyPI API token")
    print("  (a ~/.pypirc or TWINE_USERNAME/TWINE_PASSWORD in the environment are used instead, if they exist)")
    run([sys.executable, '-m', 'twine', 'upload', '--repository-url', url, sdist, wheel], capture=False)


def require_tools() -> None:
    for module in ('build', 'twine'):
        try:
            run([sys.executable, '-m', module, '--version'])
        except Failure:
            raise Failure(f"'{module}' is not available for {sys.executable} - "
                          f"pip install -r tools/release/requirements.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build jal from a clean checkout of HEAD and publish it to PyPI.")
    parser.add_argument('--dry-run', action='store_true', help="build and verify, then stop without uploading")
    parser.add_argument('--test', action='store_true', help="upload to TestPyPI instead of PyPI")
    parser.add_argument('--keep', action='store_true', help="keep the temporary build directory for inspection")
    args = parser.parse_args()

    total = 8 if args.dry_run else 9
    workdir = None
    try:
        require_tools()
        root = repository_root()
        version = get_version(root)

        step(1, total, "Checking the repository state")
        state = check_repository(root, version)

        step(2, total, "Checking the version against PyPI")
        if args.test:
            print("  skipped for TestPyPI")
        else:
            check_version_is_new(version)

        workdir = tempfile.mkdtemp(prefix=f"jal-release-{version}-")
        step(3, total, f"Exporting HEAD to {workdir}")
        checkout = export_head(root, workdir)

        step(4, total, "Building the sdist, and the wheel from that sdist")
        sdist, wheel = build(checkout)

        step(5, total, "Verifying that the wheel carries every data file")
        verify_wheel_contents(wheel, checkout)

        step(6, total, "Verifying that nothing private is in the artifacts")
        verify_no_private_files(sdist, wheel)

        step(7, total, "Verifying the metadata as PyPI reads it")
        verify_metadata(sdist, wheel)

        step(8, total, "Installing the wheel into a temporary environment")
        smoke_test(wheel, workdir, version)

        if args.dry_run:
            print(f"\nDry run finished. jal {version} from {state['commit']} builds, verifies and installs.")
            return 0

        url = TESTPYPI_URL if args.test else PYPI_URL
        step(9, total, f"Uploading to {'TestPyPI' if args.test else 'PyPI'}")
        if not confirm(f"About to publish jal {version} ({state['commit']} on {state['branch']}) to {url}", version):
            print("Nothing was uploaded.")
            return 1
        upload(sdist, wheel, url)
        print(f"\nPublished jal {version}.")
        if not args.test:
            # Tags in this repository are the bare version, with no 'v' in front - see the tag list
            print(f"Tag the release if you haven't: git tag {version} && git push origin {version}")
        return 0
    except Failure as error:
        print(f"\nSTOPPED: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 1
    finally:
        if workdir and os.path.isdir(workdir):
            if args.keep:
                print(f"\nBuild directory kept at {workdir}")
            else:
                shutil.rmtree(workdir, ignore_errors=True)
                print("\nTemporary build directory removed - the repository was never written to.")


if __name__ == "__main__":
    sys.exit(main())
