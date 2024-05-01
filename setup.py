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


setup(
    name="jal",
    version=get_version("jal/__init__.py"),
    author_email="jal@gmx.ru",
    description="Just Another Ledger - project to track personal financial records",
    long_description_content_type='text/markdown',
    long_description=read('jal/pypi_description.md'),
    packages=find_packages(),
    package_dir={'jal': 'jal'},
    python_requires=">=3.8.1",
    url="https://github.com/titov-vv/jal",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Office/Business",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python"
    ],
    install_requires=["lxml", "pandas", "PySide6>=6.5.1", "requests>=2.24", "XlsxWriter>=1.3.3", "jsonschema", "sqlparse", "oauthlib", "requests-oauthlib", "setuptools"],
    entry_points={
        'console_scripts': ['jal=jal.jal:main', ]
    },
    include_package_data=True,
    package_data={
        '': ['*.sql', '*.json', 'languages/*.qm', 'languages/*.png', 'pypi_description.md', 'img/*.ico', 'img/*.png']
    }
)
