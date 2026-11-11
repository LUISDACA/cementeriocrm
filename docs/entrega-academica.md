# Demostración académica de CementerioERP

La aplicación utiliza el nombre y logotipo **CementerioERP**, aprobados por el usuario; sus requisitos permanecen en Jira como CementerioC (CM).

El usuario confirmó el carácter académico del proyecto el 2 de noviembre de 2026. La entrega demuestra las historias de gestión con datos ficticios, un plano esquemático y operaciones simuladas. No requiere un plano geográfico ni un procedimiento de un cementerio real.

## Preparación

La aplicación utiliza Django 5.2 y PostgreSQL. Las dependencias ya están instaladas en `.venv`. Configura en `.env` una base PostgreSQL accesible, `DJANGO_DEBUG=1` y tu propio `DJANGO_SECRET_KEY`. Desde la carpeta del proyecto:

```bash
make demo
```

El comando ejecuta comprobaciones, migraciones, estáticos y datos de demostración; solicita una contraseña propia sin mostrarla y abre el servidor en **http://127.0.0.1:8000**. La contraseña debe tener al menos 12 caracteres y superar los validadores de Django. Se aplica solo a cuentas nuevas; las existentes conservan su contraseña. Para preparar sin abrir servidor:

```bash
.venv/bin/python scripts/run_academic.py --prepare-only
```

El perfil `config.settings_academic` conserva PostgreSQL, habilita el flujo simulado de movimientos y entrega los mensajes de recuperación en un buzón local privado. Muestra un aviso académico en la interfaz. El perfil normal conserva sus controles y configuración SMTP.

La primera carga genera los datos base y, automáticamente, añade seis bloques de 64 sepulturas al lote ilustrativo. Si ya se había preparado una versión anterior, al reiniciar con `make demo` se ejecuta la ampliación que agrega las 384 sepulturas nuevas sin duplicar códigos ni borrar registros. El mapa totaliza 432 espacios, con ocupaciones de nombres ficticios, reservas y estados diversos. Después de iniciar, actualiza el mapa en el navegador con Ctrl+F5.

Las fichas usan nombres colombianos verosímiles generados para la demostración y números con prefijo `DEMO-ERP`; son datos ficticios, no identidades obtenidas de un cementerio. El código `C-101` indica la fila 1 y la sepultura 01 del bloque C.

### Alternativa con Docker

Tras configurar `.env` según el README:

```bash
docker compose -f compose.yaml -f compose.academic.yaml up --build -d
docker compose -f compose.yaml -f compose.academic.yaml exec web python scripts/run_academic.py --prepare-only
```

Esta alternativa está preparada; los contenedores no se han construido ni ejecutado en esta sesión.

## Cuentas para la exposición

Todas usan la contraseña elegida durante la carga inicial. No hay una contraseña predeterminada.

| Cuenta | Función |
| --- | --- |
| admin@example.test | Configuración, usuarios, autorizaciones, auditoría y buzón simulado |
| oficina@example.test | Personas, responsables y contratos |
| tesoreria@example.test | Reservas, pagos y recibos |
| operaciones@example.test | Inhumaciones y ejecución de movimientos |
| consulta@example.test | Consulta restringida de espacios y mapa |

Se puede realizar todo el recorrido inicial con Administración y luego contrastar los permisos con los demás perfiles. No mezclar información personal real con esta demostración.

## Recorrido sugerido de exposición

