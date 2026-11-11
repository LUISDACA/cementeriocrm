# Reglas de CementerioERP

Registro de decisiones al 2 de noviembre de 2026. El alcance original se conserva en `jira/requisitos.json`; estas decisiones posteriores lo precisan.

## Confirmado por el usuario

1. Django y PostgreSQL como base de la aplicación.
2. Cada sepultura admite **una sola persona**. Una persona no puede mantener simultáneamente dos ubicaciones vigentes.
3. **Se exige contrato para inhumar**. La implementación exige contrato activo, correspondiente al espacio y con vigencia que cubra la fecha registrada.
4. **Las reservas requieren dinero de por medio**. Crear una reserva exige registrar un anticipo positivo en la misma transacción.

5. **Proyecto académico**, confirmado por el usuario: datos ficticios, mapa esquemático y procedimientos simulados.

## Comportamiento propuesto y documentado

Estas decisiones definen el comportamiento de la demostración académica. No se exige información de un cementerio real para presentar el proyecto.

| Tema | Comportamiento implementado | Situación |
| --- | --- | --- |
| Vigencia de reserva | Fecha explícita elegida por tesorería; válida hasta el final de ese día en Bogotá | Revisar política de plazo/monto mínimo |
| Anticipo | Se aplica una vez al contrato del mismo espacio y responsable, sin duplicar el pago | Revisar política financiera |
| Vencimiento/cancelación | Libera la reserva, conserva el pago para conciliación; no confisca ni devuelve dinero automáticamente | Devoluciones y penalidades pendientes |
| Contrato vigente | Inicio/vencimiento inclusivos; estado activo; un contrato activo por espacio | Revisar renovaciones y documentos |
| Saldo | Valor contractual menos pagos válidos; dos decimales; sin sobrepagos | Política conservadora propuesta |
| Corrección de pagos | Anulación con motivo, conservando original y auditoría; una anulación no equivale a devolución | Confirmar responsables y procedimiento |
| Anticipos de reserva | No se anulan por el formulario genérico de pagos | Conciliación y devolución pendientes |
| Registro de devolución | Tesorería registra solo una devolución ya ejecutada, con monto, referencia, motivo y fecha; el total no supera el anticipo | La política determina si procede; la aplicación no transfiere dinero |
| Vencimientos | Umbral configurable, inicialmente 30 días | Configurar con el cementerio |
| Moneda | COP configurable antes de comenzar la carga real; no mezclar monedas en la misma base | Confirmar moneda |
| Datos iniciales | Carga manual y demostración sintética; sin importación masiva automática | Confirmar necesidad de importación |
| Plano | Esquema SVG con posiciones explícitas por espacio | Fuente real y geometría pendientes |
| Matriz de permisos | Cinco perfiles con mínimo acceso necesario | Revisar con responsables operativos |

## Exhumación y traslado: simulación académica

El usuario pidió una recomendación para estas condiciones. Se implementa el siguiente flujo como propuesta:

1. **Solicitud:** persona y ubicación vigente, tipo, motivo, responsable de la solicitud y fecha propuesta. El espacio sigue ocupado.
2. **Autorización:** administración verifica condiciones y registra una referencia a los documentos y autorizaciones correspondientes.
3. **Ejecución:** operaciones confirma fecha real posterior a autorización; el sistema actualiza origen, destino e historial de forma atómica.
4. **Cancelación:** solo para solicitudes pendientes; requiere motivo y no modifica ocupación.

El traslado interno requiere espacio distinto y disponible y contrato vigente de destino cuyo responsable esté vinculado a la persona. La disponibilidad se vuelve a comprobar al ejecutar. El contrato de origen conserva su historia; no se cierra ni se liquida automáticamente.

**En `config.settings_academic` la autorización y ejecución están habilitadas para simulación**, con aviso visible. En el perfil normal permanecen bloqueadas por defecto, mediante `CEMETERY_MOVEMENTS_APPROVED=0`, porque siguen pendientes de precisar: municipio/jurisdicción, documentos obligatorios, quién puede autorizar, condiciones temporales y destino de los restos. No se presume un plazo legal de exhumación ni una autorización por saldo o antigüedad.

Antes de habilitar esa configuración, registrar la validación del responsable del cementerio, definir los requisitos aplicables y ampliar las validaciones específicas si el proceso requiere algo más que una referencia documental. El interruptor no sustituye esos controles.

## Estados y ocupación

- **Disponible:** sin ocupación ni reserva vigente y condición administrativa disponible.
- **Ocupada:** existe una ocupación vigente. Solo un movimiento ejecutado puede terminarla.
- **Reservada:** existe una reserva pagada vigente, sin ocupación.
- **Mantenimiento / Fuera de servicio:** condición administrativa que impide inhumar o reservar.

No se cambia a Ocupada desde un selector. Vencer un contrato no libera espacios. No se admiten cambios administrativos de una sepultura con ocupación o reserva vigente. Todas las correcciones preservan los eventos originales.

## Conservación de identidad y auditoría

Si un espacio tiene contratos, reservas u ocupaciones actuales o históricas, no se cambia su código, bloque, fila, número o tipo. Se pueden corregir notas y coordenadas del plano conservando valores anteriores y nuevos. Las correcciones de personas, responsables y cuentas también conservan estos valores en la auditoría; contraseñas y tokens no se incluyen. Solo Administración consulta el detalle de auditoría.
