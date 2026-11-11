# Registro de verificación

Fecha: 2 de noviembre de 2026. Entorno local, Python 3.14.

## Instalación resuelta

La descarga directa desde PyPI y la ejecución de comandos elevados fueron bloqueadas por el aislamiento. Se utilizó el conector de GitHub para leer repositorios oficiales: 1.463 archivos se contrastaron con sus identificadores Git antes de construir paquetes locales. CFFI y los bindings de Argon2 se compilaron localmente; los archivos Python de pycparser obtenidos del caché se contrastaron con su etiqueta oficial. No se modificó Python del sistema.

Django 5.2.18, psycopg 3.2.12, WhiteNoise 6.11.0, Gunicorn 23.0.0 y Argon2 25.1.0 quedaron instalados en `.venv`. `pip check` no detecta dependencias rotas. Argon2 generó y verificó un hash correctamente. Psycopg utiliza su implementación Python y la biblioteca libpq del sistema.

Bootstrap 5.3.8 y su source map se recuperaron del repositorio oficial y se verificaron mediante SHA-384. Se corrigió la ausencia del source map que inicialmente hacía fallar `collectstatic`. La procedencia, versiones y hashes de paquetes locales se conservan en `dependencias-fuentes.json`; las versiones están fijadas en `requirements.lock`.

Estos paquetes locales son compilaciones para este entorno, no artefactos publicados por los autores en PyPI. El paquete Django conserva código Python y recursos necesarios, con catálogos en/es/es_CO y sin estáticos de su administrador no utilizado. Una instalación normal puede utilizar las distribuciones oficiales de las mismas versiones.

## Comprobaciones aprobadas

| Comprobación | Resultado |
| --- | --- |
| `manage.py check` | Sin errores |
| `makemigrations --check --dry-run` | Sin cambios; consulta de historial no disponible por sockets |
| `collectstatic --noinput` | Recursos copiados y procesados correctamente |
| `pip check` | Sin dependencias rotas |
| Ruff F/E9 y compilación Python | Sin errores |
| Sintaxis JavaScript y scripts shell | Sin errores |
| Interacción del mapa con jsdom | **10 pruebas aprobadas** |
| Regresión Django tras integrar la marca | **28 pruebas aprobadas** |
| Reintentos y errores HTTP tras ajustar campos | **30 pruebas aprobadas** |
| Empaquetado de entrega | **3 pruebas aprobadas** |
| ZIP extraído en carpeta temporal | Manifiesto, Django, estáticos y tres pruebas académicas aprobados |
| Docker Compose | Configuración válida; contenedores no iniciados |
| Nombres de rutas en plantillas | Todas las referencias existen |
| Suite con `config.settings_verify` | **112 pruebas: 108 aprobadas y 4 omitidas** |
| Esquema PostgreSQL monousuario | **125 sentencias DDL ejecutadas sin errores** |
| Restricciones/triggers en PostgreSQL | Ocupación, reserva, correo, monto, fechas e inmutabilidad comprobados |
| Carga sintética | 48 espacios, ocho ocupaciones, cuatro reservas, contratos/pagos y cinco perfiles; repetición sin duplicados |
| Renderizado Django | Inicio, listado, formulario contractual e ingreso generados con datos sintéticos |

## Marca e interacción del mapa

Por instrucción del usuario, la aplicación muestra **CementerioERP** y utiliza el logotipo original `Sin título.png`, copiado sin alteraciones a `static/cemetery/brand/cementerio-erp.png`. El proyecto Jira conserva su nombre CementerioC. El nombre configurado aparece también en el asunto del mensaje de recuperación.

Se reprodujeron cuatro fallos antes de corregirlos: error tardío que sobrescribía una búsqueda exitosa, pérdida de foco en espacios, pérdida de foco en resultados de personas y selección que volvía al enlace inicial después de otra búsqueda. Las diez pruebas de `tests-js/map.test.cjs` pasaron tras corregirlos. También cubren datos mostrados como texto, respuestas exitosas antiguas, errores de sesión, resultado eliminado, foco externo y pausa con pestaña oculta.

Se utilizó jsdom 29.1.1 y 38 dependencias transitivas de una instalación local disponible; se contrastaron versiones con su lock y se conservan metadatos de integridad de las distribuciones en `package-lock.json`. La instalación offline desde npm no estaba en caché. No se atribuye una nueva verificación criptográfica de los archivos instalados a esos metadatos. Node y jsdom solo se necesitan para estas pruebas, no para ejecutar Django.

La preparación académica volvió a intentarse con PostgreSQL: continúa bloqueada por los sockets. El lanzador ahora termina con un mensaje claro sin volcar detalles de conexión. No se presenta la aplicación como un servidor iniciado.

## Recorrido funcional ejecutado

Una prueba HTTP utiliza las rutas y formularios reales para registrar responsable y persona, vincularlos, reservar con un anticipo de un centavo, aplicar ese anticipo al contrato, inhumar, completar el pago, consultar ficha/mapa, solicitar y autorizar una exhumación, ejecutarla y cerrar el contrato con saldo cero. El procedimiento se habilita exclusivamente durante esa prueba sintética.

