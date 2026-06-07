from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLACKLISTED_CORE_PATTERNS = {
    "desktop-overlay-assistant",
    "Desktop Overlay Assistant",
    "/srv/data/desktop-overlay-assistant",
    "runtime/windows-runner",
    "F-001-cli-health-check",
}
IGNORED_NEUTRALITY_PARTS = {
    ".git",
    ".venv",
    ".ruff_cache",
    "__pycache__",
}


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

    def run_generator_with_config(self, config_text: str) -> subprocess.CompletedProcess[str]:
        config = self.root / "invalid.yaml"
        config.write_text(config_text, encoding="utf-8")

        return subprocess.run(
            [sys.executable, str(ROOT / "create_project.py"), "--config", str(config)],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def assert_command(
        self,
        cwd: Path,
        *command: str,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )

        if result.returncode != 0:
            debug_output = self.collect_artifact_debug_output(cwd)
            self.fail(
                "Command failed in "
                f"{cwd}: {' '.join(command)}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}\n"
                f"{debug_output}"
            )

        return result

    def collect_artifact_debug_output(self, cwd: Path) -> str:
        state_path = cwd / "state" / "project.json"

        if not state_path.is_file():
            return ""

        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""

        artifact_root = Path(state.get("artifact_root", ""))

        if not artifact_root.is_dir():
            return ""

        logs = sorted(
            artifact_root.rglob("*.log"),
            key=lambda path: path.stat().st_mtime,
        )[-5:]

        if not logs:
            return ""

        chunks = ["\nRecent artifact logs:"]

        for log in logs:
            content = log.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"\n--- {log} ---\n{content[-4000:]}")

        return "\n".join(chunks)

    def harness_python(
        self,
        cwd: Path,
        script: str,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        shell_command = (
            'export PATH="$HOME/.local/bin:$PATH"; '
            + "uv run python "
            + shlex.join([script, *arguments])
        )

        return self.assert_command(cwd, "bash", "-lc", shell_command)

    def test_core_is_neutral_except_examples_and_capabilities(self) -> None:
        violations: list[str] = []
        for path in (ROOT / "core").rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in IGNORED_NEUTRALITY_PARTS for part in relative.parts):
                continue
            if relative.parts[:1] in {("examples",), ("capabilities",)}:
                continue
            if path.suffix in {".pyc", ".lock"}:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in BLACKLISTED_CORE_PATTERNS:
                if pattern in content or pattern in str(relative):
                    violations.append(f"{relative}: {pattern}")

        self.assertEqual([], violations)

    def test_rejects_invalid_project_id(self) -> None:
        result = self.run_generator_with_config(
            "\n".join(
                [
                    "project_id: Bad_Project",
                    "name: Bad Project",
                    f"output_path: {self.root / 'bad-project'}",
                    "profile: generic",
                    "capabilities: []",
                ]
            )
            + "\n"
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("project_id", result.stderr)

    def test_rejects_incompatible_profile_capability(self) -> None:
        result = self.run_generator_with_config(
            "\n".join(
                [
                    "project_id: node-mutation-project",
                    "name: Node Mutation Project",
                    f"output_path: {self.root / 'node-mutation-project'}",
                    "profile: node",
                    "capabilities: [mutation-testing]",
                ]
            )
            + "\n"
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("mutation-testing", result.stderr)

    def test_supports_configurable_operational_roots(self) -> None:
        output = self.root / "custom-roots-project"
        data_root = self.root / "custom-data-root"
        worktree_root = self.root / "custom-worktree-root"
        config = self.root / "custom-roots.yaml"
        config.write_text(
            "\n".join(
                [
                    "project_id: custom-roots-project",
                    "name: Custom Roots Project",
                    f"output_path: {output}",
                    "profile: generic",
                    "capabilities: []",
                    f"data_root: {data_root}",
                    f"worktree_root: {worktree_root}",
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

        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(str(data_root.resolve()), state["data_root"])
        self.assertEqual(str(worktree_root.resolve()), state["worktree_root"])
        self.assertEqual(str(data_root.resolve() / "control"), state["control_root"])
        self.assertEqual(str(data_root.resolve() / "artifacts"), state["artifact_root"])

    def test_generates_generic_project(self) -> None:
        output = self.generate("generic")
        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))

        self.assertTrue((output / "scripts" / "project_status.py").is_file())
        self.assertTrue((output / "state" / "project.json").is_file())
        self.assertTrue((output / "CLAUDE.md").is_file())
        self.assertTrue((output / "specs" / "CLAUDE.md").is_file())
        self.assertIn("documentation-pack", state["capabilities"])
        self.assertFalse((output / "specs" / "features" / "F-001-cli-health-check").exists())

    def write_lifecycle_feature_documents(self, output: Path) -> Path:
        feature_root = output / "specs" / "features" / "F-001-deterministic-lifecycle"
        feature_root.mkdir(parents=True)

        (feature_root / "specification.md").write_text(
            textwrap.dedent(
                """
                # Deterministic Lifecycle

                ## Problem

                Generated projects need a deterministic proof that the harness can
                move one real feature from registration to finalization.

                ## Goal

                Exercise the generated harness lifecycle without Claude Code, network
                access or external services.

                ## Scope

                The feature updates stable project documentation and validates the
                lifecycle scripts, quality gates and finalization path.

                ## Out of Scope

                This fixture does not add product runtime behavior, external runtimes
                or optional capabilities.

                ## User Scenarios

                A template maintainer generates a project and verifies that one feature
                can reach DONE using deterministic fixtures.

                ## Functional Requirements

                The lifecycle must register, validate, implement, review and finalize a
                feature with clean control-plane state.

                ## Non-Functional Requirements

                The run must be reproducible in a temporary directory and must not
                require network access after dependency sync.

                ## Assumptions

                The generated project has the default documentation pack and quality
                gates enabled.

                ## Acceptance Summary

                AC-001 verifies the final DONE state. AC-002 verifies there are no
                stale leases or orphaned worktrees.

                ## Open Questions

                There are no blocking open questions for this deterministic fixture.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (feature_root / "acceptance.yaml").write_text(
            textwrap.dedent(
                """
                schema_version: 2
                feature_id: F-001
                title: Deterministic Lifecycle
                specification:
                  mode: autonomous_with_critical_escalation
                  assumptions:
                    - id: ASM-001
                      statement: The generated project starts from an empty feature queue.
                      rationale: The generator initializes a new repository and control root.
                      risk: low
                  decisions:
                    - id: DEC-001
                      question: How should the end-to-end fixture prove implementation?
                      decision: Update stable project documentation in the feature branch.
                      rationale: Documentation changes are safe for the generic profile and still produce a real commit.
                  open_questions:
                    - id: Q-001
                      question: Are any external services required for this fixture?
                      blocking: false
                      impact: No external service is required for the deterministic run.
                documentation:
                  requires_adr: false
                  requires_runtime_update: false
                  requires_operations_update: false
                  requires_quality_update: false
                scenarios:
                  - id: SCN-001
                    title: Complete deterministic lifecycle
                    given:
                      - A generated generic project exists.
                      - The feature specification is valid.
                    when:
                      - The lifecycle scripts are executed in order.
                    then:
                      - The feature reaches DONE.
                      - The control plane has no stale lease for the feature.
                    criteria:
                      - AC-001
                      - AC-002
                criteria:
                  - id: AC-001
                    statement: The generated project can finalize F-001 into DONE using deterministic scripts.
                    category: lifecycle
                    verification: automated_e2e
                    required: true
                  - id: AC-002
                    statement: Finalization removes active leases and the feature worktree.
                    category: lifecycle
                    verification: automated_e2e
                    required: true
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (feature_root / "semantic-review.md").write_text(
            "# Semantic Review\n\nNo contradictions, ambiguous scope or blocking questions found.\n",
            encoding="utf-8",
        )

        (feature_root / "architecture.md").write_text(
            textwrap.dedent(
                """
                # Deterministic Lifecycle Architecture

                ## Specification Review

                The specification is coherent, all acceptance criteria are
                verifiable, and no external dependencies are required.

                ## Context

                The generated project contains the harness scripts, control-plane
                state and documentation pack needed by the lifecycle.

                ## Decision

                Use the existing lifecycle scripts end to end and make a small
                documentation commit as the implementation.

                ## Components

                `scripts/register_feature.py`, `transition_feature.py`,
                `start_implementation.py`, `complete_implementation.py`,
                `start_review.py`, `complete_review.py` and `finalize_feature.py`
                participate in the flow.

                ## Interfaces

                The fixture uses command-line scripts and JSON/YAML files already
                defined by the harness contract.

                ## Data Flow

                The queue advances through external control state while Git commits
                carry the feature specification, implementation evidence and review
                evidence.

                ## Data Model

                No product data model changes are introduced. The existing feature,
                run, lease and evidence documents are used.

                ## Performance Considerations

                The fixture runs only default quality gates and stays within normal
                unit-test time budgets.

                ## Failure Modes

                A failed quality gate, stale lease or dirty worktree blocks the next
                lifecycle transition.

                ## Windows Runtime Impact

                No Windows runtime behavior is changed or required.

                ## Open Questions

                There are no open architecture questions.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (feature_root / "implementation-plan.md").write_text(
            textwrap.dedent(
                """
                # Deterministic Lifecycle Implementation Plan

                ## Strategy

                Update stable project documentation in the isolated feature worktree
                and let the harness create implementation evidence.

                ## Work Breakdown

                Register the feature, validate specification and design, create the
                worktree, commit the documentation change, complete QA and finalize.

                ## Files Expected to Change

                `docs/00-project/roadmap.md` changes in the implementation branch.

                ## Dependencies

                The fixture depends only on Git, Python, uv and the generated harness.

                ## Risks

                A broken quality gate or stale worktree can block the deterministic
                run.

                ## Rollback

                The temporary generated project directory can be deleted after the
                test finishes.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (feature_root / "test-plan.md").write_text(
            textwrap.dedent(
                """
                # Deterministic Lifecycle Test Plan

                ## Test Strategy

                Execute the generated harness scripts in their real order against a
                temporary project.

                ## Acceptance Traceability

                AC-001 is verified by reading the final queue state. AC-002 is
                verified by inspecting leases and the expected worktree path.

                ## Unit Tests

                Existing harness unit tests run through the configured quality gates.

                ## Integration Tests

                The lifecycle script sequence is the integration test.

                ## Windows E2E Tests

                No Windows E2E tests are required for this feature.

                ## Performance Tests

                No performance tests are required for this feature.

                ## Exit Criteria

                The feature reaches DONE, the repository is clean, and no lease or
                feature worktree remains.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        return feature_root

    def test_generated_generic_project_reaches_done_e2e(self) -> None:
        output = self.generate("generic")
        feature_root = self.write_lifecycle_feature_documents(output)

        self.harness_python(
            output,
            "scripts/register_feature.py",
            "--title",
            "Deterministic Lifecycle",
            "--slug",
            "deterministic-lifecycle",
            "--description",
            "Deterministic generated-project lifecycle fixture.",
            "--requested-by",
            "template-test",
        )
        self.harness_python(output, "scripts/validate_spec.py", "--feature", "F-001")
        self.harness_python(output, "scripts/validate_design.py", "--feature", "F-001")

        self.assert_command(output, "git", "add", str(feature_root.relative_to(output)))
        self.assert_command(
            output,
            "git",
            "commit",
            "-m",
            "test(F-001): add deterministic lifecycle spec",
        )

        self.harness_python(
            output,
            "scripts/transition_feature.py",
            "--feature",
            "F-001",
            "--to",
            "SPEC_READY",
            "--role",
            "specifier",
            "--reason",
            "Spec fixture validated",
        )
        self.harness_python(
            output,
            "scripts/transition_feature.py",
            "--feature",
            "F-001",
            "--to",
            "DESIGN_READY",
            "--role",
            "architect",
            "--reason",
            "Architecture fixture validated",
        )
        self.harness_python(
            output,
            "scripts/transition_feature.py",
            "--feature",
            "F-001",
            "--to",
            "READY_FOR_DEVELOPMENT",
            "--role",
            "architect",
            "--reason",
            "Implementation and test plans validated",
        )

        self.harness_python(
            output,
            "scripts/start_implementation.py",
            "--feature",
            "F-001",
            "--agent-id",
            "implementer-e2e",
        )

        state = json.loads((output / "state" / "project.json").read_text(encoding="utf-8"))
        worktree = Path(state["worktree_root"]) / "F-001-deterministic-lifecycle"
        roadmap = worktree / "docs" / "00-project" / "roadmap.md"
        roadmap.write_text(
            roadmap.read_text(encoding="utf-8")
            + "\n## Deterministic Lifecycle\n\nValidated by the generated-project E2E fixture.\n",
            encoding="utf-8",
        )
        self.assert_command(worktree, "git", "add", "docs/00-project/roadmap.md")
        self.assert_command(
            worktree,
            "git",
            "commit",
            "-m",
            "docs(F-001): record deterministic lifecycle marker",
        )

        self.harness_python(
            worktree,
            "scripts/complete_implementation.py",
            "--feature",
            "F-001",
            "--agent-id",
            "implementer-e2e",
        )
        self.harness_python(
            output,
            "scripts/start_review.py",
            "--feature",
            "F-001",
            "--agent-id",
            "qa-e2e",
        )
        self.harness_python(
            worktree,
            "scripts/complete_review.py",
            "--feature",
            "F-001",
            "--agent-id",
            "qa-e2e",
            "--verdict",
            "APPROVED",
            "--summary",
            "Deterministic lifecycle fixture approved after full gates.",
        )
        self.harness_python(
            output,
            "scripts/finalize_feature.py",
            "--feature",
            "F-001",
            "--reason",
            "Deterministic generated-project lifecycle completed.",
        )

        queue = json.loads((Path(state["control_root"]) / "queue.json").read_text(encoding="utf-8"))
        runtime = json.loads((Path(state["control_root"]) / "runtime.json").read_text(encoding="utf-8"))
        feature = next(item for item in queue["features"] if item["id"] == "F-001")

        self.assertEqual("DONE", feature["state"])
        self.assertEqual([], runtime.get("active_runs", []))
        self.assertFalse((Path(state["control_root"]) / "leases" / "F-001.json").exists())
        self.assertFalse(worktree.exists())
        self.assertEqual("", self.assert_command(output, "git", "status", "--porcelain").stdout)

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
        package = json.loads((output / "package.json").read_text(encoding="utf-8"))
        self.assertNotIn("devDependencies", package)
        self.assertEqual(
            {
                "test": "node --test",
                "lint": "node --check src/index.js tests/index.test.js",
            },
            package["scripts"],
        )
        subprocess.run(["npm", "test"], cwd=output, check=True, text=True, capture_output=True)

    def test_project_id_pattern_documents_slug_contract(self) -> None:
        self.assertIsNotNone(re.fullmatch(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "valid-id"))
        self.assertIsNone(re.fullmatch(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "Invalid_Id"))


if __name__ == "__main__":
    unittest.main()
