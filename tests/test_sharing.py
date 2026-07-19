import asyncio
import os

os.environ["HF_MODEL_NAME"] = "disabled"
os.environ["HF_TOKENIZER_NAME"] = "disabled"

from app.config import get_settings
from app.schemas import SharingRequest, ContentIntake
from app.services.orchestrator import AnalysisOrchestrator

get_settings.cache_clear()


def test_sharing_package_masks_actor_id(tmp_path, monkeypatch):
    # ensure sqlite writes to temp location
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    get_settings.cache_clear()

    orchestrator = AnalysisOrchestrator()
    intake = ContentIntake(
        text="Sample text with sufficient length to trigger detection features for testing purposes.",
        source="web",
    )
    result = orchestrator._process_sync(intake)

    request = SharingRequest(
        intake_id=result.intake_id,
        destination="USA",
        justification="Joint task force investigation",
        include_personal_data=False,
    )
    package = asyncio.run(orchestrator.build_sharing_package(request))
    metadata = package.payload.get("metadata")
    assert '"actor_id"' not in metadata