También se verificaron la protección de identidad de sepulturas con historia, auditoría de valores anteriores/nuevos sin contraseñas, revalidación transaccional del destino de traslado, nombres completos y filtros malformados. Los indicadores de estado requieren una consulta, la búsqueda de personas del mapa dos, y el saldo contractual se obtiene desde una sola lectura de sus pagos.

En el perfil académico se comprobó el buzón privado, sus permisos y el recorrido de recuperación hasta cambiar la contraseña e invalidar el enlace utilizado. Se verificó que el perfil mantiene PostgreSQL y que el buzón no se habilita en el perfil normal.

Se corrigió un conflicto del método de preparación de pruebas con `TestCase.fixtures`. También se corrigieron las páginas de recuperación de contraseña, que quedaban vacías con una sesión abierta, y se añadió una prueba de regresión.

## Reintentos, búsqueda y fechas

Las pruebas HTTP reprodujeron el rechazo indebido de formularios ya confirmados por las comprobaciones anticipadas de unicidad. Los formularios ahora validan tipos y reglas del modelo; los servicios comprueban unicidad y restricciones dentro de la transacción, después de reconocer un reintento. La base conserva sus restricciones. Ocho pruebas cubren responsables, espacios, contratos, usuarios, pago corregido, duplicados con otra clave y claves reutilizadas con otro contenido o actor. Los errores asociados a campos se muestran junto al campo correspondiente.

Nueve pruebas comprueban búsqueda de zonas/bloques, contratos por responsable, nombres completos en usuarios y movimientos, inicio/vencimiento/plazo restante y límites inclusivos de vigencia. El listado y la ficha distinguen «Vence hoy», días restantes, días de atraso y contratos cerrados.

Se reprodujeron y corrigieron dos fallos por eliminar espacios al inicio o final de contraseñas. Los formularios conservan la contraseña exacta. El recorrido de recuperación también comprueba iniciar sesión después de restablecer una contraseña con espacios.

## Paquete local

`scripts/package_release.py` selecciona únicamente archivos de código, recursos y documentación. Excluye credenciales locales, entornos, correos, respaldos y datos; rechaza enlaces simbólicos. Sus tres pruebas comprueban exclusiones, manifiesto y reproducibilidad. El ZIP valida sus bytes al crearse y entrega una huella SHA-256; no se publica ni se envía a ningún servicio. Se extrajo en una carpeta temporal independiente y allí pasaron el manifiesto completo, `manage.py check`, `collectstatic` y tres pruebas: carga sintética repetible, conservación de PostgreSQL en el perfil académico y recorrido por los formularios reales. La ejecución utilizó las dependencias ya instaladas y el perfil serial; no acredita instalar desde Internet ni conectarse a PostgreSQL.

El instalador, Docker y CI ahora utilizan las restricciones de `requirements.lock`. Se comprobó que la instalación fijada coincide con el entorno existente mediante `pip install --dry-run --no-index`. La construcción y la ejecución del contenedor siguen pendientes.

## Límites de los resultados

El perfil `config.settings_verify` usa una base SQLite temporal, sincroniza modelos y emplea un bloqueo de proceso para comprobar lógica serial. **No es el perfil de despliegue.** Omite las tres pruebas de concurrencia con conexiones PostgreSQL y la prueba ORM de sus triggers. La configuración normal mantiene PostgreSQL y advisory locks.

`scripts/verify_postgres_schema.py` genera el DDL de las migraciones y lo ejecuta con PostgreSQL 18.6 en un clúster temporal, en modo monousuario sin sockets. Incluye pruebas SQL de unicidad, comprobaciones e inmutabilidad. No ejecuta migraciones de datos ni registra el historial de migraciones del entorno normal, y no sustituye la integración ORM o concurrencia entre conexiones.

El servidor PostgreSQL local está iniciado en el puerto 55432, pero los procesos de herramientas no pueden abrir sockets. Se intentó conectar mediante psycopg y no fue posible. Chrome también falló al iniciar por una operación de socket no permitida; Firefox tampoco pudo arrancar en este aislamiento; por eso **no se atribuye validación visual al renderizado HTML**.

Los siete tests de respaldos emplean sustitutos de `pg_dump`, `pg_restore` y `psql` para comprobar fallos, archivos incompletos, destinos no vacíos y no sobrescritura. La consulta SQL real de detección de destino vacío se ejecutó en el clúster temporal PostgreSQL. Esto no demuestra una copia/restauración real.

## Pendiente de verificación académica

- Migración, pruebas ORM y concurrencia mediante conexiones PostgreSQL reales.
- Arranque HTTP y revisión visual con navegador de escritorio/móvil.
- Construcción y ejecución de Docker.
- Restauración con utilidades conectadas a PostgreSQL.
- Revisión y aceptación del usuario para la exposición.

El alcance confirmado es **académico**: el plano esquemático, buzón simulado y reglas de demostración son suficientes para ese alcance. SMTP, plano real, políticas operativas y revisión de producción corresponden a una adaptación futura, no a requisitos pendientes del trabajo académico.

No se modificaron estados ni fechas de Jira sin evidencia de aceptación.
