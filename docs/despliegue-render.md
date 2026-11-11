# Preparación de despliegue en Render

Esta configuración propone una instancia independiente para CementerioERP. No adopta, modifica ni comparte la base o aplicación ImmunoClinic que ya existe en la cuenta Render.

## Recursos propuestos

- Servicio Docker `cementerioerp-web`, plan `0.5c-512mb`, región Virginia.
- PostgreSQL 17, plan mínimo pagado `0.1c-256mb`, almacenamiento inicial de 1 GB, en Virginia.
- Despliegue automático desde la rama `main`, comprobación de salud en `/salud/`.
- `DJANGO_DEBUG=0`, clave Django generada por Render y movimientos operativos sin aprobar.
- Variables SMTP solicitadas durante la primera configuración; sus valores no se guardan en Git.

Los planos, contratos escaneados y soportes se guardan en campos binarios de PostgreSQL; no necesitan un disco local persistente. Según los precios publicados por Render al preparar este archivo, la referencia de cómputo mínimo es aproximadamente USD 7/mes para el servicio web y USD 6/mes para PostgreSQL, más USD 0,30/GB-mes por almacenamiento. Con 1 GB de base, el costo base estimado es USD 13,30/mes, antes de tarifa del espacio de trabajo, tráfico excedente e impuestos. El precio final debe revisarse en Render antes de aplicar el plan: https://render.com/pricing

## Requisitos antes de crear los servicios

1. Publicar este proyecto en un repositorio **privado** de GitHub/GitLab/Bitbucket. No subir `.env`, `media/`, `backups/`, base de datos, mensajes simulados ni contraseñas. `.gitignore` y `.dockerignore` ya excluyen los datos locales.
2. Conceder a Render acceso de lectura al repositorio y configurar un remoto Git local funcional.
3. Confirmar el espacio Render `My Workspace` antes de aplicar recursos. Allí ya existe otra aplicación; esta configuración crea nombres y recursos nuevos.
4. Tener un proveedor SMTP y su remitente/dominio verificado. El formulario de alta no podrá entregar enlaces de confirmación si el correo saliente no se configura.
5. Revisar y aprobar el gasto mensual estimado en la página del plan de Render.

La carpeta local actual no tiene historial/remoto Git válido y la sesión de `gh` local no está autenticada. Por ello, la configuración no se ha publicado y Render aún no puede crear el Blueprint. La conexión GitHub disponible permite consultar repositorios, pero no crear uno nuevo desde esta sesión.

## Configuración y puesta en marcha

`render.yaml` describe la infraestructura. `scripts/start.py` ejecuta `check`, migraciones, estáticos y Gunicorn; ahora toma el puerto de `PORT`. Django confía en el encabezado HTTPS del proxy cuando corre en Render y agrega el hostname de Render permitido.

Después de enlazar el repositorio, Render debe mostrar el plan antes de crear los servicios. Verificar que se creen solo `cementerioerp-web`, `cementerioerp-db` y el disco nuevo. Tras el primer despliegue:

1. Completar `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL` en Environment, sin copiar secretos al repositorio.
2. Crear el primer administrador mediante la Shell del servicio con `python manage.py createsuperuser`.
3. Verificar `/salud/`, inicio de sesión, activación de cuenta con correo real, carga/lectura de documentos y una copia/restauración de PostgreSQL.
4. Mantener el sistema sin datos reales hasta revisar privacidad, procedimientos, facturación y aceptación del responsable.

## Límites

Este Blueprint empieza con una instancia web y recursos pequeños; no constituye una arquitectura de alta disponibilidad. El tamaño de la base debe crecer con los adjuntos y respaldos. Es un punto de partida para un piloto pequeño, sujeto a aceptación del responsable y a las pruebas indicadas en la guía de operación.

No se configura el perfil académico: su rutina de carga está diseñada para demostración local y exige contraseña interactiva. La instancia propuesta corre con `config.settings`, sin datos de demostración ni cuentas predeterminadas.
