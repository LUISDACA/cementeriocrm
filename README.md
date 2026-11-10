# CementerioERP

Proyecto académico confirmado por el usuario. Nombre de la aplicación: **CementerioERP**; proyecto de requisitos en Jira: **CementerioC (CM)**. El logotipo fue proporcionado y aprobado por el usuario. Aplicación web en español para administrar sepulturas, personas fallecidas, responsables, contratos, reservas con anticipo, pagos, inhumaciones, exhumaciones/traslados, mapa e historial.

Base elegida con el usuario: **Django 5.2 LTS y PostgreSQL**. Interfaz renderizada en servidor con Bootstrap 5.3.8 instalado localmente, tema adaptable y JavaScript para mapa SVG, zoom, búsqueda y actualización. No necesita Node para ejecutar el servidor ni servicios de mapas externos.

## Estado real

La implementación inicial ya se ejecutó con Django 5.2.18. Se instalaron las dependencias en `.venv` desde fuentes oficiales verificadas y recursos locales; la procedencia y versiones están en [dependencias-fuentes.json](docs/dependencias-fuentes.json) y `requirements.lock`.

**Demostración:** ejecuta `make demo` con PostgreSQL accesible. Prepara cinco perfiles, datos ficticios, un lote ilustrado de 432 sepulturas, movimientos simulados y buzón local de recuperación. Si ya ejecutaste una versión anterior, el siguiente `make demo` agrega el lote automáticamente. Consulta el [guion de exposición](docs/entrega-academica.md).

El ingreso permite registro público de cuentas familiares con confirmación de correo. Estas cuentas solo ven su portal privado; administración debe cotejar el documento y vincular el registro antes de exponer contratos o facturas existentes. El portal ofrece los recibos propios y las copias firmadas asociadas al responsable vinculado.

Administración y Oficina pueden cargar un plano PNG privado y ubicar las lápidas encima con un CSV de coordenadas en píxeles. La importación muestra vista previa, valida límites/códigos y deja auditoría. El catálogo incluye un informe de capacidad por bloque y permite exportar el inventario e importar hasta 5.000 sepulturas por CSV, sin alterar registros existentes. El proyecto no trae la imagen del cementerio: para ver el lugar real, administración debe cargar el plano autorizado y ubicar todos los espacios.

También puedes ejecutar `make demo-map` para ampliar el mapa sin iniciar el servidor. Añade seis bloques ilustrativos, 384 sepulturas, 64 ocupaciones con nombres ficticios, 24 reservas y varios estados visibles. Los códigos siguen bloque, fila y número (por ejemplo, `C-101`). El comando solo se ejecuta con la configuración académica, conserva los registros existentes y puede repetirse sin duplicar códigos.

**Resultado actual:** comprobaciones de Django sin errores; modelo y migraciones coinciden; estáticos generados; 108 pruebas aprobadas en el perfil serial y cuatro omitidas; además, diez pruebas de interacción del mapa aprobadas. En PostgreSQL 18.6 se ejecutaron por separado las 125 sentencias DDL y se verificaron restricciones e inmutabilidad en un clúster temporal sin sockets. El recorrido completo por formularios y la carga de demostración también pasaron.

**Verificación pendiente:** faltan ORM y concurrencia con conexiones PostgreSQL reales y revisión visual en navegador. El alcance acordado es una demostración académica. Los sockets de esta sesión están restringidos. El perfil serial usa SQLite exclusivamente para diagnóstico; el servidor y la configuración normal siguen requiriendo PostgreSQL. Consulta los límites en [verificacion.md](docs/verificacion.md).

## Requisitos

- Python 3.12–3.14; el entorno comprobado usa Python 3.14 y Django 5.2.18.
- PostgreSQL 16 o posterior; usuario con permiso para crear la base de pruebas al ejecutar tests.
- Biblioteca cliente `libpq` para psycopg. En Ubuntu/Debian: paquete `libpq5`; Dockerfile la instala.
- Acceso a PyPI para instalar `requirements.txt`, o un repositorio local de ruedas compatible.
- SMTP solo para un uso posterior con correo externo; la demostración académica usa un buzón local.

## Ejecutar con Docker Compose

```bash
cp .env.example .env
```

`bootstrap.py` genera `.env` y conecta `DATABASE_URL` con `POSTGRES_PASSWORD`. PostgreSQL queda disponible en `127.0.0.1:55432` para ejecutar los comandos locales. No publiques `.env`.

```bash
docker compose up -d db
make demo
```

La base conserva sus datos en un volumen de Docker. Para ejecutar toda la aplicación dentro de contenedores, usa el perfil indicado en [la guía académica](docs/entrega-academica.md).

Abre **http://127.0.0.1:8000**. Compose está preparado para desarrollo local: `DEBUG=1`, puerto limitado a localhost y movimientos pendientes de aprobación. No publicarlo tal cual en Internet.

## Ejecutar sin Docker

1. Crea una base PostgreSQL dedicada, por ejemplo `cementerio`.
2. Copia `.env.example` a `.env`; configura el secreto, `DATABASE_URL` y `DJANGO_DEBUG=1`.
3. Instala y prepara:

