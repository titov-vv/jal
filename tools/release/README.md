# Publishing a release

```bash
pip install -r tools/release/requirements.txt   # once
python tools/release/publish.py --dry-run       # build and verify, upload nothing
python tools/release/publish.py                 # the real thing
```

`publish.py` is the whole procedure: it refuses to start on a dirty tree, exports **HEAD** into a temporary
directory, builds there, verifies the artifacts, asks before uploading, and removes everything it made. The
repository is never written to - no `build/`, no `dist/`, no `jal.egg-info/` is left behind, and none of those is
read either.

| Option | What it does |
|---|---|
| `--dry-run` | stops after the checks; nothing is uploaded |
| `--test` | uploads to TestPyPI instead of PyPI |
| `--keep` | leaves the temporary directory in place so the artifacts can be looked at |

## Why a clean export and not the working tree

Whatever is in the tree ends up deciding what is in the package. A leftover `jal.egg-info/SOURCES.txt` lists files
from an earlier build and setuptools will happily reuse it, so a data file can be *in* a release only because of a
directory nobody meant to keep - and can silently vanish from the next one built elsewhere. That is not a
hypothetical: the Russian 3-NDFL template shipped that way until 2026-09, named by no packaging rule at all.

`git archive HEAD` gives a checkout that contains tracked content and nothing else, which is what the release is
built from. Untracked files cannot reach it, and uncommitted changes cannot either - which is why a dirty tree is
refused rather than warned about.

## What it checks

1. **The tree is clean**, and it says which commit and branch the release comes from. It warns if that commit is
   not pushed anywhere.
2. **The version is new** - `jal/__init__.py`'s `__version__` is not on PyPI already. PyPI rejects a repeat upload
   *after* receiving it; this asks first. Skipped for TestPyPI, and skipped if PyPI cannot be reached.
3. **The sdist can be built from, not just built.** `python -m build` makes the sdist and then builds the wheel
   **from that sdist**, which is how an sdist that is missing a file `setup.py` reads (`requirements.txt`, for one)
   is caught here instead of by the first person who installs it.
4. **Every data file of the source tree is in the wheel.** Everything under `jal/` that is not python code, minus
   the four kinds a release leaves out on purpose (`.ui` sources, `.ts` sources, `jal.pro`, any database). This is
   the check the whole script exists for: adding a data file is common, remembering `package_data` is not, and the
   tests never notice because they run from the source tree where every file is present regardless.
5. **Nothing private is in either artifact** - no `.sqlite`, `.db` or `.ini` anywhere in the sdist or the wheel.
6. **The metadata is what PyPI accepts** (`twine check`), including that the long description renders.
7. **The wheel installs and reads back.** It goes into a throwaway virtual environment; the installed package is
   imported from *there* (never from the source tree, which would shadow it), its version is compared with the one
   released, six data files are looked for on disk and the `jal` console script must exist.

Only then does it ask for confirmation - the version has to be typed - and hand over to `twine`, which asks for
credentials: username `__token__` and a PyPI API token as the password, unless `~/.pypirc` or
`TWINE_USERNAME`/`TWINE_PASSWORD` already answer for you.

## After a successful upload

The script prints the tag command; tagging is left to you:

```bash
git tag <version> && git push origin <version>
```

Tags here are the bare version (`2026.8.5`), with no `v` in front.

## Related

`tools/manual/` regenerates the manual's screenshots - a separate step, done before the release rather than by it,
because a screenshot belongs in a commit and not in a build.
