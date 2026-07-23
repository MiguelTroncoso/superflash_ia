"""Tests del comando de diagnóstico de fuentes."""

import pytest

import app.database.session as db_session
from app.tasks.diagnose_source import main


def _forbid_engine(monkeypatch):
    """Hace fallar el test si el diagnóstico intenta crear el motor de BD."""

    def _boom(*args, **kwargs):
        raise AssertionError("el diagnóstico no debe tocar la base de datos")

    monkeypatch.setattr(db_session, "create_engine", _boom)
    db_session.get_engine.cache_clear()
    db_session.get_session_factory.cache_clear()


def test_diagnose_all_sources(monkeypatch, capsys):
    """El diagnóstico completo termina en 0 y describe ambas fuentes."""
    _forbid_engine(monkeypatch)

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fuente de infraestructura: mock-infra" in output
    assert "Fuente de streaming: mock-streaming" in output
    assert "servidores visibles: 5" in output
    assert "canales visibles: 24" in output
    assert "cpu_percent" in output and "disk_percent" in output
    assert "viewers" in output and "bitrate_mbps" in output
    assert "No se escribió nada en la base de datos." in output
    assert "No se realizó ninguna conexión externa" in output


def test_diagnose_single_source(monkeypatch, capsys):
    """--source infrastructure limita el diagnóstico a esa fuente."""
    _forbid_engine(monkeypatch)

    exit_code = main(["--source", "infrastructure"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fuente de infraestructura: mock-infra" in output
    assert "Fuente de streaming" not in output


def test_diagnose_rejects_unknown_source():
    """Un valor de --source no soportado es rechazado por argparse."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--source", "ssh"])
    assert excinfo.value.code == 2
