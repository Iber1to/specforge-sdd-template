#!/usr/bin/env python3
"""Role Guard determinista para Claude Code.

Lee eventos JSON desde stdin y bloquea llamadas de herramientas que no respetan
el rol activo, la propiedad de archivos o el worktree asignado.

Los bloqueos se realizan mediante exit code 2, que Claude Code interpreta como
denegación de PreToolUse incluso en bypassPermissions.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN_ROLES = {
    "leader",
    "specifier",
    "architect",
    "implementer",
    "qa-reviewer",
    "mutation-reviewer",
    "repository-publisher",
}

SPECIALIZED_AGENTS = {
    "specifier",
    "architect",
    "implementer",
    "qa-reviewer",
    "mutation-reviewer",
    "repository-publisher",
}

MUTATING_TOOLS = {
    "Write",
    "Edit",
    "Bash",
    "Agent",
    "NotebookEdit",
    "PowerShell",
    "Workflow",
    "TeamCreate",
    "TeamDelete",
    "SendMessage",
    "EnterWorktree",
    "ExitWorktree",
}

ALWAYS_DENIED_TOOLS = {
    "NotebookEdit",
    "PowerShell",
    "Workflow",
    "TeamCreate",
    "TeamDelete",
    "SendMessage",
    "EnterWorktree",
    "ExitWorktree",
}

LEADER_HARNESS_SCRIPTS = {
    "project_status.py",
    "metrics_status.py",
    "refresh_feature_metrics.py",
    "transition_lifecycle.py",
    "recover_stale_leases.py",
    "register_feature.py",
    "validate_spec.py",
    "validate_design.py",
    "transition_feature.py",
    "start_implementation.py",
    "start_review.py",
    "finalize_feature.py",
    "publish_feature.py",
    "collect_windows_evidence.py",
    "run_external_runtime.py",
    "run_performance_gate.py",
    "run_security_scan.py",
    "validate_external_runtime_result.py",
    "validate_performance_result.py",
    "validate_security_result.py",
    "generate_docs_index.py",
    "refresh_project_docs.py",
    "refresh_feature_index.py",
    "refresh_quality_summary.py",
    "refresh_metrics_summary.py",
}

IMPLEMENTER_HARNESS_SCRIPTS = {
    "heartbeat_lease.py",
    "complete_implementation.py",
}

QA_HARNESS_SCRIPTS = {
    "heartbeat_lease.py",
    "complete_review.py",
}

PUBLISHER_HARNESS_SCRIPTS = {
    "project_status.py",
    "publish_feature.py",
}

READ_ONLY_COMMAND_PREFIXES = (
    "pwd",
    "ls",
    "tree",
    "cat ",
    "head ",
    "tail ",
    "wc ",
    "grep ",
    "rg ",
    "find ",
    "sed -n ",
    "jq ",
    "git status",
    "git diff",
    "git log",
    "git show",
    "git rev-parse",
    "git branch --show-current",
    "git worktree list",
    "uv run pytest",
    "uv run ruff",
    "uv run python -m pytest",
    "uv run python -m compileall",
    "pytest",
    "ruff",
    "./scripts/verify_fast.sh",
    "./scripts/verify_full.sh",
    "bash scripts/verify_fast.sh",
    "bash scripts/verify_full.sh",
)

FORBIDDEN_COMMAND_PATTERNS = (
    r"(^|[;&|]\s*)sudo(\s|$)",
    r"(^|[;&|]\s*)su(\s|$)",
    r"\brm\s+-[^ \n]*r[^ \n]*f\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-",
    r"\bgit\s+push\b",
    r"\bgit\s+rebase\b",
    r"\bgit\s+merge\b",
    r"\bgit\s+checkout\b",
    r"\bgit\s+switch\b",
    r"\bgit\s+worktree\b",
    r"\bgit\s+branch\s+-(?:D|d|m|M)\b",
    r"\b(?:mkfs|fdisk|parted|lvcreate|lvremove|lvextend|mount|umount|dd)\b",
    r"\bcurl\b[^|\n]*\|\s*(?:ba)?sh\b",
    r"\bwget\b[^|\n]*\|\s*(?:ba)?sh\b",
    r"<<[-~]?\s*['\"]?\w+",
    r"\btee\b",
    r"\bsed\s+-i\b",
    r"\bperl\s+-i\b",
    r"\bpython(?:3)?\s+-c\b",
    r"\buv\s+run\s+python\s+-c\b",
    r"(?:^|[\s\"'])\.\./",
)

SHELL_CHAIN_TOKENS = {"&&", "||", ";", "|"}

CHANGE_DOMAINS = {"product", "harness", "template"}
HARNESS_IMPLEMENTER_ROOTS = {
    ".claude",
    "docs",
    "scripts",
    "specs",
    "state",
    "tests",
}
HARNESS_IMPLEMENTER_FILES = {
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("pyproject.toml"),
    Path("uv.lock"),
}


CONTROL_ROOT_DEFAULT = Path(".agentic/control")


class GuardError(RuntimeError):
    """Error controlado del Role Guard."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_event() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise GuardError(f"Entrada JSON inválida: {exc}") from exc

    if not isinstance(data, dict):
        raise GuardError("La entrada del hook debe ser un objeto JSON")

    return data


