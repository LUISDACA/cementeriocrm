"""Create a compact, dependency-free PDF status report for the academic project."""
from pathlib import Path
import textwrap


OUT = Path(__file__).resolve().parents[1] / "docs" / "estado-actual.pdf"
W, H = 595, 842
pages: list[list[tuple[str, float, str]]] = [[]]
y = H - 64


def add(text: str, *, size: int = 10, color: str = "0.14 0.22 0.18", bold: bool = False,
        gap: int = 3, indent: int = 0, max_chars: int | None = None) -> None:
    global y
    font = "F2" if bold else "F1"
    width = max_chars or (88 if size <= 10 else 67 if size <= 13 else 39)
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]
    leading = size * 1.32
    needed = len(lines) * leading + gap
    if y - needed < 58:
        pages.append([])
        y = H - 64
    for line in lines:
        pages[-1].append((f"{color} rg /{font} {size} Tf 1 0 0 1 {54 + indent} {y:.1f} Tm ({escape(line)}) Tj", size, ""))
        y -= leading
    y -= gap


def escape(s: str) -> str:
    raw = s.encode("cp1252", errors="replace")
    return "".join("\\%03o" % b if b < 32 or b > 126 else "\\" + chr(b) if chr(b) in "()\\" else chr(b) for b in raw)


add("INFORME DE AVANCE · PROYECTO ACADÉMICO", size=9, color="0.30 0.48 0.39", bold=True, gap=11)
add("CementerioERP", size=29, color="0.08 0.29 0.22", bold=True, gap=2)
add("Estado actual y ruta para preparar una futura operación real", size=15, color="0.26 0.35 0.29", gap=12)
add("Corte: 3 de noviembre de 2026  ·  Django 5.2  ·  PostgreSQL", size=10, color="0.36 0.43 0.38", gap=15)
add("CONCLUSIÓN", size=12, color="0.08 0.29 0.22", bold=True, gap=4)
add("La aplicación tiene una base funcional amplia para demostrar procesos de cementerio, pero no está certificada ni preparada para operar con datos reales, cobrar dinero real o emitir documentos tributarios.", size=11, color="0.14 0.22 0.18", gap=12)

add("Resumen ejecutivo", size=17, color="0.08 0.29 0.22", bold=True, gap=6)
add("CementerioERP organiza el inventario de sepulturas y muestra flujos de personas, responsables, contratos, reservas, pagos, movimientos y gastos. Incluye perfiles de acceso, registro público de cuentas familiares, confirmación de correo, auditoría y documentos privados.")
add("La demostración utiliza datos sintéticos, una parcela ilustrativa y un buzón académico local. Se pueden cargar planos y coordenadas propios, pero el proyecto no incluye el plano de un cementerio real. El uso real exige definir reglas locales, adaptar integraciones y validar la operación con el personal.")

add("Capacidades disponibles", size=17, color="0.08 0.29 0.22", bold=True, gap=5)
for title, body in [
    ("Acceso y personas", "Perfiles operativos; registro público familiar; confirmación de correo; revisión y vinculación administrativa."),
    ("Mapa e inventario", "Mapa SVG con búsqueda/zoom; carga privada de plano PNG; importación CSV con vista previa; exportación e informes de capacidad."),
    ("Operación funeraria", "Personas fallecidas, responsables, contratos, reservas con anticipo, inhumaciones y flujo académico de exhumación/traslado."),
    ("Finanzas", "Facturas internas, mensualidades configuradas, pagos parciales, recibos, devoluciones registradas, gastos, cartera y libro de caja."),
    ("Documentos y auditoría", "Adjuntos privados de contratos y gastos, versiones, huellas SHA-256 y registro de cambios."),
]:
    add(title + ": " + body, indent=8)

add("Registro familiar", size=13, color="0.08 0.29 0.22", bold=True, gap=3)
add("Cualquier persona puede crear una cuenta con su correo. Queda inactiva hasta confirmar el enlace; luego, administración debe cotejar identidad y vincular los registros antes de mostrar información privada. En modo académico el mensaje queda en «Correos simulados», no sale a Internet.")

add("Mapa y datos", size=17, color="0.08 0.29 0.22", bold=True, gap=5)
add("El lote de ejemplo contiene 432 sepulturas en bloques C–H, con nombres verosímiles y códigos marcados como demostrativos. Es un escenario inventado: no representa ubicaciones ni identidades reales. Administración puede cargar un plano autorizado y ubicar los espacios. La importación CSV admite hasta 5.000 espacios por archivo, con validación; no elimina ni altera los existentes.")

