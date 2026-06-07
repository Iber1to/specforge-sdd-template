# Runbook de Validaciones Reales (Windows y SSH)

Estas validaciones requieren hardware o servicios reales que las suites offline no
cubren. El codigo ya esta listo (`F2`, `T-007C`, BatchMode/ConnectTimeout SSH); aqui
van los procedimientos para que QA complete `T-008E` y `T-008F`.

## T-008E — Windows real

Prerrequisitos: una workstation Windows con Python 3.12 y acceso al `artifact_root`
del proyecto (carpeta compartida, `external-runtime` SSH/SCP, o copia manual).

1. En el host de orquestacion (Linux), finaliza la feature y anota el commit
   revisado por QA (`reviewed_commit`).
2. En la workstation Windows, dentro del proyecto generado, ejecuta el runner
   **sin** `--allow-non-windows` (el check de plataforma debe pasar por ser Windows
   real):

   ```
   python scripts\collect_windows_evidence.py --feature F-XXX --commit <commit>
   ```

3. Publica `artifact_root/windows-tests/F-XXX/latest.json` (y `runner.log` /
   `environment.json`) hacia el `artifact_root` accesible desde Linux.
4. En el host Linux valida:

   ```
   python3 scripts/validate_windows_evidence.py --feature F-XXX --commit <commit>
   ```

Criterios de aceptacion:

- El runner se ejecuta en Windows real sin override.
- No importa modulos POSIX (corregido en `control_common`, locking portable).
- La evidencia es valida; commit y feature coinciden.
- Un commit incorrecto se rechaza con exit code 2.

La cobertura offline equivalente (`collect --allow-non-windows` + `validate`) esta en
`tests/test_generator.py::test_windows_evidence_collect_and_validate_offline`.

## T-008F — SSH real

Prerrequisitos: un target SSH accesible (VM o host remoto) con autenticacion por
clave (compatible con `BatchMode=yes`, sin password interactivo) y el binario del
comando declarado disponible en el remoto.

1. En `state/capabilities/external-runtime.json`, habilita un target SSH real
   (`enabled: true`, `host`, `user`, `port`) y declara `allowed_command_templates`
   con los `command-id` permitidos.
2. Ejecuta un job:

   ```
   uv run python scripts/run_external_runtime.py \
     --feature F-XXX --target <ssh-target> --command-id <id>
   ```

3. Revisa la evidencia en
   `artifact_root/capabilities/external-runtime/F-XXX/latest.json`.

Criterios de aceptacion:

- Un job SSH valido produce resultado `PASSED` con evidencia.
- Un target inaccesible falla con error claro (BatchMode + ConnectTimeout evitan
  colgarse o pedir password) y queda registrado en la evidencia.
- Solo se ejecutan comandos declarados por `command-id`; no se admiten comandos
  libres por SSH.

La cobertura offline equivalente (command-id desconocido rechazado, target
inaccesible falla limpio) esta en
`tests/test_generator.py::test_external_runtime_ssh_guards_offline`.
