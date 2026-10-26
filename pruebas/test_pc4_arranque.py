"""Que la PC 4 trabaje sola al encenderse: el cerebro no se queda sin base y el vigía lo levanta."""
from pathlib import Path

from validacion import cerebro_red

PC4 = Path(__file__).resolve().parents[1] / 'cerebro' / 'pc4'


def test_sin_base_el_cerebro_sale_para_que_su_lanzador_lo_vuelva_a_intentar(tmp_path):
    # Antes arrancaba sin base y contestaba error 500 en todo lo de la base hasta que alguien lo reiniciaba.
    argumentos = ['--clave', str(tmp_path / 'clave.txt'), '--base', str(tmp_path / 'no_existe.txt'), '--exigir-base',
                  '--sin-mostrar-clave', '--actualizaciones', str(tmp_path / 'actualizaciones')]
    assert cerebro_red.main(argumentos) == 3


def test_el_instalador_deja_al_vigia_revisando_cada_dos_minutos():
    instalador = (PC4 / 'instalar_servicios.ps1').read_text(encoding='utf-8-sig')
    vigia = (PC4 / 'vigia.ps1').read_text(encoding='utf-8-sig')
    assert '--exigir-base' in instalador and "Join-Path $PSScriptRoot 'vigia.ps1'" in instalador
    assert "-RepetitionInterval (New-TimeSpan -Minutes 2)" in instalador and "-UserId 'SYSTEM'" in instalador
    # El vigía no escribe la clave: la lee del archivo que solo está en la PC 4.
    assert 'Get-Content $ArchivoClave' in vigia and 'Anota "$clave' not in vigia
    for servicio in ("Start-ScheduledTask -TaskName 'SIDP-Cerebro'", "Start-ScheduledTask -TaskName 'SIDP-Ollama'", 'Start-Service'):
        assert servicio in vigia


def test_en_el_servidor_que_tambien_es_cerebro_el_cerebro_escucha_solo_en_esa_pc(tmp_path, monkeypatch):
    visto = {}

    class Falso:
        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(cerebro_red, 'crear_servidor', lambda *a, **k: visto.update(k) or Falso())
    monkeypatch.setenv('SIDP_ACTUALIZAR_GITHUB', '0')
    monkeypatch.delenv('SIDP_BASE', raising=False)
    argumentos = ['--clave', str(tmp_path / 'clave.txt'), '--base', str(tmp_path / 'no_existe.txt'), '--sin-mostrar-clave',
                  '--actualizaciones', str(tmp_path / 'actualizaciones')]
    monkeypatch.setenv('SIDP_CEREBRO_ANFITRION', '127.0.0.1')
    assert cerebro_red.main(argumentos) == 0 and visto['anfitrion'] == '127.0.0.1'
    monkeypatch.delenv('SIDP_CEREBRO_ANFITRION')
    assert cerebro_red.main(argumentos) == 0 and visto['anfitrion'] == '0.0.0.0'  # La PC 4 aparte: toda la red.
    instalador = (PC4 / 'instalar_servicios.ps1').read_text(encoding='utf-8-sig')
    assert '[switch]$MismaPC' in instalador and "SIDP_CEREBRO_ANFITRION = '127.0.0.1'" in instalador
    assert '$p.PriorityClass = $env:SIDP_PRIORIDAD' in instalador