1. **Inicio y mapa.** Mostrar el lote ilustrativo con senderos, árboles, acceso y bloques C–H. Usa «Ajustar» para ver el terreno completo; luego acerca el bloque C y localiza C-101. La leyenda combina texto y color. El plano representa un parque inventado, no reproduce un lote real.
2. **Responsable y persona.** Crear un responsable ficticio, registrar una persona con fecha de fallecimiento anterior a hoy y vincular ambos. Los homónimos se distinguen por ficha/documento.
3. **Reserva con dinero.** Elegir una sepultura disponible, por ejemplo A-301 en el plano inicial. Registrar una reserva con anticipo de 100.000 COP, referencia y vencimiento futuro. Verificar el recibo y el estado Reservada.
4. **Contrato.** Crear un contrato de 1.000.000 COP para el mismo espacio y responsable, vigente hoy. El sistema aplica automáticamente el anticipo vigente del mismo espacio y responsable una sola vez. El saldo inicial debe quedar en 900.000 COP.
5. **Inhumación.** Seleccionar la persona, espacio y contrato y registrar la fecha actual. Verificar Ocupada en ficha y mapa. Intentar una segunda ocupación del mismo espacio debe ser rechazado.
6. **Pagos.** Registrar un abono y después el saldo restante. Mostrar recibos y saldo cero. Un importe superior al saldo es rechazado; una anulación exige motivo y conserva el registro original.
7. **Movimiento simulado.** Solicitar una exhumación con destino externo ficticio y fecha de hoy. Mostrar que la solicitud mantiene ocupado el espacio. Autorizar con una referencia como `SIMULACION-ACADEMICA-001`; confirmar ejecución dejando la hora vacía para usar el momento de confirmación. Revisar la liberación y el historial. Para un traslado interno se necesita otro espacio disponible y su contrato vigente con un responsable vinculado.
8. **Auditoría.** Corregir un teléfono y mostrar los valores anterior y nuevo desde Administración. Explicar la conservación de eventos y la protección de la identidad física de espacios con historia.
9. **Roles.** Entrar con Consulta y comprobar que no ve finanzas ni puede registrar operaciones. Comparar Tesorería y Operaciones.
10. **Recuperación.** Desde otra ventana solicitar recuperación para `consulta@example.test`. En la sesión de Administración abrir «Correos simulados», copiar el enlace y elegir otra contraseña. Los mensajes no salen a Internet. Si se cambia esta contraseña, conservar el nuevo valor para futuros ingresos.

## Reglas de la simulación

Una sepultura admite una persona y una persona tiene una ubicación vigente. La inhumación exige contrato válido y responsable vinculado. Las reservas exigen un anticipo positivo. Un contrato vencido no libera una ocupación. Solicitar o autorizar un movimiento tampoco la libera: solo su ejecución actualiza origen, destino e historial.

El flujo solicitud → autorización → ejecución es la propuesta académica. No se inventan plazos legales. La cancelación o el vencimiento de una reserva no ejecuta devoluciones automáticas; conserva el dinero registrado para conciliación. Las devoluciones bancarias y documentos adjuntos quedan fuera de la demostración.

## Entregar una copia

`make package` crea `dist/CementerioERP-academico.zip` y un archivo `.sha256`. El ZIP contiene código, recursos, pruebas y guías, junto con `MANIFEST.sha256`. No contiene las cuentas ni la contraseña elegida, la base local, `.env` o los mensajes de recuperación.

En el equipo de destino extrae el ZIP, entra en `CementerioERP`, verifica `sha256sum --check MANIFEST.sha256`, configura `.env` y PostgreSQL y ejecuta el instalador y `make demo` como se explica en el README. La contraseña de demostración se vuelve a elegir en la nueva base. El paquete no requiere que se comparta ninguna credencial local. Se comprobó su extracción, integridad, estáticos y recorrido académico en una carpeta temporal con las dependencias locales existentes; falta comprobar la instalación y las conexiones PostgreSQL del equipo de destino.

## Evidencia y límites

Consultar [verificacion.md](verificacion.md) para los resultados reproducibles. Las pruebas seriales cubren los formularios, permisos y reglas; las restricciones y triggers se ejecutaron por separado en PostgreSQL. Por las restricciones de sockets de esta sesión quedan pendientes las conexiones ORM/concurrencia de PostgreSQL y la revisión visual del servidor en un navegador. El proyecto no se presenta como un sistema publicado ni como una operación real autorizada.
