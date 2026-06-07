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
  "windows_validation_available": true
}
```

en `state/project.json`. La obligatoriedad de evidencia Windows es por feature
(se declara con `--capability windows-validation` o `--windows-validation-required`
al registrar la feature); instalar la capability solo la deja disponible.

## Componentes

- `scripts/collect_windows_evidence.py`
- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

## Evidencia

La evidencia Windows debe seguir el contrato documentado en:

```text
docs/windows-runner/evidence-contract.md
```

Runner minimo:

```bash
python3 scripts/collect_windows_evidence.py \
  --feature F-001 \
  --commit <commit>
```

Smoke no Windows para validar infraestructura en Jarvis:

```bash
python3 scripts/collect_windows_evidence.py \
  --feature F-001 \
  --allow-non-windows
```

## Nota Operativa

Windows validation no es dependencia del core. Los proyectos que no activan esta capability pueden completar features sin evidencia Windows.
