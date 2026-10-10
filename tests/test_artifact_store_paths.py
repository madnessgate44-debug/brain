"""Artifact-store path safety tests."""

import pytest

from brain.storage.artifact_store import ArtifactStore


@pytest.mark.parametrize("logical_name", ["", " ", ".", "..", "///"])
def test_artifact_store_rejects_empty_or_dot_only_names(tmp_path, logical_name):
    store = ArtifactStore(str(tmp_path / "workspace"))

    with pytest.raises(ValueError, match="Artifact logical name"):
        store.get_artifact_path("mission_test", logical_name)
