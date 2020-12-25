# setup.py
from setuptools import setup, find_packages

setup(
    name="jal",
    version="2020.12.1",
    author_email="jal@gmx.ru",
    description="Just Another Ledger - project to track personal financial records",
    long_description="""Just Another Ledger is a project for personal finance tracking. 
    It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.""",
    packages=find_packages(),
    package_dir={'jal': 'jal'},
    python_requires=">=3.8.1",
    url="https://github.com/titov-vv/jal",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Office/Business",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python"
    ],
    install_requires=["lxml", "pandas", "PySide2>=5.15.0", "requests", "XlsxWriter"],
    entry_points={
        'console_scripts': ['jal=jal.jal:main', ]
    },
    include_package_data=True,
    package_data={
        '': ['*.sql', 'languages/*.qm', 'languages/*.png']
    }
)