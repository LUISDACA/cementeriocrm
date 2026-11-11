# Trazabilidad con Jira

Fuente: proyecto [CementerioC](https://fluttergrupolms.atlassian.net/jira/software/projects/CM), 89 incidencias leídas el 2 de noviembre de 2026. Alcance académico confirmado por el usuario. La evidencia ejecutada y sus límites se registran en `verificacion.md`; los estados de Jira no se modificaron.

| Historia | Implementación | Verificación prevista |
| --- | --- | --- |
| [CM-7](https://fluttergrupolms.atlassian.net/browse/CM-7) Iniciar sesión | `views.sign_in/sign_out`, `forms.SignInForm`, middleware de sesión, recuperación de Django | Sesión, inactivo, credenciales, caducidad, CSRF y redirección segura |
| [CM-8](https://fluttergrupolms.atlassian.net/browse/CM-8) Usuarios | `User`, `save_user`, formularios y listado | Correo normalizado único, hash y último administrador |
| [CM-9](https://fluttergrupolms.atlassian.net/browse/CM-9) Roles | `permissions.py`, controles en vistas y servicios | Denegaciones directas y cambio de rol sin reingreso |
| [CM-10](https://fluttergrupolms.atlassian.net/browse/CM-10) Registrar sepultura | `Zone`, `Block`, `Space`, `save_space` | Código/ubicación únicos, validación y revisión de edición |
| [CM-11](https://fluttergrupolms.atlassian.net/browse/CM-11) Consultar sepulturas | `queries.py`, listado paginado, `space_detail` | Filtros, privacidad, estado vacío y navegación |
| [CM-12](https://fluttergrupolms.atlassian.net/browse/CM-12) Estado | `Space.status`, `change_condition`, `Event` | Impedir liberación administrativa, reserva vigente y edición obsoleta |
| [CM-13](https://fluttergrupolms.atlassian.net/browse/CM-13) Fallecidos | `Person`, formulario, `save_person`, ficha | Homónimos, documento opcional, fechas y auditoría |
| [CM-14](https://fluttergrupolms.atlassian.net/browse/CM-14) Asociación | `Occupancy`, fichas de persona/espacio, `bury` | Una ubicación vigente, navegación y conservación histórica |
| [CM-15](https://fluttergrupolms.atlassian.net/browse/CM-15) Responsables | `Responsible`, `PersonResponsible`, `link_responsible` | Contacto reutilizable, vínculo principal y permisos |
| [CM-16](https://fluttergrupolms.atlassian.net/browse/CM-16) Mapa | `map.html`, `app.js`, `map_data` | Identidad de espacio, zoom, desplazamiento, plano esquemático académico |
| [CM-17](https://fluttergrupolms.atlassian.net/browse/CM-17) Estados del mapa | Estado derivado compartido, texto/color, sondeo | Consistencia JSON/espacio, error sin éxito falso |
| [CM-18](https://fluttergrupolms.atlassian.net/browse/CM-18) Búsqueda del mapa | Filtros, selección de homónimos y ubicación vigente | Sin marcador falso y sin datos personales al perfil Consulta |
| [CM-19](https://fluttergrupolms.atlassian.net/browse/CM-19) Contratos | `Contract`, creación, edición limitada y cierre | Vigencia, unicidad activa, reserva aplicada y conservación histórica |
| [CM-20](https://fluttergrupolms.atlassian.net/browse/CM-20) Fechas contractuales | `Contract.validity`, filtros y dashboard | Fronteras de fechas; vencimiento no libera ocupación |
| [CM-21](https://fluttergrupolms.atlassian.net/browse/CM-21) Pagos | `Payment`, registro/anulación, recibo, saldo decimal | Reintento, concurrencia, sobrepago, permisos y conservación original |
| [CM-22](https://fluttergrupolms.atlassian.net/browse/CM-22) Inhumación | `bury`, ocupación y evento atómicos | Doble ocupación concurrente, contrato obligatorio y rollback |
| [CM-23](https://fluttergrupolms.atlassian.net/browse/CM-23) Exhumación/traslado | Solicitud/autorización/ejecución/cancelación y bloqueo configurable | Revalidación de destino, traslado atómico, ejecución autorizada; flujo académico habilitado en perfil separado |
| [CM-24](https://fluttergrupolms.atlassian.net/browse/CM-24) Historial | `Event`, línea de tiempo paginada, filtros y triggers | Fechas/tipo, orden estable, permisos y eventos inmutables |

Las 54 subtareas quedan vinculadas a sus historias originales en `jira/requisitos.json`; no se cuentan como historias independientes terminadas.

## Preparación y cierre

- **CM-80/81:** acuerdos confirmados en `reglas.md`; alcance académico confirmado; reglas simuladas documentadas.
- **CM-82/83:** Django instalado, versiones de instalación fijadas y comprobaciones aprobadas; modelo/migraciones coinciden. DDL probado en PostgreSQL monousuario; migración mediante ORM y arranque HTTP pendientes por sockets.
- **CM-84:** interfaz y plano esquemático escritos. Plano esquemático suficiente para el alcance académico; revisión de navegador pendiente.
- **CM-85:** `seed_demo` ejecutado con 48 espacios, ocho ocupaciones y cuatro reservas sintéticas en el perfil local; cinco perfiles ficticios disponibles; no se requiere carga real para la exposición.
- **CM-86:** 108 pruebas seriales aprobadas, cuatro específicas de PostgreSQL omitidas; pruebas por conexiones pendientes.
- **CM-87:** recorrido completo por formularios aprobado en perfil serial; falta repetir con ORM PostgreSQL y navegador.
- **CM-88:** respaldos/restauración y configuración incluidos; faltan restauración demostrada, medición y revisión de producción.
- **CM-89:** guion de exposición en `entrega-academica.md` y paquete local con manifiesto mediante `make package`; revisión y aceptación del usuario pendientes.

La marca visible fue cambiada a **CementerioERP** por instrucción del usuario; CementerioC (CM) conserva la trazabilidad original. CM-16/17/18 cuentan además con diez pruebas de interacción del JavaScript aprobadas en un DOM simulado.

No se cambian fechas ni se cierra trabajo en Jira automáticamente. La programación histórica de septiembre/noviembre debe reemplazarse por un calendario basado en capacidad y avance verificado.

Las comprobaciones HTTP de reintento cubren CM-8/10/15/19/21 y conservan resultados sin duplicar registros. CM-20 incorpora plazo restante y fronteras inclusivas de fechas. Las búsquedas de CM-11/13/23 también se verificaron por nombres completos y relaciones. Se conserva la diferencia entre evidencia serial y concurrencia real pendiente.
