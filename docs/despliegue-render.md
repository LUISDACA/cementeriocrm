# Demo gratuita temporal en Render

`render.yaml` crea recursos separados para una demo académica: servicio web gratuito y PostgreSQL gratuito en Virginia. No adopta ni modifica servicios de otros proyectos del espacio `My Workspace`.

## Qué hace

- Usa `config.settings_academic`, `DJANGO_DEBUG=0`, PostgreSQL 17 y HTTPS de Render.
- Carga al iniciar el lote sintético académico: 432 sepulturas, personas ficticias, contratos y pagos de demostración.
- Render solicita `DEMO_ADMIN_PASSWORD` durante la primera aplicación del Blueprint. Define ahí una contraseña propia de al menos 12 caracteres; no la guardes en Git.
- La demo usa un buzón de correo simulado. No envía correo real ni necesita credenciales SMTP.
- El repositorio no contiene `.env`, cuentas reales, adjuntos locales, respaldos ni base de datos.

## Límites del nivel gratuito

Este destino es solo para demostración, no producción. Render duerme la web tras 15 minutos sin tráfico y puede tardar cerca de un minuto en reactivarla. PostgreSQL gratuito tiene 1 GB, vence a los 30 días y no cuenta con respaldos; Render puede reiniciar o hacer mantenimiento. Los cambios del buzón local se pierden al reiniciar. Los planos y soportes de documentos del sistema viven en PostgreSQL y desaparecen con la base cuando expire.

La cuenta creada para la demo usa roles académicos y datos ficticios. No registres información personal real, pagos reales ni documentos oficiales. El perfil académico simula los movimientos y el correo.

Fuente oficial de límites: https://render.com/docs/free

## Arranque

El contenedor ejecuta comprobaciones Django, migraciones, estáticos y Gunicorn en el puerto asignado por Render. Cuando `CEMETERY_AUTO_SEED_DEMO=1`, el proceso inicializa el conjunto sintético únicamente con `config.settings_academic`; los comandos no pueden cargar datos sintéticos en el perfil normal.

El plan del Blueprint debe revisarse en Render antes de aplicarlo. Una demo en nivel gratuito no genera cómputo mensual, pero está sujeta a los límites y vencimiento anteriores. Para mantenerla después, habrá que cambiar a planes pagos, preparar correo SMTP, respaldos y una configuración no académica.
