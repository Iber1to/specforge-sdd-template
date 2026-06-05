# Feature Architecture — F-001 CLI local de health check

## Context

La feature F-001 (estado `SPEC_READY`) necesita un comando local de health
check, autocontenido y determinista, ejecutable mediante el entorno `uv` del
proyecto. El comando debe emitir por `stdout` un único documento JSON válido con
los campos `status`, `application`, `version` y `python_version`, y terminar con
código de salida `0` cuando el estado sea correcto.

Restricciones técnicas relevantes del repositorio:

- Estructura canónica: `src/`, `tests/`, `pyproject.toml`.
- Paquete de aplicación existente (vacío): `src/desktop_overlay_assistant/`.
- `pyproject.toml` define `requires-python = ">=3.12,<3.13"`, no contiene
  `[build-system]` y configura `pythonpath = ["."]` con `testpaths = ["tests"]`.
  En consecuencia, el paquete de aplicación no se instala como distribución y se
  importa por su ruta desde la raíz del repositorio: `src.desktop_overlay_assistant`.
- Sin red, sin base de datos, sin componentes Windows. La validación Windows
  **no** es requerida por esta feature.

Esta arquitectura diseña la solución mínima que satisface AC-001..AC-008 sin
introducir requisitos funcionales nuevos.

## Decision

Implementar el health check como un módulo Python único dentro del paquete de
aplicación, con dos responsabilidades separadas y verificables:

1. Una **función pura** que construye el documento de health check (un
   `dict[str, str]`) a partir de los metadatos de la aplicación y de la versión
   del intérprete Python en ejecución. Es determinista y no realiza E/S.
2. Un **punto de entrada CLI** (`main`) que serializa ese documento a JSON,
   lo escribe en `stdout` y devuelve el código de salida `0` cuando el estado es
   correcto.

El comando se expone como **módulo ejecutable** mediante un bloque
`if __name__ == "__main__"`, de modo que sea invocable a través del entorno
`uv`:

```
uv run python -m src.desktop_overlay_assistant.health_check
```

Razones de esta decisión:

- **Simplicidad operativa y coherencia con el repo.** No existe `[build-system]`,
  por lo que un `console_scripts` no quedaría instalado por `uv run <nombre>`.
  La invocación `uv run python -m ...` funciona con la estructura actual sin
  añadir empaquetado ni dependencias.
- **Aislamiento Windows/Ubuntu.** El comando solo usa la biblioteca estándar
  (`json`, `sys`, `platform`) y metadatos del proyecto; no toca rutas, red, base
  de datos ni APIs específicas de plataforma, por lo que es idéntico en Linux y
  no introduce impacto en el runtime Windows.
- **Latencia.** Sin E/S externa ni importaciones pesadas, el arranque y la
  ejecución son del orden de milisegundos.
- **Testabilidad.** Separar la construcción del documento (pura) de la
  serialización/salida permite tests unitarios directos (AC-007) y tests de
  integración por subproceso sobre el comando completo (AC-008).

Alternativa considerada y descartada para esta feature: declarar un
`[project.scripts]` + `[build-system]` para exponer un binario `health-check`.
Se descarta como mecanismo principal porque exigiría instalar el paquete y
añadir backend de construcción, ampliando el alcance sin necesidad. El
implementador podrá añadirlo de forma opcional (ver plan de implementación) sin
romper el contrato de invocación documentado.

## Components

- **`src/desktop_overlay_assistant/__init__.py`** (nuevo): marca el directorio
  como paquete importable y expone los metadatos de aplicación reutilizables:
  - `APPLICATION` (identificador de la aplicación, cadena no vacía).
  - `VERSION` (versión de la aplicación, cadena no vacía), alineada con
    `project.version` de `pyproject.toml` (actualmente `"0.1.0"`).
- **`src/desktop_overlay_assistant/health_check.py`** (nuevo): módulo del
  comando. Contiene:
  - `build_health_report() -> dict[str, str]`: función pura que produce el
    documento de health check.
  - `main(argv: list[str] | None = None) -> int`: punto de entrada CLI que
    serializa el documento a JSON, lo escribe en `stdout` y devuelve el código de
    salida.
  - Guard `if __name__ == "__main__": raise SystemExit(main())`.
- **Tests** (nuevos): unitarios en `tests/unit/` e integración en
  `tests/integration/`.

## Interfaces

### Función pura

```
build_health_report() -> dict[str, str]
```

- Entradas: ninguna (lee metadatos del paquete y la versión del intérprete en
  ejecución).
- Salida: diccionario con exactamente las claves obligatorias:
  - `status`: `"ok"` en estado correcto.
  - `application`: `APPLICATION`, cadena no vacía.
  - `version`: `VERSION`, cadena no vacía.
  - `python_version`: versión del intérprete Python activo, cadena no vacía
    (obtenida con `platform.python_version()`).
