"""The repository's other projects keep their own workflows; this project's checks read only its own."""
from tests.workflows import PROJECT_FOLDER, project_workflows


def test_a_workflow_that_never_names_the_project_folder_is_not_the_projects(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    ours = [workflows / "gate.yml", workflows / "nightly.yaml"]
    for path in ours:
        path.write_text(f"defaults:\n  run:\n    working-directory: {PROJECT_FOLDER}\n")
    (workflows / "another-app.yml").write_text("env:\n  OCR_LANGUAGE: eng\n")
    assert project_workflows(tmp_path) == ours


def test_the_corpus_gate_and_the_fly_deploy_are_the_projects():
    assert {path.name for path in project_workflows()} >= {"corpus-gate.yml", "fly-deploy.yml"}
