# Guía de uso

Para la demostración académica usa [entrega-academica.md](entrega-academica.md): incluye preparación automática, cinco cuentas y guion de exposición.

## Preparación inicial

Administración crea zonas y bloques; después registra los espacios con códigos únicos, fila, número, tipo y coordenadas del esquema. Cada espacio tiene capacidad de una persona. El proyecto académico utiliza un plano esquemático con datos ficticios. Una adaptación a uso real requeriría contrastar sus posiciones con el plano del cementerio.

Los perfiles se crean en **Usuarios y permisos**. El ingreso utiliza correo y contraseña. Se pueden desactivar usuarios y cambiar su perfil sin eliminar el historial de sus acciones.

## Registro de familiares

Cualquier persona puede abrir **¿Eres familiar? Crea tu cuenta** desde el ingreso. Debe indicar nombre, correo, documento y teléfono, elegir una contraseña y confirmar el correo recibido. Hasta confirmar el correo no puede iniciar sesión.

La cuenta entra a un portal privado sin acceso al mapa, al directorio ni a otras familias. Para mostrar contratos y facturas existentes, administración coteja presencialmente el documento y vincula la cuenta desde **Configuración → Cuentas familiares**. La vinculación se registra en auditoría. La familia puede consultar los abonos y abrir sus recibos internos; también descargar las copias firmadas que estén adjuntas a sus contratos. Cada descarga vuelve a comprobar el vínculo del responsable. En modo académico, el mensaje de confirmación aparece en **Correos simulados**.

El enlace de confirmación vence a los tres días; desde la pantalla de enlace vencido se puede solicitar otro. Administración puede desactivar o reactivar cuentas ya confirmadas desde el mismo listado, con constancia de auditoría.

## Recorrido principal

1. **Registrar responsable:** guardar identidad y contacto una sola vez. El mismo responsable se puede asociar a varias personas.
2. **Registrar persona fallecida:** nombres, apellidos y fecha de fallecimiento; documento y nacimiento son opcionales. No se usa el nombre como identificador único: se permiten homónimos.
3. **Vincular responsable:** desde la ficha de la persona, seleccionar el contacto, parentesco y, si corresponde, responsable principal.
4. **Reserva opcional:** tesorería elige un espacio disponible, responsable, fecha límite, anticipo positivo, método y referencia. No existe reserva confirmada sin el pago inicial.
5. **Crear contrato:** número, espacio, responsable, valor, fechas y condiciones. Si existe reserva vigente del mismo responsable, administración o tesorería aplica el anticipo automáticamente una sola vez.
6. **Registrar inhumación:** operaciones selecciona persona, espacio y contrato, registra fecha/hora y observaciones con responsable operativo. Se verifica contrato vigente, vínculo del responsable y disponibilidad. La ubicación y el historial se confirman juntos.
7. **Registrar pagos posteriores:** tesorería elige el contrato y registra valor, método, referencia y fecha. El sistema impide pagos por encima del saldo. El recibo interno se puede imprimir.
8. **Consultar ficha o mapa:** búsqueda por código y filtros de zona, bloque, tipo y estado. La búsqueda por persona muestra todas las coincidencias; si no tiene ubicación vigente lo indica sin inventar un marcador.

## Contratos, facturas y gastos

Al crear el contrato, parte de las condiciones propuestas y edítalas para acordar los detalles. Se genera una factura interna por el valor contractual. Puedes fijar una cuota mensual familiar para mantenimiento de zonas comunes; el contrato aclara que la familia conserva el cuidado de la sepultura particular. Administración o tesorería imprimen el contrato y completan las firmas manuscritas. Después pueden adjuntar en el expediente la copia escaneada firmada en PDF, PNG o JPEG (máximo 8 MB). Cada reemplazo conserva su versión anterior, registra quién la cargó y calcula una huella SHA-256; solo perfiles con acceso a contratos pueden descargarla.

Para cobrar abonos parciales, abre la factura del contrato, usa **Registrar abono** y selecciona la factura y el método. Cada abono crea un recibo imprimible y actualiza el saldo de esa factura. Para emitir las cuotas mensuales en el perfil académico ejecuta `make billing-month`; opcionalmente indica `MONTH=AAAA-MM`. Repetir la emisión no duplica cuotas.

Registra pagos de impuestos, energía, agua y limpieza pública desde **Gastos operativos**. Abre el consecutivo del gasto para adjuntar la factura del proveedor o el comprobante; se aceptan PDF, PNG y JPEG de hasta 8 MB, y cada reemplazo conserva el historial. Las facturas y recibos son internos para la demostración y no sustituyen documentos tributarios oficiales. La copia adjunta es evidencia interna: el sistema no verifica identidad ni autenticidad y no genera firma electrónica. La plantilla contractual requiere revisión legal antes de aplicarse en un cementerio real.

