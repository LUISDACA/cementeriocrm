"""Strict, dependency-free validation for private cemetery plan PNGs."""

import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 12_000_000


class InvalidPlanImage(ValueError):
    pass


def inspect_plan_png(content):
    if len(content) > MAX_BYTES:
        raise InvalidPlanImage("La imagen no puede superar 8 MB.")
    if not content.startswith(PNG_SIGNATURE):
        raise InvalidPlanImage("Carga un archivo PNG válido.")

    offset = len(PNG_SIGNATURE)
    width = height = color_type = None
    compressed = bytearray()
    saw_ihdr = saw_idat = saw_iend = idat_closed = False
    while offset < len(content):
        if offset + 12 > len(content):
            raise InvalidPlanImage("El archivo PNG está incompleto.")
        length = struct.unpack_from(">I", content, offset)[0]
        chunk_type = content[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end > len(content) or crc_end > len(content):
            raise InvalidPlanImage("El archivo PNG contiene un bloque incompleto.")
        chunk_data = content[data_start:data_end]
        expected_crc = struct.unpack_from(">I", content, data_end)[0]
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise InvalidPlanImage("La imagen PNG está dañada.")

        if not saw_ihdr and chunk_type != b"IHDR":
            raise InvalidPlanImage("La imagen PNG no tiene una cabecera válida.")
        if chunk_type == b"IHDR":
            if saw_ihdr or length != 13:
                raise InvalidPlanImage("La cabecera PNG no es válida.")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
            if (
                not width
                or not height
                or width > 6000
                or height > 6000
                or width * height > MAX_PIXELS
                or bit_depth != 8
                or channels is None
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                raise InvalidPlanImage(
                    "Usa un PNG RGB/RGBA de 8 bits, sin entrelazado, de hasta 6.000 × 6.000 píxeles y 12 megapíxeles."
                )
            saw_ihdr = True
        elif chunk_type == b"IDAT":
            if idat_closed or saw_iend:
                raise InvalidPlanImage("La estructura de datos PNG no es válida.")
            saw_idat = True
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0 or not saw_idat:
                raise InvalidPlanImage("El archivo PNG no se cerró correctamente.")
            saw_iend = True
            offset = crc_end
            break
        else:
            if saw_idat:
                idat_closed = True
            if chunk_type in (b"acTL", b"fcTL", b"fdAT"):
                raise InvalidPlanImage("No se admiten PNG animados.")
            if chunk_type == b"PLTE" and (
                saw_idat or color_type not in (2, 6) or length < 3 or length > 768 or length % 3
            ):
                raise InvalidPlanImage("La paleta auxiliar del PNG no es válida.")
            if chunk_type[0] & 0x20 == 0 and chunk_type not in (b"PLTE",):
                raise InvalidPlanImage("La imagen usa una extensión PNG no compatible.")
        offset = crc_end

    if not saw_iend or offset != len(content) or width is None:
        raise InvalidPlanImage("El archivo PNG está incompleto o contiene datos adicionales.")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    expected_size = height * (1 + width * channels)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(compressed), expected_size + 1)
        if len(pixels) > expected_size or decoder.unconsumed_tail:
            raise InvalidPlanImage("La imagen descomprimida supera el tamaño permitido.")
        pixels += decoder.flush(expected_size - len(pixels) + 1)
    except zlib.error as exc:
        raise InvalidPlanImage("Los datos de la imagen PNG no son válidos.") from exc
    if len(pixels) != expected_size or not decoder.eof or decoder.unused_data:
        raise InvalidPlanImage("Los datos de la imagen PNG no coinciden con sus dimensiones.")
    stride = 1 + width * channels
    if any(pixels[row * stride] > 4 for row in range(height)):
        raise InvalidPlanImage("La imagen PNG contiene filas con filtros no válidos.")
    return width, height
