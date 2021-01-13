#
# conftest.py
import sys
from os.path import dirname
from os.path import abspath, join
root_dir = dirname(dirname(abspath(__file__)))
root_dir = join(root_dir, 'jal')
sys.path.append(root_dir)