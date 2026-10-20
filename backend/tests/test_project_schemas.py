from aura.schemas import ProjectOut, ProjectUpdate


def test_project_dataset_binding_schema() -> None:
    update = ProjectUpdate(ragflow_dataset_ids=["ds-1", "ds-2"])
    assert update.ragflow_dataset_ids == ["ds-1", "ds-2"]
    assert "ragflow_dataset_ids" in ProjectOut.model_fields
