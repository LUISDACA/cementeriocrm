# Arquitectura y permisos

## Estructura

Monolito Django con PostgreSQL, plantillas del servidor y recursos estáticos locales. Los formularios HTML hacen POST con CSRF; llaman servicios del dominio que vuelven a comprobar permisos. El endpoint JSON del mapa es de solo lectura, autenticado y sin caché compartida.

Bootstrap 5.3.8 se instala con su CSS y source map, ambos verificados con SHA-384, y se sirve localmente. `scripts/vendor_bootstrap.py` reutiliza archivos válidos sin descargarlos otra vez. La generación de estáticos pasó. No hay solicitudes a CDN desde el navegador.

```
Navegador → rutas/vistas → formularios → servicios del dominio → PostgreSQL
                                     ↘ permisos / auditoría / historial
Mapa SVG ← JSON autenticado ← consultas de disponibilidad
```

## Entidades

| Entidad | Responsabilidad |
| --- | --- |
| User | Correo único normalizado, contraseña con hash, perfil, actividad |
| Zone / Block / Space | Catálogo físico, ubicación, código único, condición y posición del plano |
| Person / Responsible / PersonResponsible | Fallecido, contacto reutilizable y parentesco por vínculo |
| Reservation | Espacio reservado, responsable, fecha límite, estado; pago inicial en la misma operación |
| Contract | Espacio, responsable, valor, moneda, vigencia y condiciones históricas |
| Payment | Pago original, relación con contrato/reserva y datos de anulación |
| Occupancy | Persona, espacio, contrato, inicio y fin; unicidad parcial para ocupación vigente |
| Movement | Solicitud, autorización, ejecución/cancelación y destino |
| Event / Audit | Historial del espacio y registro de acciones; triggers impiden actualización/eliminación |
| Command | Clave UUID, huella HMAC de la operación y resultado para reintentos |
| LoginThrottle | Límites persistentes de intentos por cuenta e IP |

## Consistencia

Todas las escrituras del dominio usan `transaction.atomic()` y un advisory lock de PostgreSQL compartido. Además se bloquean las filas pertinentes. Es una elección deliberada para el volumen de un MVP: serializa escrituras entre procesos, evita carreras entre entidades y permite lecturas concurrentes. No está dimensionada para alto volumen; medir y particionar los bloqueos por agregado si la carga lo exige.

`locks.transaction_lock` mantiene ese comportamiento en PostgreSQL. Existe una excepción explícita y exclusiva de `config.settings_verify`: un bloqueo de proceso para pruebas seriales con SQLite. Este perfil no se utiliza en el servidor normal y no acredita concurrencia entre conexiones ni procesos. Las cuatro pruebas específicas de PostgreSQL se omiten con una razón visible en ese perfil.

Restricciones de la base impiden dos ocupaciones vigentes por persona/espacio, dos reservas activas del mismo espacio, dos contratos activos, duplicados de código/correo y fechas/montos estructuralmente inválidos. Los servicios verifican relaciones, permisos, vigencia y saldo dentro de la transacción.

Los reintentos con la misma clave, actor y contenido recuperan el mismo resultado. Los formularios no adelantan las comprobaciones de unicidad: los servicios ejecutan `full_clean()` y conservan las restricciones SQL dentro de su transacción. Así un formulario repetido alcanza el resultado guardado antes de intentar crear otro registro. Una clave reutilizada con otro contenido se rechaza. La huella HMAC evita almacenar contraseñas en texto o como hashes rápidos verificables sin el secreto del servidor. Las contraseñas de acceso usan Argon2 y se conservan exactamente como se escriben, incluidos espacios al inicio/final.

Las fichas de espacio incluyen una revisión para rechazar ediciones simultáneas obsoletas. La edición de contratos conserva su número, relaciones, moneda y valor original; permite revisar condiciones y vencimiento con auditoría. Las correcciones de monto o renegociaciones requieren un flujo de enmiendas adicional si se incluyen en el alcance final.

## Matriz de permisos propuesta

Todos los perfiles operativos activos pueden ver disponibilidad y ubicación física. “Consulta” no recibe nombres, documentos, contactos, pagos ni usuarios en las vistas ni en el JSON. La cuenta “Familiar” tiene acceso únicamente al portal de su perfil; requiere correo confirmado y vinculación administrativa cotejada para consultar contratos y facturas propios.

| Acción | Administrador | Administrativo | Tesorería | Operaciones | Consulta |
| --- | --- | --- | --- | --- | --- |
| Ver espacios y mapa | Sí | Sí | Sí | Sí | Sí |
| Crear/editar espacios y condición | Sí | Sí | — | — | — |
| Registrar/editar fallecidos | Sí | Sí | — | Sí | — |
| Leer personas y contactos | Sí | Sí | Sí | Sí | — |
| Mantener responsables/vínculos | Sí | Sí | Sí | Sí | — |
| Crear/editar/cerrar contratos | Sí | Sí | Sí | — | — |
| Consultar contratos y recibos | Sí | Sí | Sí | — | — |
| Reservar con anticipo y registrar/anular pagos | Sí | — | Sí | — | — |
| Aplicar un anticipo a contrato | Sí | — | Sí | — | — |
| Inhumar / solicitar / ejecutar movimientos | Sí | — | — | Sí | — |
| Autorizar exhumación/traslado | Sí | — | — | — | — |
| Usuarios, roles y auditoría | Sí | — | — | — | — |

Administración conserva al menos una cuenta administradora activa. La cuenta inicial se crea con `createsuperuser`, sin contraseña incrustada. Los cambios de rol se aplican en la siguiente solicitud; desactivar impide acceso con sesiones existentes. Cambio de contraseña invalida las sesiones anteriores mediante el mecanismo estándar de Django.

El registro familiar es público, pero crea cuentas inactivas hasta que se confirme el correo. La vinculación a un responsable requiere cotejo presencial de identificación; solo Administración puede realizarla y queda auditada. El middleware bloquea a ese rol de las rutas operativas y financieras generales.

## Sesiones y recuperación

Sesiones del servidor: 30 minutos sin solicitudes y ocho horas de duración absoluta. El sondeo del mapa cuenta como solicitud, por lo que el límite absoluto evita extender indefinidamente una sesión abierta. Cookies HttpOnly y SameSite; cookies seguras, HTTPS y HSTS en producción.

Ingreso limitado a cinco fallos por cuenta y 30 por IP en ventanas de 15 minutos. Los errores no distinguen cuentas inexistentes e inactivas. La recuperación usa tokens de Django y SMTP en el perfil normal, o un buzón local privado visible solo para Administración en el perfil académico, con máximo tres solicitudes por correo y 12 por IP cada 15 minutos, manteniendo una respuesta genérica. Comprobar su entrega y revisar los límites del proxy antes del cierre.

No se publica un administrador genérico con acceso directo al ORM: todas las operaciones de negocio pasan por servicios. No exponer una consola de base de datos a usuarios finales. Utilizar roles de base con privilegios mínimos en despliegue.

## Recursos de interfaz y comprobaciones

El logotipo aprobado por el usuario se sirve como recurso local y conserva su archivo original. `CEMETERY_NAME` controla el nombre visible y el asunto de recuperación; el proyecto de requisitos en Jira mantiene CementerioC.

El mapa protege sus actualizaciones con un número de solicitud para descartar respuestas antiguas, conserva selección y foco durante el sondeo y suspende las solicitudes pendientes al ocultar la pestaña. Sus diez pruebas se ejecutan con Node/jsdom; no sustituyen la comprobación visual del navegador. `package-lock.json` fija las dependencias de desarrollo y el servidor sigue sin requerir Node.