def project_root() -> Path:
    value = os.environ.get("CLAUDE_PROJECT_DIR")

    if value:
        return Path(value).expanduser().resolve()

    return Path.cwd().resolve()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GuardError(f"No existe el archivo requerido: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GuardError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise GuardError(f"{path} debe contener un objeto JSON")

    return data


def project_config(root: Path) -> dict[str, Any]:
    return load_json(root / "state" / "project.json")


def control_root(root: Path) -> Path:
    try:
        configured = project_config(root).get("control_root")
    except GuardError:
        configured = None

    if configured:
        return Path(str(configured)).expanduser().resolve()

    # Fallback solo usado si falta control_root en project.json. Se mantiene
    # dentro del repositorio (no en /tmp, world-writable y predecible).
    return (root / CONTROL_ROOT_DEFAULT).resolve()


def role_sessions_root(root: Path) -> Path:
    return control_root(root) / "role-sessions"


def audit_log_path(root: Path) -> Path:
    return control_root(root) / "role-guard" / "audit.jsonl"


def append_audit(root: Path, payload: dict[str, Any]) -> None:
    path = audit_log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": now_utc(),
        **payload,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def session_role_path(root: Path, session_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)
    return role_sessions_root(root) / f"{safe_id}.json"


def register_session(root: Path, event: dict[str, Any]) -> int:
    session_id = str(event.get("session_id", "")).strip()

    if not session_id:
        return 0

    path = session_role_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = load_json(path)
        except GuardError:
            existing = {}

    supplied_role = event.get("agent_type")
    env_role = os.environ.get("CLAUDE_HARNESS_ROLE", "").strip()

    if supplied_role in KNOWN_ROLES:
        role = supplied_role
    elif supplied_role in (None, "claude") and env_role in KNOWN_ROLES:
        # La sesion principal (claude --agent leader) llega como agent_type "claude";
        # el rol se toma de CLAUDE_HARNESS_ROLE, fijado por el operador al lanzar.
        role = env_role
    else:
        role = existing.get("role", "unscoped")

    payload = {
        "session_id": session_id,
        "role": role,
        "agent_type": supplied_role,
        "source": event.get("source"),
        "project_root": str(root),
        "updated_at": now_utc(),
    }

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    append_audit(root, {"action": "SESSION_REGISTERED", **payload})

    return 0


def resolve_role(root: Path, event: dict[str, Any]) -> str:
    direct = event.get("agent_type")

    if direct in KNOWN_ROLES:
        return str(direct)

    session_id = str(event.get("session_id", "")).strip()

    if session_id:
        path = session_role_path(root, session_id)

        if path.exists():
            try:
                role = load_json(path).get("role")
            except GuardError:
                role = None

            if role in KNOWN_ROLES:
                return str(role)

    return "unscoped"


def deny(root: Path, event: dict[str, Any], role: str, reason: str) -> int:
    append_audit(
        root,
        {
            "action": "DENIED",
            "role": role,
            "session_id": event.get("session_id"),
            "agent_id": event.get("agent_id"),
            "agent_type": event.get("agent_type"),
            "tool_name": event.get("tool_name"),
            "cwd": event.get("cwd"),
            "reason": reason,
            "tool_input": event.get("tool_input"),
        },
    )
    print(f"Role Guard bloqueó la operación: {reason}", file=sys.stderr)
    return 2


def allow(root: Path, event: dict[str, Any], role: str) -> int:
    append_audit(
        root,
        {
            "action": "ALLOWED",
            "role": role,
            "session_id": event.get("session_id"),
            "agent_id": event.get("agent_id"),
            "agent_type": event.get("agent_type"),
            "tool_name": event.get("tool_name"),
            "cwd": event.get("cwd"),
        },
    )
    return 0


def resolve_input_path(event: dict[str, Any], key: str) -> Path:
    raw = event.get("tool_input", {}).get(key)

    if not isinstance(raw, str) or not raw.strip():
        raise GuardError(f"Falta tool_input.{key}")

    path = Path(raw).expanduser()

    if not path.is_absolute():
        cwd = Path(str(event.get("cwd") or project_root())).expanduser().resolve()
        path = cwd / path

    return path.resolve(strict=False)


def relative_to_or_none(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def queue_features(root: Path) -> list[dict[str, Any]]:
    queue = load_json(control_root(root) / "queue.json")
    features = queue.get("features", [])

    if not isinstance(features, list):
        raise GuardError("queue.json debe contener una lista features")

    return [item for item in features if isinstance(item, dict)]


def feature_by_id(root: Path, feature_id: str) -> dict[str, Any] | None:
    for feature in queue_features(root):
        if feature.get("id") == feature_id:
            return feature

    return None


def change_domain_for_lease(root: Path, lease: dict[str, Any]) -> str:
    feature = feature_by_id(root, str(lease.get("feature_id", "")))

    if feature is None:
        return "product"

    domain = feature.get("change_domain", "product")

    if domain not in CHANGE_DOMAINS:
        return "product"

    return str(domain)


def eligible_spec_paths(root: Path, role: str) -> set[Path]:
    result: set[Path] = set()

    for feature in queue_features(root):
        state = feature.get("state")
        spec_path = feature.get("spec_path")

        if not isinstance(spec_path, str):
            continue

        base = (root / spec_path).resolve(strict=False)

        if role == "specifier" and state == "DRAFT":
            result.update(
                {
                    base / "specification.md",
                    base / "acceptance.yaml",
                }
            )

        if role == "architect" and state in {"SPEC_READY", "DESIGN_READY"}:
            result.update(
                {
                    base / "architecture.md",
                    base / "implementation-plan.md",
                    base / "test-plan.md",
                }
            )

    return {path.resolve(strict=False) for path in result}


def active_lease(root: Path, role: str) -> dict[str, Any]:
    leases_root = control_root(root) / "leases"
    matches: list[dict[str, Any]] = []

    for path in sorted(leases_root.glob("F-*.json")):
        try:
            lease = load_json(path)
        except GuardError:
            continue

        if lease.get("role") == role:
            matches.append(lease)

    if len(matches) != 1:
        raise GuardError(
            f"Se esperaba exactamente un lease activo para {role}; encontrados: {len(matches)}"
        )

    return matches[0]


def validate_write_edit(root: Path, event: dict[str, Any], role: str) -> tuple[bool, str]:
    path = resolve_input_path(event, "file_path")

    if ".git" in path.parts:
        return False, "No se permite modificar contenido interno de .git"

    if role in {"leader", "qa-reviewer", "unscoped"}:
        return False, f"El rol {role} no tiene autorización de escritura directa"

    if role in {"specifier", "architect"}:
        allowed = eligible_spec_paths(root, role)

        if path in allowed:
            return True, ""

        return False, f"{role} solo puede escribir sus documentos de la feature elegible"

    if role == "implementer":
        lease = active_lease(root, "implementer")
        worktree = Path(str(lease["worktree"])).resolve()
        relative = relative_to_or_none(path, worktree)

        if relative is None:
            return False, "El implementador solo puede escribir dentro del worktree asignado"

        change_domain = change_domain_for_lease(root, lease)

        if change_domain == "harness":
            if relative in HARNESS_IMPLEMENTER_FILES:
                return True, ""

            if relative.parts and relative.parts[0] in HARNESS_IMPLEMENTER_ROOTS:
                return True, ""

            return False, f"Ruta no autorizada para implementer harness: {relative}"

        allowed_roots = {"src", "tests", "runtime"}
        allowed_files = {Path("pyproject.toml"), Path("uv.lock")}

        if relative in allowed_files:
            return True, ""

        if relative.parts and relative.parts[0] in allowed_roots:
            if relative.parts[0] == "runtime":
                required_prefix = Path("runtime/external")
                if relative == required_prefix or required_prefix in relative.parents:
                    return True, ""
                return False, "Solo runtime/external esta autorizado"

            return True, ""

        return False, f"Ruta no autorizada para implementer: {relative}"

    return False, f"Rol no soportado para escritura: {role}"


def requested_agent_type(event: dict[str, Any]) -> str | None:
    tool_input = event.get("tool_input", {})

    for key in ("subagent_type", "agent_type", "name"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value

    return None


def validate_agent_call(event: dict[str, Any], role: str) -> tuple[bool, str]:
    if role != "leader":
        return False, "Solo el leader puede lanzar subagentes"

    requested = requested_agent_type(event)

    if requested is None:
        return False, "La llamada Agent no identifica el tipo de subagente"

    if requested not in SPECIALIZED_AGENTS:
        return False, f"Subagente no autorizado: {requested}"

    return True, ""


def strip_cd_prefix(command: str, worktree: Path) -> tuple[str, bool]:
    value = command.strip()
    expected = str(worktree)

    patterns = (
        rf"^cd\s+{re.escape(shlex.quote(expected))}\s*&&\s*(.+)$",
        rf"^cd\s+[\"']{re.escape(expected)}[\"']\s*&&\s*(.+)$",
        rf"^cd\s+{re.escape(expected)}\s*&&\s*(.+)$",
    )

    for pattern in patterns:
        match = re.match(pattern, value, flags=re.DOTALL)
        if match:
            return match.group(1).strip(), True

    return value, False


def shell_tokens(command: str) -> list[str]:
    """Tokeniza Bash respetando correctamente textos entrecomillados."""

    try:
        lexer = shlex.shlex(
            command,
            posix=True,
            punctuation_chars=";&|<>",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""

        return list(lexer)

    except ValueError as exc:
        raise GuardError(f"Comando Bash con sintaxis o comillas inválidas: {exc}") from exc


def shell_redirection_operator(command: str) -> str | None:
    """Detecta redirecciones reales, ignorando > y < dentro de comillas."""

    for token in shell_tokens(command):
        is_operator = token and all(character in ";&|<>" for character in token)

        if is_operator and ("<" in token or ">" in token):
            return token

    return None


def leader_combines_git_add_and_commit(command: str) -> bool:
    """Detecta git add y git commit encadenados en una única llamada."""

    tokens = shell_tokens(command)

    if not any(token in SHELL_CHAIN_TOKENS for token in tokens):
        return False

    pairs = set(zip(tokens, tokens[1:]))

    return ("git", "add") in pairs and ("git", "commit") in pairs


def contains_forbidden_command(command: str) -> str | None:
    for pattern in FORBIDDEN_COMMAND_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE | re.MULTILINE):
            return pattern

    return None


def script_name_from_command(command: str) -> str | None:
    match = re.search(r"(?:^|\s)scripts/([A-Za-z0-9_.-]+\.py)(?:\s|$)", command)
    return match.group(1) if match else None


def starts_read_only(command: str) -> bool:
    normalized = command.strip()

    return any(
        normalized == prefix or normalized == prefix.strip() or normalized.startswith(prefix)
        for prefix in READ_ONLY_COMMAND_PREFIXES
    )


def split_command_segments(command: str) -> list[str]:
    """Divide un comando en segmentos por operadores de shell (&&, ||, ;, |).

    Permite validar cada subcomando de forma independiente y evita que un
    prefijo de solo lectura o un script autorizado habiliten comandos
    encadenados posteriores no autorizados.
    """

    segments: list[str] = []
    current: list[str] = []

    for token in shell_tokens(command):
        if token in SHELL_CHAIN_TOKENS:
            if current:
                segments.append(" ".join(current).strip())
                current = []
            continue
        current.append(token)

    if current:
        segments.append(" ".join(current).strip())

    return [segment for segment in segments if segment]


def validate_leader_bash(root: Path, command: str) -> tuple[bool, str]:
    redirection = shell_redirection_operator(command)

    if redirection is not None:
        return False, f"Redirección Bash prohibida para leader: {redirection}"

    if leader_combines_git_add_and_commit(command):
        return (
            False,
            "El Leader debe ejecutar git add y git commit en llamadas separadas",
        )

    forbidden = contains_forbidden_command(command)
    if forbidden:
        return False, f"Patrón Bash prohibido para leader: {forbidden}"

    if str(control_root(root)) in command:
        return False, "El plano de control no puede modificarse directamente"

    segments = split_command_segments(command)
    if not segments:
        return False, "La llamada Bash no contiene un comando válido"

    for segment in segments:
        allowed, reason = _leader_segment_allowed(segment)
        if not allowed:
            return False, reason

    return True, ""


def _leader_segment_allowed(segment: str) -> tuple[bool, str]:
    script_name = script_name_from_command(segment)
    if script_name is not None:
        if script_name in LEADER_HARNESS_SCRIPTS:
            return True, ""
        return False, f"Script no autorizado para leader: {script_name}"

    normalized = segment.strip()

    if starts_read_only(normalized):
        return True, ""

    if re.fullmatch(r"mkdir\s+-p\s+specs/features/F-\d{3,}-[a-z0-9-]+/?", normalized):
        return True, ""

    if normalized.startswith("git add "):
        paths = normalized[len("git add ") :].strip().split()
        if paths and all(path.startswith("specs/features/") for path in paths):
            return True, ""
        return False, "Leader solo puede añadir documentos bajo specs/features/"

    if normalized.startswith("git commit "):
        return True, ""

    return False, "Comando Bash no incluido en la allowlist del leader"


def validate_repository_publisher_bash(root: Path, command: str) -> tuple[bool, str]:
    redirection = shell_redirection_operator(command)

    if redirection is not None:
        return False, f"Redirección Bash prohibida para repository-publisher: {redirection}"

    forbidden = contains_forbidden_command(command)
    if forbidden:
        return False, f"Patrón Bash prohibido para repository-publisher: {forbidden}"

    if str(control_root(root)) in command:
        return False, "El plano de control no puede modificarse directamente"

    segments = split_command_segments(command)
    if not segments:
        return False, "La llamada Bash no contiene un comando válido"

    for segment in segments:
        allowed, reason = _repository_publisher_segment_allowed(segment)
        if not allowed:
            return False, reason

    return True, ""


def _repository_publisher_segment_allowed(segment: str) -> tuple[bool, str]:
    script_name = script_name_from_command(segment)
    if script_name is not None:
        if script_name in PUBLISHER_HARNESS_SCRIPTS:
            return True, ""
        return False, f"Script no autorizado para repository-publisher: {script_name}"

    if starts_read_only(segment.strip()):
        return True, ""

    return False, "Repository publisher solo puede leer estado y ejecutar scripts de publicación"


def validate_worktree_bash(
    root: Path, event: dict[str, Any], role: str, command: str
) -> tuple[bool, str]:
    lease = active_lease(root, role)
    worktree = Path(str(lease["worktree"])).resolve()
    cwd = Path(str(event.get("cwd") or root)).resolve()

    body, has_cd = strip_cd_prefix(command, worktree)

    if cwd != worktree and not has_cd:
        return False, f"El comando debe ejecutarse desde el worktree asignado: {worktree}"

    canonical = Path(project_config(root).get("canonical_repository", root)).resolve()
    protected_values = {
        str(canonical),
        str(control_root(root)),
        str(root / "scripts"),
        str(root / ".claude"),
        str(root / "state"),
    }

    for protected in protected_values:
        if protected and protected in body:
            return False, f"El comando referencia una ruta protegida: {protected}"

    redirection = shell_redirection_operator(body)

    if redirection is not None:
        return False, f"Redirección Bash prohibida: {redirection}"

    forbidden = contains_forbidden_command(body)
    if forbidden:
        return False, f"Patrón Bash prohibido: {forbidden}"

    segments = split_command_segments(body)
    if not segments:
        return False, "La llamada Bash no contiene un comando válido"

    if role == "implementer":
        for segment in segments:
            allowed, reason = _implementer_segment_allowed(segment)
            if not allowed:
                return False, reason
        return True, ""

    if role == "qa-reviewer":
        for segment in segments:
            allowed, reason = _qa_reviewer_segment_allowed(segment)
            if not allowed:
                return False, reason
        return True, ""

    return False, f"Rol no soportado para Bash: {role}"


IMPLEMENTER_COMMAND_PREFIXES = (
    "uv add ",
    "uv remove ",
    "uv sync",
    "uv lock",
    "uv run ",
    "git add ",
    "git commit ",
    "git status",
    "git diff",
    "git log",
    "git show",
    "git rev-parse",
    "mkdir ",
    "touch ",
)


def _implementer_segment_allowed(segment: str) -> tuple[bool, str]:
    script_name = script_name_from_command(segment)
    if script_name is not None:
        if script_name in IMPLEMENTER_HARNESS_SCRIPTS:
            return True, ""
        return False, f"Script no autorizado para implementer: {script_name}"

    normalized = segment.strip()

    if starts_read_only(normalized):
        return True, ""

    if normalized.startswith(IMPLEMENTER_COMMAND_PREFIXES):
        return True, ""

    return False, "Comando Bash no incluido en la allowlist del implementer"


def _qa_reviewer_segment_allowed(segment: str) -> tuple[bool, str]:
    script_name = script_name_from_command(segment)
    if script_name is not None:
        if script_name in QA_HARNESS_SCRIPTS:
            return True, ""
        return False, f"Script no autorizado para qa-reviewer: {script_name}"

    if starts_read_only(segment.strip()):
        return True, ""

    return False, "QA solo puede ejecutar lecturas, verificaciones y scripts QA autorizados"


def validate_bash(root: Path, event: dict[str, Any], role: str) -> tuple[bool, str]:
    command = event.get("tool_input", {}).get("command")

    if not isinstance(command, str) or not command.strip():
        return False, "La llamada Bash no contiene un comando válido"

    if role == "leader":
        return validate_leader_bash(root, command)

    if role == "repository-publisher":
        return validate_repository_publisher_bash(root, command)

    if role in {"implementer", "qa-reviewer"}:
        return validate_worktree_bash(root, event, role, command)

    return False, f"El rol {role} no tiene autorización para Bash"


def handle_config_change(root: Path, event: dict[str, Any], role: str) -> int:
    source = event.get("source")

    if source in {"project_settings", "local_settings"}:
        return deny(
            root,
            event,
            role,
            "Los settings de Claude Code no pueden cambiar durante una sesión protegida",
        )

    return allow(root, event, role)


def handle_pre_tool_use(root: Path, event: dict[str, Any], role: str) -> int:
    tool_name = str(event.get("tool_name", ""))

    if tool_name not in MUTATING_TOOLS:
        return allow(root, event, role)

    if tool_name in ALWAYS_DENIED_TOOLS:
        return deny(root, event, role, f"La herramienta {tool_name} está prohibida por el harness")

    try:
        if tool_name in {"Write", "Edit"}:
            permitted, reason = validate_write_edit(root, event, role)
        elif tool_name == "Agent":
            permitted, reason = validate_agent_call(event, role)
        elif tool_name == "Bash":
            permitted, reason = validate_bash(root, event, role)
        else:
            permitted, reason = False, f"Herramienta mutante no soportada: {tool_name}"
    except GuardError as exc:
        permitted, reason = False, str(exc)

    if permitted:
        return allow(root, event, role)

    return deny(root, event, role, reason)


def main() -> int:
    root = project_root()

    try:
        event = read_event()
    except GuardError as exc:
        print(f"Role Guard no pudo interpretar el evento: {exc}", file=sys.stderr)
        return 2

    event_name = event.get("hook_event_name")

    if event_name == "SessionStart":
        return register_session(root, event)

    role = resolve_role(root, event)

    if event_name == "ConfigChange":
        return handle_config_change(root, event, role)

    if event_name == "PreToolUse":
        return handle_pre_tool_use(root, event, role)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
