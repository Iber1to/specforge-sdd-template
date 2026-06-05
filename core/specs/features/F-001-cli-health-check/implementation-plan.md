# Implementation Plan — F-001 CLI local de health check

## Strategy

Implementar el comando de health check con la mínima superficie posible,
respetando la estructura del repositorio (`src/`, `tests/`, `pyproject.toml`) y
la arquitectura de F-001. El trabajo se divide en:

1. Exponer metadatos de aplicación en el paquete (`__init__.py`).
2. Crear el módulo del comando con una función pura de construcción del documento
   y un punto de entrada CLI ejecutable como módulo (`python -m`).
3. Cubrir el comportamiento con tests unitarios (función pura) y de integración
   (ejecución por subproceso del comando completo).

El comando solo usa la biblioteca estándar (`json`, `sys`, `platform`) y los
metadatos del paquete. No se añaden dependencias de ejecución. No se accede a
red, base de datos ni componentes Windows.

El contrato de invocación estable es:

```
uv run python -m src.desktop_overlay_assistant.health_check
```

## Work Breakdown

1. **Metadatos del paquete** — `src/desktop_overlay_assistant/__init__.py`:
   - Definir `APPLICATION: str` con el identificador de la aplicación, una cadena
     no vacía (por ejemplo `"desktop-overlay-assistant"`, coincidiendo con
     `project.name`).
   - Definir `VERSION: str` con la versión de la aplicación, alineada con
     `project.version` de `pyproject.toml` (actualmente `"0.1.0"`).
   - Mantener ambos valores como cadenas no vacías.

2. **Módulo del comando** — `src/desktop_overlay_assistant/health_check.py`:
   - Importar `json`, `sys`, `platform` y los metadatos del paquete
     (`APPLICATION`, `VERSION`).
   - Definir la constante de estado correcto `OK_STATUS = "ok"`.
   - Implementar `build_health_report() -> dict[str, str]` que devuelva un
     diccionario con las claves obligatorias, en este orden:
     `{"status": OK_STATUS, "application": APPLICATION, "version": VERSION,
     "python_version": platform.python_version()}`. Función pura, sin E/S.
   - Implementar `main(argv: list[str] | None = None) -> int`:
     - Construir el documento con `build_health_report()`.
     - Serializarlo con `json.dumps(report)` (un único documento JSON).
     - Escribirlo en `stdout` mediante `print(...)` o
       `sys.stdout.write(... + "\n")` (una sola línea, nada más en `stdout`).
     - Devolver `0` cuando `report["status"] == OK_STATUS`.
   - Añadir el guard `if __name__ == "__main__": raise SystemExit(main())`.

3. **Tests unitarios** — `tests/unit/test_health_check.py`:
   - Verificar que `build_health_report()` devuelve las cuatro claves
     obligatorias y que `status == "ok"`.
   - Verificar que `application`, `version` y `python_version` son cadenas no
     vacías y que `python_version` coincide con `platform.python_version()`.

4. **Tests de integración** — `tests/integration/test_health_check_cli.py`:
   - Ejecutar el comando completo por subproceso con
     `subprocess.run([sys.executable, "-m",
     "src.desktop_overlay_assistant.health_check"], ...)` desde la raíz del repo,
     capturando `stdout` y el código de salida.
   - Verificar código de salida `0`.
   - Parsear `stdout` con `json.loads` (JSON único y válido) y comprobar campos
     obligatorios y `status == "ok"`.

5. **Verificación local previa a la entrega** (sin cambiar estados):
   - `uv run ruff check` y `uv run ruff format --check` sobre los archivos nuevos.
   - `uv run pytest tests/unit/test_health_check.py
     tests/integration/test_health_check_cli.py`.
   - Comando manual:
     `uv run python -m src.desktop_overlay_assistant.health_check`.

Nota sobre el entry point: el mecanismo principal y obligatorio es el módulo
ejecutable (`python -m ...`), coherente con la ausencia de `[build-system]` en
`pyproject.toml`. **Opcionalmente**, si el implementador decide exponer además un
script con nombre (`health-check`), deberá añadir `[build-system]` y
`[project.scripts]` en `pyproject.toml` e instalar el paquete; esto es opcional y
no debe romper el contrato `python -m` documentado ni introducir dependencias de
red/base de datos.

## Files Expected to Change

- `src/desktop_overlay_assistant/__init__.py` (nuevo): metadatos `APPLICATION`,
  `VERSION`.
- `src/desktop_overlay_assistant/health_check.py` (nuevo): función pura, `main`
  y guard `__main__`.
- `tests/unit/test_health_check.py` (nuevo): tests unitarios de la función pura.
- `tests/integration/test_health_check_cli.py` (nuevo): tests de integración del
  comando completo.
- `pyproject.toml` (opcional, solo si el implementador añade el script con
  nombre): bloques `[build-system]` y `[project.scripts]`.

No se modifica ningún otro archivo. No se tocan `runtime/windows-runner/`,
`state/`, `scripts/` ni el plano de control.

## Dependencies

None. El comando se apoya exclusivamente en la biblioteca estándar de Python
(`json`, `sys`, `platform`) y en los metadatos del paquete. Las dependencias de
desarrollo necesarias (`pytest`, `ruff`) ya están declaradas en el grupo `dev`
de `pyproject.toml`.

## Risks

- **Import path del paquete:** sin `[build-system]`, el módulo se importa como
  `src.desktop_overlay_assistant.health_check`. Mitigación: usar exactamente esa
  ruta tanto en la invocación `python -m` como en los imports de los tests
  unitarios, y ejecutar el subproceso de integración desde la raíz del repo
  (donde `pythonpath = ["."]` aplica).
- **Contaminación de `stdout`:** escribir trazas adicionales en `stdout` rompería
  el parseo JSON (AC-002). Mitigación: emitir únicamente el documento JSON en
  `stdout`; cualquier diagnóstico va a `stderr`.
- **Desalineación de `version`:** la versión expuesta podría divergir de
  `project.version`. Mitigación: documentar y mantener `VERSION` alineada con
  `pyproject.toml`; en cualquier caso debe ser una cadena no vacía.
- **Sobrealcance:** añadir empaquetado o lógica de diagnóstico avanzada excedería
  el alcance. Mitigación: mantener la solución mínima; el script con nombre es
  estrictamente opcional.

## Rollback

Los cambios son puramente aditivos y aislados en archivos nuevos. Para revertir
basta con eliminar los archivos creados
(`src/desktop_overlay_assistant/health_check.py`,
`src/desktop_overlay_assistant/__init__.py`, `tests/unit/test_health_check.py`,
`tests/integration/test_health_check_cli.py`) y, si se hubiera añadido, deshacer
la edición opcional de `pyproject.toml`. No hay migraciones de datos, estado
persistente ni efectos secundarios externos que limpiar; revertir el commit
correspondiente deja el repositorio en su estado anterior.
