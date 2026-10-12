import pytest


@pytest.fixture(autouse=True)
def hogar_aislado(tmp_path, monkeypatch):
    """Ninguna prueba toca la instalación real del equipo."""
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'hogar'))
    for variable in ('SIDP_DATA_DIR', 'SIDP_AGENTE_DIR', 'SIDP_TOKEN', 'SIDP_URL', 'SIDP_IDENTIDADES'):
        monkeypatch.delenv(variable, raising=False)
    return tmp_path / 'hogar'
