# Feature Specification — F-001 CLI local de health check

## Problem

No existe ninguna forma local, rápida y determinista de comprobar que la
aplicación y su entorno Python arrancan correctamente. Sin una señal
observable y estructurada, una persona operadora o un proceso automatizado no
pueden confirmar de forma fiable que la instalación está en un estado válido
antes de iniciar tareas posteriores. La verificación manual actual es ambigua
y no produce una salida que pueda consumirse mediante máquinas.

## Goal

Proporcionar un comando local de health check que pueda ejecutarse mediante el
entorno `uv`, que valide que la aplicación y su entorno Python arrancan
correctamente, que emita un documento JSON válido y estructurado por la salida
estándar y que finalice con código de salida `0` cuando el estado sea correcto.
El resultado debe ser observable y consumible por humanos y por automatización
sin depender de red, base de datos ni componentes específicos de Windows.

## Scope

- Un comando ejecutable de health check invocable a través del entorno `uv`.
- Emisión por la salida estándar (`stdout`) de un único documento JSON válido.
- Inclusión obligatoria en el JSON de los campos `status`, `application`,
  `version` y `python_version`.
- Valor `"ok"` en el campo `status` cuando la ejecución sea correcta.
- Código de salida `0` cuando el estado de health check sea correcto.
- Cobertura mediante tests unitarios y tests de integración que validen el
  comportamiento observable del comando.

## Out of Scope

- Cualquier comprobación que requiera acceso a red.
- Cualquier comprobación que requiera una base de datos.
- Cualquier comportamiento o validación específicos de componentes Windows.
- Validación Windows end-to-end (no requerida para esta feature).
- Interfaz gráfica, overlay u otra superficie de usuario distinta de la CLI.
- Diagnóstico avanzado del entorno más allá de confirmar el arranque correcto.
- Definición de la arquitectura interna, nombres de módulos o decisiones de
  diseño técnico.

## User Scenarios

- Como persona operadora, ejecuto el comando de health check mediante `uv` y
  obtengo por `stdout` un JSON con `status` igual a `"ok"` y un código de
  salida `0`, de modo que confirmo que la aplicación arranca correctamente.
- Como proceso automatizado, invoco el comando, parseo el JSON de `stdout` y
  leo los campos `status`, `application`, `version` y `python_version` para
  decidir de forma determinista si el entorno es válido.
- Como persona operadora en un entorno sin red ni base de datos, ejecuto el
  comando y obtengo el mismo resultado correcto, porque el health check no
  depende de esos recursos.

## Functional Requirements

- FR-001: El sistema debe exponer un comando de health check ejecutable a
  través del entorno `uv`.
- FR-002: El comando debe escribir por `stdout` un único documento JSON
  sintácticamente válido.
- FR-003: El documento JSON debe incluir, como mínimo, los campos `status`,
  `application`, `version` y `python_version`.
- FR-004: El campo `status` debe contener el valor `"ok"` cuando la ejecución
  sea correcta.
- FR-005: El campo `application` debe contener un identificador de la
  aplicación como cadena no vacía.
- FR-006: El campo `version` debe contener la versión de la aplicación como
  cadena no vacía.
- FR-007: El campo `python_version` debe reflejar la versión del intérprete
  Python en ejecución como cadena no vacía.
- FR-008: El comando debe finalizar con código de salida `0` cuando el estado
  de health check sea correcto.
- FR-009: El comando no debe realizar accesos a red, base de datos ni
  componentes específicos de Windows durante su ejecución.

## Non-Functional Requirements

- El comando debe ejecutarse de forma local y autocontenida, sin dependencias
  externas de red ni base de datos.
- El comando debe ser determinista: para un mismo entorno, las claves del JSON
  y el código de salida deben ser estables entre ejecuciones.
- La salida JSON debe ser parseable por consumidores automáticos estándar.
- El comando debe ejecutarse en el entorno Linux del proyecto sin requerir
  componentes Windows.

## Assumptions

- La invocación del comando se realiza dentro del entorno gestionado por `uv`
  definido por el proyecto.
- Los valores de `application` y `version` proceden de los metadatos del
  proyecto y se consideran cadenas no vacías.
- El campo `python_version` corresponde a la versión del intérprete Python
  activo durante la ejecución.
- La salida JSON se emite por `stdout`; los diagnósticos o errores ajenos al
  documento JSON, si existieran, no se mezclan con `stdout`.
- "Estado correcto" significa que la aplicación y su entorno Python arrancan
  sin error y que todos los campos obligatorios pueden producirse.

## Acceptance Summary

Los criterios de aceptación de `acceptance.yaml` cubren: la existencia de un
comando ejecutable mediante `uv` (AC-001); la emisión de un JSON válido por
`stdout` (AC-002); la presencia de los campos obligatorios `status`,
`application`, `version` y `python_version` (AC-003); el valor `"ok"` del campo
`status` en ejecución correcta (AC-004); el código de salida `0` en estado
correcto (AC-005); la ausencia de dependencias de red, base de datos y
componentes Windows (AC-006); y la cobertura mediante tests unitarios (AC-007)
e integración (AC-008) del comportamiento observable.

## Open Questions

None
