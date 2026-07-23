import shutil

import pytest

from avge_engine.services import engine


@pytest.fixture(autouse=True)
def isolate_engine_storage(tmp_path):
    """Keep tests from writing generated documents into the real .avge_data."""
    previous_dir = engine.STORAGE_DIR
    temp_storage = tmp_path / ".avge_data"
    engine.STORAGE_DIR = str(temp_storage)
    engine.reset_documents()
    try:
        yield
    finally:
        engine.reset_documents()
        shutil.rmtree(temp_storage, ignore_errors=True)
        engine.STORAGE_DIR = previous_dir
