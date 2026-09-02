import os
from setuptools import setup, find_packages


def read(rel_path: str) -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, rel_path), 'r', encoding='utf-8') as fp:
        return fp.read()


def get_version(rel_path: str) -> str:
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            quote_char = '"' if '"' in line else "'"
            return line.split(quote_char)[1]
    raise RuntimeError("Unable to find version string.")


# Runtime dependencies are stated once, in requirements.txt.
def get_requirements(rel_path: str) -> list:
    lines = [line.strip() for line in read(rel_path).splitlines()]
    return [line for line in lines if line and not line.startswith('#')]


setup(
    name="jal",
    version=get_version("jal/__init__.py"),
    author_email="jal@gmx.ru",
    description="Just Another Ledger - project to track personal financial records",
    long_description_content_type='text/markdown',
    long_description=read('jal/pypi_description.md'),
    packages=find_packages(),
    package_dir={'jal': 'jal'},
    python_requires=">=3.9",
    url="https://github.com/titov-vv/jal",
    project_urls={
        "User manual": "https://titov-vv.github.io/jal/manual/",
        "Source": "https://github.com/titov-vv/jal",
        "Bug Tracker": "https://github.com/titov-vv/jal/issues",
        "Support": "https://t.me/jal_support"
    },
    license="GPL-3.0-or-later",
    license_files=["docs/LICENSE"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Office/Business",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Office/Business :: Financial :: Investment",
        "Intended Audience :: End Users/Desktop",
        "Environment :: X11 Applications :: Qt",
        "Natural Language :: English",
        "Natural Language :: Russian",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14"
    ],
    install_requires=get_requirements("requirements.txt"),
    entry_points={
        'console_scripts': ['jal=jal.jal:main', ]
    },
    include_package_data=True,
    package_data={
        # '*.json' reaches a package's own directory only, so the per-year 3-NDFL templates - which live in a plain
        # subdirectory of jal/data_export/templates - are named separately or they are left out of the package.
        '': ['*.sql', '*.json', 'data_export/templates/*/*.json', 'languages/*.qm', 'pypi_description.md',
             'img/*.ico', 'img/*.png']
    }
)
