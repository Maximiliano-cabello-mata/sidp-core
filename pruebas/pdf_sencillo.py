"""Hace un PDF de texto mínimo para las pruebas (sin bibliotecas): una línea por renglón."""


def pdf_de_texto(lineas):
    def escapar(texto):
        return texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    contenido = 'BT /F1 11 Tf 40 800 Td 14 TL ' + ' '.join(f'({escapar(l)}) Tj T*' for l in lineas) + ' ET'
    contenido = contenido.encode('latin-1', 'replace')
    objetos = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
               b'<< /Length %d >>\nstream\n' % len(contenido) + contenido + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    salida, posiciones = bytearray(b'%PDF-1.4\n'), []
    for numero, objeto in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += b'%d 0 obj\n' % numero + objeto + b'\nendobj\n'
    inicio = len(salida)
    salida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objetos) + 1)
    salida += b''.join(b'%010d 00000 n \n' % p for p in posiciones)
    salida += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objetos) + 1, inicio)
    return bytes(salida)
