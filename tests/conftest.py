import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def project(tmp_path):
    """Cópia mínima do projeto (config + templates) numa pasta temporária."""
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "content" / "articles").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    return tmp_path


@pytest.fixture
def fixtures():
    return FIXTURES