- Sin efectos secundarios, sin E/S, sin red, sin base de datos.

### Punto de entrada CLI

```
main(argv: list[str] | None = None) -> int
```

- Construye el documento con `build_health_report()`.
- Serializa con `json.dumps(report)` produciendo un único documento JSON.
- Escribe el JSON en `stdout` (una sola línea, seguida de salto de línea).
- Devuelve `0` cuando el estado es correcto (`status == "ok"`).
- No escribe el documento JSON en `stderr`; cualquier diagnóstico ajeno al JSON,
  si existiera, iría a `stderr` para no contaminar `stdout`.

### Contrato de invocación (límite externo)

- Comando estable de health check:
  `uv run python -m src.desktop_overlay_assistant.health_check`.
- Salida observable: una única línea JSON en `stdout`; código de salida `0`.

## Data Flow

1. El operador o el proceso automatizado invoca
   `uv run python -m src.desktop_overlay_assistant.health_check`.
2. `uv` activa el entorno gestionado y ejecuta el módulo.
3. El guard `__main__` llama a `main()`.
4. `main()` invoca `build_health_report()`.
5. `build_health_report()` lee `APPLICATION` y `VERSION` del paquete y obtiene
   `platform.python_version()`, y devuelve el `dict` con las cuatro claves.
6. `main()` serializa el `dict` a JSON con `json.dumps` y lo escribe en `stdout`.
7. `main()` devuelve `0`; el guard lo propaga como código de salida del proceso.
8. El consumidor parsea el JSON de `stdout` y/o evalúa el código de salida.

No hay red, base de datos, sistema de archivos de aplicación ni rutas
específicas de plataforma en ningún paso.

## Data Model

Documento de health check (objeto JSON con valores de tipo cadena):

| Campo            | Tipo   | Origen                              | Restricción          |
|------------------|--------|-------------------------------------|----------------------|
| `status`         | string | Constante de estado correcto        | `== "ok"`            |
| `application`    | string | `APPLICATION` del paquete           | no vacío             |
| `version`        | string | `VERSION` del paquete               | no vacío             |
| `python_version` | string | `platform.python_version()`         | no vacío             |

Ejemplo representativo de la salida:

```json
{"status": "ok", "application": "desktop-overlay-assistant", "version": "0.1.0", "python_version": "3.12.x"}
```

El conjunto de claves es estable entre ejecuciones para un mismo entorno
(determinismo requerido por la especificación). `python_version` puede variar
según el intérprete activo, pero siempre es una cadena no vacía.

## Performance Considerations

- **Latencia:** ejecución dominada por el arranque del intérprete bajo `uv`. El
  trabajo propio del comando (construir un `dict` de cuatro claves y serializarlo)
  es O(1) y del orden de microsegundos; el coste total es de pocos milisegundos
  tras el arranque del intérprete.
- **Memoria:** despreciable; estructuras de tamaño fijo y solo módulos de la
  biblioteca estándar (`json`, `sys`, `platform`).
- **Concurrencia:** no aplica; ejecución de un solo proceso, sin estado
  compartido ni recursos externos, idempotente y reentrante.
- **Cuellos de botella:** ninguno relevante; no hay E/S de red ni de base de
  datos. La importación se mantiene mínima para no penalizar el arranque.

## Failure Modes

- **Metadatos ausentes o vacíos** (`APPLICATION`/`VERSION`): se definen como
  constantes no vacías dentro del paquete, por lo que en condiciones normales no
  pueden faltar. Si el implementador derivara la versión de una fuente externa y
  esta no estuviese disponible, debe recurrir a la constante del paquete como
  valor de respaldo para garantizar una cadena no vacía y `status == "ok"`.
- **Fallo de importación del intérprete/entorno:** si el entorno Python no
  arranca, el proceso falla antes de producir JSON y termina con código distinto
  de `0`; esto es exactamente la señal de "no saludable" que la feature pretende
  hacer observable. No se enmascara con un `0`.
- **Contaminación de `stdout`:** para no romper el parseo del JSON, el comando no
  escribe nada más en `stdout`. Cualquier traza de diagnóstico va a `stderr`.
- **Recuperación:** el comando es sin estado e idempotente; ante un fallo
  transitorio del entorno, basta con reintentar la ejecución. No deja efectos
  secundarios que requieran limpieza.

## Windows Runtime Impact

None. El comando usa exclusivamente la biblioteca estándar de Python
(`json`, `sys`, `platform`) y metadatos del proyecto; no invoca APIs de Windows,
no toca el `runtime/windows-runner/` ni depende de rutas o componentes
específicos de plataforma. La feature no requiere validación Windows y no
introduce ningún criterio `windows_e2e`.

## Open Questions

None
