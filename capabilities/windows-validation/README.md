# Capability: Windows Validation

Capacidad opcional para proyectos que requieren evidencia de validacion en Windows.

## Activacion

En `project.yaml`:

```yaml
capabilities: [windows-validation]
```

El generador marcara:

```json
{
  "windows_validation_required": true
}
```

en `state/project.json`.

## Componentes

- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

## Evidencia

La evidencia Windows debe seguir el contrato documentado en:

```text
docs/windows-runner/evidence-contract.md
```

## Nota Operativa

Windows validation no es dependencia del core. Los proyectos que no activan esta capability pueden completar features sin evidencia Windows.
