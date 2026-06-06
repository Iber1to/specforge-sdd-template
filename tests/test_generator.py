from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def generate(self, profile: str, capabilities: str = "[]") -> Path:
        output = self.root / f"test-{profile}-project"
        config = self.root / f"{profile}.yaml"
        config.write_text(
            "\n".join(
                [
                    f"project_id: test-{profile}-project",
                    f"name: Test {profile.title()} Project",
                    f"output_path: {output}",
                    f"profile: {profile}",
                    f"capabilities: {capabilities}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        subprocess.run(
            [sys.executable, str(ROOT / "create_project.py"), "--config", str(config)],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

        return output

    def test_generates_generic_project(self) -> None:
        output = self.generate("generic")
        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))

        self.assertTrue((output / "scripts" / "project_status.py").is_file())
        self.assertTrue((output / "state" / "project.json").is_file())
        self.assertIn("documentation-pack", state["capabilities"])

    def test_generates_git_publish_capability_config(self) -> None:
        output = self.generate("generic", "[git-publish]")
        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))

        self.assertIn("documentation-pack", state["capabilities"])
        self.assertIn("git-publish", state["capabilities"])
        self.assertTrue(state["git_publication"]["enabled"])
        self.assertEqual("local", state["git_publication"]["mode"])

    def test_generates_pending_capability_policies(self) -> None:
        output = self.generate(
            "generic",
            "[external-runtime, performance-testing, security-scanning]",
        )
        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))

        self.assertIn("external-runtime", state["capabilities"])
        self.assertTrue((output / "state" / "capabilities" / "external-runtime.json").is_file())
        self.assertTrue(
            (output / "state" / "capabilities" / "performance-testing.json").is_file()
        )
        self.assertTrue((output / "state" / "capabilities" / "security-scanning.json").is_file())

    def test_generates_documentation_pack_structure(self) -> None:
        output = self.generate("generic")
        required_files = [
            "docs/README.md",
            "docs/00-project/overview.md",
            "docs/00-project/goals-and-scope.md",
            "docs/00-project/glossary.md",
            "docs/00-project/roadmap.md",
            "docs/10-architecture/system-context.md",
            "docs/10-architecture/architecture-overview.md",
            "docs/10-architecture/components.md",
            "docs/10-architecture/data-model.md",
            "docs/10-architecture/interfaces.md",
            "docs/10-architecture/deployment.md",
            "docs/10-architecture/adr/ADR-0001-template-baseline.md",
            "docs/20-runtime/local-development.md",
            "docs/20-runtime/configuration.md",
            "docs/20-runtime/external-runtimes.md",
            "docs/20-runtime/environment-matrix.md",
            "docs/30-quality/test-strategy.md",
            "docs/30-quality/quality-gates.md",
            "docs/30-quality/mutation-testing.md",
            "docs/30-quality/performance-testing.md",
            "docs/30-quality/security-scanning.md",
            "docs/40-operations/runbook.md",
            "docs/40-operations/troubleshooting.md",
            "docs/40-operations/backup-and-restore.md",
            "docs/40-operations/maintenance.md",
            "docs/50-releases/changelog.md",
            "docs/90-generated/.gitkeep",
            "state/capabilities/documentation-pack.json",
            "specs/schemas/documentation-policy.schema.json",
        ]

        for relative_path in required_files:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((output / relative_path).is_file())

    def test_refreshes_generated_documentation(self) -> None:
        output = self.generate("generic")

        subprocess.run(
            [sys.executable, "scripts/refresh_project_docs.py"],
            cwd=output,
            check=True,
            text=True,
            capture_output=True,
        )

        for relative_path in [
            "docs/90-generated/project-status.md",
            "docs/90-generated/feature-index.md",
            "docs/90-generated/quality-summary.md",
            "docs/90-generated/metrics-summary.md",
        ]:
            with self.subTest(relative_path=relative_path):
                path = output / relative_path
                self.assertTrue(path.is_file())
                self.assertIn("generated", path.read_text(encoding="utf-8").lower())

    def test_generates_windows_validation_documentation(self) -> None:
        output = self.generate("generic", "[windows-validation]")

        self.assertTrue((output / "docs" / "20-runtime" / "windows-runner.md").is_file())
        self.assertTrue((output / "docs" / "30-quality" / "windows-validation.md").is_file())

    def test_generates_python_project(self) -> None:
        output = self.generate("python", "[mutation-testing]")
        self.assertTrue((output / "pyproject.toml").is_file())
        self.assertTrue((output / "docs" / "20-runtime" / "python-environment.md").is_file())
        subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "scripts", "src", "tests"],
            cwd=output,
            check=True,
        )

    def test_generates_node_project(self) -> None:
        output = self.generate("node")
        self.assertTrue((output / "package.json").is_file())
        self.assertTrue((output / "docs" / "20-runtime" / "node-environment.md").is_file())
        subprocess.run(["npm", "test"], cwd=output, check=True, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