add("Límites de correo, documentos y finanzas", size=17, color="0.08 0.29 0.22", bold=True, gap=5)
for t in [
    "Los contratos son plantillas imprimibles con espacio para firmas manuscritas. Adjuntar una copia firmada no equivale a firma electrónica ni valida su autenticidad.",
    "Facturas y recibos son internos; no son comprobantes tributarios autorizados. No hay pasarela de pago ni movimiento de dinero.",
    "El correo académico usa un buzón local. Correo real requiere SMTP, credenciales protegidas, dominio y pruebas de entrega.",
    "Impuestos, tarifas y procedimientos deben contrastarse con la normativa y políticas del cementerio elegido.",
]: add(t, indent=8)

add("Seguridad y validación técnica", size=17, color="0.08 0.29 0.22", bold=True, gap=5)
add("Incluye permisos por perfil, contraseñas administradas por Django, límites de intentos, controles de integridad, transacciones, documentos autenticados y auditoría. Son controles implementados, no una certificación de seguridad.")
for t in [
    "Django check y compilación: sin errores en la verificación registrada.",
    "Pruebas documentadas: perfil de verificación con 112 pruebas (108 aprobadas y 4 omitidas); también hay comprobaciones seriales y de interfaz.",
    "DDL y restricciones PostgreSQL: comprobados en instancia temporal según el registro técnico.",
    "En esta sesión no se pudo verificar la conexión ORM ni el historial de migraciones contra PostgreSQL.",
    "El ZIP académico fue creado; no es un servicio desplegado.",
]: add(t, indent=8)

add("Qué falta para una operación real", size=17, color="0.08 0.29 0.22", bold=True, gap=5)
for i, t in enumerate([
    "Definir cementerio, municipio/país, responsables y procesos vigentes.",
    "Aprobar reglas para espacios, contratos, tarifas, reservas, devoluciones, movimientos y conservación de documentos.",
    "Preparar plano e inventario verificados; migrar información con revisión de duplicados y conciliación.",
    "Validar con asesoría local facturación, impuestos, firma aceptada, pagos y conciliación bancaria.",
    "Revisar privacidad y seguridad: base legal, retención, acceso mínimo, secretos, vulnerabilidades e incidentes.",
    "Desplegar con HTTPS, base respaldada, monitoreo, correo transaccional, actualizaciones y soporte.",
    "Capacitar, probar en paralelo, obtener aceptación formal y definir reversa antes de producción.",
], 1): add(f"{i}. {t}", indent=5)

add("Siguiente paso recomendado", size=13, color="0.08 0.29 0.22", bold=True, gap=3)
add("Hacer una etapa de descubrimiento y piloto controlado. No cargar datos personales reales ni emitir cobros o documentos oficiales hasta cerrar y aprobar los puntos anteriores.")
add("Iniciar demostración: make demo (con PostgreSQL disponible). Dirección local: http://127.0.0.1:8000. Revisa docs/entrega-academica.md y docs/operacion.md.", size=9, color="0.32 0.39 0.34", gap=6)
add("Informe basado en README.md y la documentación del proyecto al corte indicado. No es auditoría independiente ni certificación legal, tributaria o de seguridad.", size=8, color="0.40 0.45 0.41", gap=0)


def make_pdf() -> bytes:
    objs: list[bytes] = []
    def obj(data: bytes) -> int:
        objs.append(data)
        return len(objs)
    catalog = obj(b"")
    pages_id = obj(b"")
    f1 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    kids = []
    for idx, entries in enumerate(pages, 1):
        commands = ["BT"]
        for command, _, _ in entries:
            commands.append(command)
        commands.extend(["ET", f"0.38 0.47 0.41 rg /F1 8 Tf 1 0 0 1 54 34 Tm (CementerioERP  ·  Estado al 3 de noviembre de 2026  ·  {idx}) Tj"])
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        content = obj(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = obj(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W} {H}] /Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> >> /Contents {content} 0 R >>".encode())
        kids.append(f"{page_id} 0 R")
    objs[catalog - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    objs[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, data in enumerate(objs, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + data + b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(objs)+1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


OUT.write_bytes(make_pdf())
print(f"PDF creado: {OUT} ({len(pages)} páginas)")
