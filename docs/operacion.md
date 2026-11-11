# Operación y despliegue

El alcance confirmado es académico. Para preparar la exposición utiliza [entrega-academica.md](entrega-academica.md). Las recomendaciones de producción de este documento solo aplican a una adaptación futura.

## Configuración

La aplicación lee `.env` como datos, sin ejecutar código shell. Las variables reales del proceso tienen prioridad. Los secretos no se incluyen en el repositorio ni en imágenes Docker.

| Variable | Uso |
| --- | --- |
| DJANGO_SECRET_KEY | Secreto aleatorio del servidor; obligatorio con DEBUG=0 |
| DJANGO_DEBUG | 1 solo en desarrollo; 0 en producción |
| DJANGO_ALLOWED_HOSTS | Nombres de host explícitos separados por coma |
| DATABASE_URL | Conexión PostgreSQL, con contraseña codificada si contiene caracteres especiales |
| DATABASE_SSLMODE | Usar `require` o verificación de certificado para base remota según proveedor |
| CEMETERY_NAME | Nombre visible de la institución |
| CEMETERY_CURRENCY | Moneda única de la instalación; decidir antes de carga real |
| CEMETERY_EXPIRY_DAYS | Umbral de aviso de vencimiento contractual |
| CEMETERY_MOVEMENTS_APPROVED | Mantener 0 hasta validar y configurar el procedimiento real |
| EMAIL_HOST / EMAIL_PORT | Servidor SMTP |
| EMAIL_HOST_USER / EMAIL_HOST_PASSWORD | Credenciales SMTP |
| EMAIL_USE_TLS / DEFAULT_FROM_EMAIL | Transporte y remitente |

La configuración local admite una base dedicada de pruebas. Para producción usar un rol de ejecución limitado y otro rol para migraciones. No confiar en encabezados de proxy enviados directamente por clientes. Si se termina TLS en un proxy, configurar el encabezado seguro únicamente después de asegurar que el proxy sobrescribe ese encabezado y que el servidor no es accesible directamente.

El Docker Compose incluido **es local** y publica solo en 127.0.0.1. El servicio web real requiere TLS, secretos, base respaldada, correo verificado y revisión de los controles de acceso. No se ha desplegado ni publicado esta aplicación.

## Inicio y migraciones

`scripts/start.py` ejecuta comprobaciones, migraciones y recolección de estáticos antes de iniciar Gunicorn. Para un despliegue con varias réplicas, ejecutar las migraciones como paso único anterior al arranque, en vez de lanzarlas en cada réplica.

`GET /salud/` comprueba acceso a la base sin devolver conexión, versión ni datos de usuarios. Monitorizar respuestas 503, errores de aplicación, latencia y espacio disponible.

Gunicorn no registra URLs de acceso para evitar que aparezcan tokens de recuperación en logs. El proxy también debe omitir o redactar las rutas de recuperación. No registrar cuerpos de formularios, cookies, credenciales ni tokens. Django en DEBUG puede registrar rutas durante desarrollo; usar solo cuentas sintéticas en ese entorno.

## Copias y restauración

Los scripts usan utilidades oficiales `pg_dump` y `pg_restore`. El archivo es formato custom, con permisos restringidos. Se utiliza la variable de entorno de libpq para que la contraseña no aparezca en los argumentos del proceso.

```bash
# Exporta DATABASE_URL sin imprimirla en terminal o historial compartido.
bash scripts/backup.sh backups

# Crea una base VACÍA de recuperación y configura RESTORE_DATABASE_URL.
bash scripts/restore.sh backups/<archivo>.dump
```

El respaldo se valida y se renombra al finalizar, sin sobrescribir otro archivo del mismo segundo. La restauración valida el archivo, rechaza la misma URL de origen y un destino con relaciones o funciones propias, y aplica el archivo en una transacción. No usa `--clean`. Debe usarse una base nueva, aislada de producción. La herramienta no puede determinar por sí sola si una URL corresponde al entorno correcto.

Después de restaurar: verificar recuentos, acceso por rol, ocupación vigente única, saldos, reservas, muestra de eventos y lectura del mapa. Registrar tiempo de restauración y resultados. Conservar los respaldos fuera del servidor y probar restauración periódicamente. Frecuencia, retención, cifrado y objetivos de recuperación deben acordarse antes de producción.

## Vencimiento de reservas

El estado visible trata como vencida una reserva cuya fecha pasó, aunque el job todavía no haya registrado el evento. Antes de reservar/contratar el mismo espacio se registra su vencimiento dentro de la transacción. Para registrar proactivamente todos los eventos:

```bash
.venv/bin/python manage.py expire_reservations --actor tesoreria@dominio-del-cementerio
```

La cuenta indicada debe ser activa y tener perfil Tesorería o Administrador. Programar una ejecución diaria en el entorno elegido. Se conservan los pagos; el job no ejecuta devoluciones ni penalidades.

## Rendimiento y límites actuales

- Paginación del servidor: 20 registros con orden estable.
- Mapa: máximo 1.000 espacios por respuesta; advertencia y filtros si se supera.
- Mapa: actualización cada 15 segundos mientras la pestaña está visible.
- Escrituras serializadas para proteger consistencia; medir con carga real antes de escalar.
- Sin carga masiva de personas reales ni documentos adjuntos; no se ha acordado su alcance.
- Indicadores de estado: una consulta agregada; búsqueda de personas del mapa: dos consultas hasta 20 coincidencias; saldo contractual calculado desde una misma lectura de pagos. Medir otros recorridos antes de producción.

## Cierre y aceptación

Para una entrega destinada a producción deben ejecutarse:

1. Instalación con dependencias concretas y registro de versiones; generar un lock reproducible del entorno validado.
2. `manage.py check`, `makemigrations --check --dry-run`, migraciones desde base vacía y `collectstatic`.
3. Pruebas de dominio/HTTP/concurrencia con PostgreSQL.
4. Recorrido completo con cinco perfiles y datos sintéticos.
5. Validación visual de escritorio y móvil, teclado, estados vacíos/errores y mapa.
6. Prueba de correo de recuperación, respaldo y restauración aislada.
7. Validación del plano y de las reglas de reservas, devoluciones y movimientos.
8. `manage.py check --deploy` con configuración de destino, medición acordada y revisión de autorización.
9. Aceptación del responsable del cementerio y despliegue en el entorno acordado.

El código escrito y las fechas del calendario original no sustituyen esa evidencia.
