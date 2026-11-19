"""Standalone end-to-end verification script for Section 24 Definition of Done (John Doe 15-file workflow)."""

import os
import sys
import tempfile
from pathlib import Path

# Allow running directly from workspace root
API_DIR = Path(__file__).resolve().parents[2] / "apps" / "api"
sys.path.insert(0, str(API_DIR))


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'e2e_verify.db').as_posix()}"
        os.environ["STORAGE_BACKEND"] = "local_vault"
        os.environ["LOCAL_VAULT_PATH"] = (tmp_path / "vault").as_posix()
        os.environ["CELERY_ALWAYS_EAGER"] = "true"
        os.environ["AI_PROVIDER"] = "LOCAL_DETERMINISTIC"
        os.environ["ALLOW_EXTERNAL_AI"] = "false"

        from fastapi.testclient import TestClient
        from app.core.database import engine
        from app.main import app
        from tests.conftest import auth_headers
        from tests.test_e2e_john_doe import test_section_24_definition_of_done_john_doe_15_files

        try:
            with TestClient(app) as client:
                health = client.get("/health")
                assert health.status_code == 200, health.text
                _ = auth_headers(client, "officer@leaders.edu", "LeadersOfficer!2026")
                test_section_24_definition_of_done_john_doe_15_files(client)
                print("SUCCESS: Full Section 24 Definition of Done (John Doe 15-file workflow) passed.")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
