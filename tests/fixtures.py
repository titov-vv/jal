import pytest
import os

@pytest.fixture
def project_root():
    return os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