```bash
python3 scripts/bootstrap.py
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

El instalador se detiene si falta un paquete o no se puede conectar a la base. Los paquetes se instalan en `.venv`, sin modificar Python del sistema. El entorno de esta sesión ya tiene los paquetes instalados; su conexión de ORM sigue pendiente por la restricción de sockets.

## Demostración con datos sintéticos

En desarrollo, define temporalmente `DEMO_ADMIN_PASSWORD` con una contraseña de al menos 12 caracteres que cumpla los validadores y ejecuta:

```bash
.venv/bin/python manage.py seed_demo
```

El comando crea 48 espacios en un plano esquemático, ocho ocupaciones, cuatro reservas pagadas y ejemplos de contratos, pagos, mantenimiento e historial. Crea cinco perfiles: `admin`, `oficina`, `tesoreria`, `operaciones` y `consulta`, todos bajo `@example.test`. La contraseña es la que definiste, no una credencial predeterminada. Usa `make demo` para habilitar las operaciones simuladas y el buzón de recuperación. No modifica espacios existentes ni admite ejecutarse con `DEBUG=0`. Retira `DEMO_ADMIN_PASSWORD` del entorno después de usarla.

## Verificación

```bash
make check
make test
```

`make test` usa PostgreSQL y comprueba también concurrencia entre conexiones. Si el entorno no permite sockets, existen dos comprobaciones complementarias:

```bash
make test-serial
make schema-check
```

La primera verifica reglas, formularios y HTTP en un perfil SQLite temporal; omite tres pruebas de concurrencia PostgreSQL y una de sus triggers. La segunda ejecuta el DDL de las migraciones y pruebas de restricciones/triggers en el motor PostgreSQL en modo monousuario, dentro de un clúster temporal nuevo. **No sustituyen la batería con ORM conectado a PostgreSQL ni la validación del navegador.**

Las pruebas de JavaScript son opcionales para ejecutar el servidor. Para verificarlas en otro entorno se necesita Node 22.13 o posterior de la rama 22, o Node 24 o posterior:

```bash
npm ci --ignore-scripts
make test-ui
```

El paquete de entrega también tiene tres pruebas de exclusión de credenciales, enlaces simbólicos e integridad, ejecutables con `make test-package`.

Las versiones de sus dependencias están fijadas en `package-lock.json`. Los tests ejecutan el JavaScript real con un DOM simulado; cubren respuestas fuera de orden, actualización periódica, selección, foco del teclado y errores de sesión. La revisión visual sigue siendo una comprobación independiente.

### Contratos y contabilidad académica

Los contratos nuevos parten de condiciones predefinidas que se pueden editar. Cada uno genera una factura interna del valor contractual; admite cuota familiar mensual, abonos parciales y recibos vinculados a la factura. El contrato se imprime con espacios para firmas manuscritas. El expediente permite adjuntar la copia escaneada firmada (PDF/PNG/JPEG), descargarla con permisos, conservar versiones previas y verificar su huella SHA-256. Esto no constituye firma electrónica ni verifica autenticidad. Cada mes se pueden generar las cuotas configuradas con `make billing-month` (usa `MONTH=2026-11` para elegir otro mes); el comando evita duplicar factura por contrato y periodo. Los gastos de impuestos, electricidad, agua, limpieza pública e insumos se registran en Administración y finanzas → Gastos operativos. Cada registro admite adjuntar factura o soporte PDF/PNG/JPEG privado, con versiones previas, auditoría y huella SHA-256.

El informe de cartera agrupa los saldos pendientes por antigüedad y permite exportarlos a CSV. El libro de caja mensual consolida cobros, devoluciones y gastos pagados para revisar el flujo neto operativo. En este perfil las facturas y recibos son documentos internos académicos, no documentos tributarios autorizados. La firma se recoge en el ejemplar impreso y requiere revisión de la normativa aplicable antes de cualquier uso real.

## Entrega local

```bash
make package
```

Genera `dist/CementerioERP-academico.zip` y su huella SHA-256. Incluye código, logotipo, dependencias fijadas, pruebas y guías; excluye `.env`, cuentas, correos simulados, bases, respaldos, entornos y `node_modules`. El ZIP contiene un manifiesto verificable:

```bash
# Después de extraer, desde la carpeta CementerioERP:
sha256sum --check MANIFEST.sha256
```

La instalación, el contenedor y CI utilizan `requirements.lock` como restricciones de versiones. El paquete requiere instalar dependencias y configurar PostgreSQL en su destino; no contiene un servidor ya iniciado.

## Documentación

- [Entrega académica](docs/entrega-academica.md): preparación, cuentas y guion de exposición.
- [Reglas y decisiones](docs/reglas.md): acuerdos confirmados y decisiones pendientes.
- [Arquitectura y permisos](docs/arquitectura.md): entidades, transacciones, seguridad y matriz de roles.
- [Guía de uso](docs/usuario.md): recorrido completo de operación.
- [Operación y despliegue](docs/operacion.md): configuración, respaldos, restauración y límites.
- [Trazabilidad Jira](docs/trazabilidad.md): historias y archivos correspondientes.
- [Requisitos originales](docs/jira/requisitos.json): captura de las 89 incidencias revisadas el 2 de noviembre de 2026.
- [Dependencias verificadas](docs/dependencias-fuentes.json): repositorios, referencias y huellas de los paquetes locales.

El plano esquemático y las reglas documentadas sirven para la exposición académica. Una adaptación a un cementerio real requeriría validar su plano, procedimientos y políticas financieras.