El tablero financiero resume cobros, devoluciones registradas, gastos pagados y facturas pendientes/vencidas del mes calendario actual; el flujo neto resta devoluciones y gastos de los cobros. Este flujo neto es una vista operativa de los registros y no reemplaza la contabilidad formal. El enlace **Cartera y mora** organiza los saldos por vencer y por rangos de días vencidos, permite abrir la factura y exportar el informe completo a CSV. **Libro de caja** reúne cobros, devoluciones y gastos del mes elegido, enlaza cada movimiento con su recibo, reserva o soporte, y exporta sus movimientos a CSV.

Desde el listado de sepulturas puedes abrir **Capacidad por bloque** para consultar conteos actuales por zona, comparar ocupación, reservas, disponibilidad y mantenimiento, y descargar el resumen CSV. Las cifras se calculan con ocupaciones y reservas vigentes.

Administración y Oficina pueden importar hasta 5.000 sepulturas desde **Sepulturas → Importar CSV**. La carga crea registros nuevos y no modifica ni elimina los existentes. Zona y bloque deben estar creados primero; códigos, fila/número, tipo, condición y coordenadas se revisan en una vista previa antes de confirmar. Con un plano cargado, cada fila debe incluir coordenadas x,y dentro de la imagen.

## Mapa

La demostración presenta un lote ilustrativo con acceso, senderos, árboles y sectores agrupados por bloque. Cada marcador corresponde al identificador de un espacio, lleva su código y estado, y conserva su posición al actualizar los datos: verde Disponible, rojo Ocupada, amarillo Reservada, azul Mantenimiento y gris Fuera de servicio. Se puede acercar/alejar, desplazarse y abrir la ficha.

El mapa consulta cambios cada 15 segundos mientras la pestaña está visible. Un error conserva los datos previos con advertencia de que pueden estar desactualizados. La vista se limita a 1.000 espacios por consulta e indica cuándo hay que filtrar. Para operación sin JavaScript se conserva el listado del servidor.

Administración y Oficina pueden cargar un plano PNG desde **Cargar imagen del plano**. Luego, quienes tengan permiso de sepulturas pueden activar **Editar ubicaciones** en el mapa y arrastrar cada marcador hasta su posición; el movimiento se guarda al soltar, comprueba límites, cruces con otras lápidas y cambios concurrentes, y deja auditoría. Para grandes lotes también está **Ajustar plano por CSV**: descarga la plantilla, usa `x,y` como píxeles desde la esquina superior izquierda de cada lápida, revisa la vista previa y confirma. Incluye todas las sepulturas para que ninguna conserve posiciones del esquema anterior. La imagen se conserva en la base de datos y solo se sirve a usuarios autenticados.

## Exhumación y traslado

En el perfil académico se simula el flujo completo: solicitud, autorización por Administración con referencia ficticia y ejecución por Operaciones. Se puede dejar vacía la fecha/hora de ejecución para usar el momento de confirmar. En el perfil normal la autorización y ejecución permanecen bloqueadas hasta validar y configurar las condiciones operativas.

Solicitar o autorizar no libera una sepultura. Solo ejecutar termina la ocupación. El traslado interno exige destino disponible y contrato vigente de destino; conserva todas las ubicaciones anteriores. Un fallo revierte la operación completa. El contrato de origen no se liquida automáticamente.

Los contratos muestran inicio, vencimiento y plazo restante. El día de vencimiento todavía es válido y muestra «Vence hoy»; después se indica cuántos días han transcurrido. El cierre deja de mostrar plazo restante.

## Correcciones

- **Espacio:** editar notas y posición del plano o cambiar condición con motivo. Si tiene contratos, reservas u ocupaciones actuales o históricas, su identidad física no se puede cambiar. No se puede liberar una ocupación mediante un cambio administrativo.
- **Responsables:** actualizar el contacto conserva sus relaciones.
- **Contrato:** editar condiciones/vencimiento no elimina pagos ni movimientos. Un contrato ocupado no se cierra; se exige también saldo cero.
- **Pago:** anular con motivo conserva el original y recalcula saldo. No confirma una devolución. Los anticipos de reservas requieren conciliación específica.
- **Reserva:** cancelar conserva el pago; no hay confiscación ni devolución automática. Si la devolución ya se procesó por fuera del sistema, Tesorería puede registrarla en la ficha con importe, método, referencia, motivo y fecha. El total devuelto no puede superar el anticipo. Cada devolución tiene un comprobante interno imprimible. La aplicación solo deja constancia; no autoriza ni transfiere dinero.

## Errores y sesión

Los errores de formulario se muestran junto a los campos o al inicio. Si el registro cambió mientras estaba abierto, recarga antes de volver a guardar. Una operación fallida no debe dejar cambios parciales. Los campos se conservan para corregirlos. Reenviar una confirmación con la misma clave y contenido recupera su resultado; usar esa clave para otros datos se rechaza.

El acceso se limita según el perfil. Usa **Cerrar sesión** al terminar. Si olvidas la contraseña, solicita un enlace desde el ingreso; en el perfil académico Administración consulta el enlace en «Correos simulados» desde su sesión. El perfil normal requiere correo saliente configurado.

Administración puede abrir el detalle de Auditoría para ver valores anteriores y nuevos de las correcciones. Los eventos originales se conservan; las contraseñas nunca se incluyen en ese detalle.
