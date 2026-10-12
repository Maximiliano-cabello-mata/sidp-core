"""Exporta SQL revisable de las migraciones reales, sin secretos ni datos de usuario."""
import tempfile
from pathlib import Path
from backend.main import preparar


def generar():
    with tempfile.TemporaryDirectory() as temporal:
        ctx = preparar(directorio=temporal)
        with ctx.bd.conexion() as db:
            objetos = db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
                                 "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 WHEN 'view' THEN 2 ELSE 3 END,name").fetchall()
            versiones = db.execute('SELECT modulo,version FROM esquema ORDER BY modulo').fetchall()
        texto = '-- Generado por python -m herramientas.exportar_esquema. Para bases nuevas, no migrar existentes con este archivo.\n'
        texto += 'PRAGMA foreign_keys=ON;\nBEGIN;\n'
        texto += '\n'.join(f[0] + ';' for f in objetos)
        for modulo, version in versiones:
            texto += f"\nINSERT INTO esquema VALUES('{modulo}',{version});"
        return texto + '\nCOMMIT;\n'


if __name__ == '__main__':
    destino = Path('database/esquema_actual.sql')
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(generar(), encoding='utf-8')
    print(destino)
