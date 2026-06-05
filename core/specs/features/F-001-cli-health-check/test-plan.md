# Test Plan — F-001 CLI local de health check

## Test Strategy

La verificación combina tres niveles, alineados con `acceptance.yaml`:

- **Unit:** validan la función pura `build_health_report()` (construcción del
  documento, campos obligatorios y valor `"ok"`), sin E/S.
- **Integration:** ejecutan el comando completo por subproceso
  (`python -m src.desktop_overlay_assistant.health_check`) y verifican el JSON de
  `stdout` y el código de salida `0`.
- **Inspection:** revisión estática del código y del diseño para confirmar la
  ausencia de accesos a red, base de datos y componentes Windows.

Todas las pruebas se ejecutan en el entorno Linux gestionado por `uv` con
`pytest`. No se requiere validación Windows: esta feature no define criterios
`windows_e2e`. Las pruebas son deterministas y autocontenidas.

## Acceptance Traceability

| Criterio | Verificación | Evidencia concreta |
|----------|--------------|--------------------|
| AC-001 | integration | `tests/integration/test_health_check_cli.py`: el comando se ejecuta vía `uv`/`python -m` y produce salida en `stdout`. |
| AC-002 | integration | `tests/integration/test_health_check_cli.py`: `json.loads(stdout)` parsea un único documento JSON válido sin error. |
| AC-003 | integration | `tests/integration/test_health_check_cli.py`: el JSON contiene las claves `status`, `application`, `version`, `python_version`. |
| AC-004 | integration | `tests/integration/test_health_check_cli.py`: el JSON de `stdout` tiene `status == "ok"`. |
| AC-005 | integration | `tests/integration/test_health_check_cli.py`: el proceso termina con código de salida `0`. |
| AC-006 | inspection | Sección "Failure Modes"/"Windows Runtime Impact" de `architecture.md` y revisión del código: solo se usan `json`, `sys`, `platform` y metadatos del paquete; sin red, base de datos ni componentes Windows. |
| AC-007 | unit | `tests/unit/test_health_check.py`: valida la construcción del documento, los campos obligatorios y `status == "ok"`. |
| AC-008 | integration | `tests/integration/test_health_check_cli.py`: ejecuta el comando completo y verifica JSON de `stdout` y código de salida `0`. |

## Unit Tests

Archivo: `tests/unit/test_health_check.py`. Importa
`src.desktop_overlay_assistant.health_check`.

- **test_build_report_contains_required_fields (AC-007):**
  `build_health_report()` devuelve un `dict` cuyo conjunto de claves incluye
  exactamente `status`, `application`, `version`, `python_version`.
- **test_build_report_status_is_ok (AC-007):** el campo `status` del documento
  construido es exactamente `"ok"`.
- **test_build_report_fields_are_nonempty_strings (AC-007):** `application`,
  `version` y `python_version` son cadenas no vacías (`isinstance(v, str)` y
  `v.strip() != ""`).
- **test_build_report_python_version_matches_runtime (AC-007):**
  `python_version` coincide con `platform.python_version()` del intérprete en
  ejecución.

## Integration Tests

Archivo: `tests/integration/test_health_check_cli.py`. Ejecuta el comando por
subproceso desde la raíz del repositorio:
`subprocess.run([sys.executable, "-m",
"src.desktop_overlay_assistant.health_check"], capture_output=True, text=True)`.

- **test_command_runs_and_writes_stdout (AC-001):** el comando finaliza y
  `stdout` no está vacío.
- **test_stdout_is_single_valid_json (AC-002):** `json.loads(result.stdout)` no
  lanza excepción y produce un único objeto JSON (la salida es una sola línea
  parseable).
- **test_json_has_required_fields (AC-003):** el objeto parseado contiene
  `status`, `application`, `version` y `python_version`.
- **test_status_is_ok (AC-004):** el objeto parseado cumple `status == "ok"`.
- **test_exit_code_is_zero (AC-005):** `result.returncode == 0`.
- **test_full_command_contract (AC-008):** caso integrado que comprueba, en una
  única ejecución, código de salida `0` y JSON de `stdout` con campos
  obligatorios y `status == "ok"`.

## Windows E2E Tests

None. La feature no requiere validación Windows y no define criterios
`windows_e2e`. El comando no interactúa con el runtime Windows.

## Performance Tests

None. El comando es O(1), sin E/S de red ni de base de datos, y su latencia está
dominada por el arranque del intérprete; no procede una prueba de rendimiento
dedicada. Las pruebas de integración constatan implícitamente una ejecución
rápida y sin bloqueos.

## Exit Criteria

La implementación se considera aceptable cuando:

- Todos los tests unitarios y de integración descritos pasan en el entorno Linux
  bajo `uv`/`pytest`.
- Cada criterio AC-001..AC-008 está cubierto por la evidencia trazada en la
  sección "Acceptance Traceability".
- La inspección confirma ausencia de accesos a red, base de datos y componentes
  Windows (AC-006).
- `ruff check` y `ruff format --check` no reportan problemas en los archivos
  nuevos.
- La suite completa de tests del repositorio permanece en verde.
