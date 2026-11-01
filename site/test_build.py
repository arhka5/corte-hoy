import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from datetime import date  # noqa: E402

from build import distrito, titulo_dia, zonas_txt  # noqa: E402


def test_titulo_por_fecha_como_se_busca():
    hoy = date(2026, 11, 1)
    assert titulo_dia("2026-11-01", hoy) == "Corte de luz hoy domingo 1 de noviembre en Lima y Callao"
    assert titulo_dia("2026-11-02", hoy) == "Corte de luz mañana lunes 2 de noviembre en Lima y Callao"
    assert titulo_dia("2026-11-04", hoy) == "Corte de luz el miércoles 4 de noviembre en Lima y Callao"


def test_distritos_canonicos():
    assert distrito("SAN MARTÍN DE PORRES") == ("san-martin-de-porres", "San Martín de Porres")
    assert distrito("LIMA CERCADO") == ("lima-cercado", "Lima Cercado")
    assert distrito("JESUS MARIA") == ("jesus-maria", "Jesús María")
    assert distrito("SAN ANTONIO DE CHACLLA") == ("san-antonio-de-chaclla", "San Antonio de Chaclla")
    # Luz del Sur escribe el distrito con su capital
    assert distrito("LURIGANCHO-CHOSICA") == ("lurigancho", "Lurigancho")


def test_zonas_legibles_sin_cambiar_datos():
    assert zonas_txt("JR. HUANCAVELICA CDRAS. 2, 4, AV. EL NARANJAL CDRA 14, MZ H2.") == \
        "Jr. Huancavelica cdras. 2, 4, Av. el Naranjal cdra. 14, Mz. H2"
    assert zonas_txt("LAS LOMAS FTE.763.ESQ.SANTUARIO(SED1373)") == "Las Lomas FTE.763.ESQ.SANTUARIO(SED1373)"
