import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build import distrito, zonas_txt  # noqa: E402


def test_distritos_canonicos():
    assert distrito("SAN MARTÍN DE PORRES") == ("san-martin-de-porres", "San Martín de Porres")
    assert distrito("LIMA CERCADO") == ("lima-cercado", "Lima Cercado")
    assert distrito("JESUS MARIA") == ("jesus-maria", "Jesús María")
    assert distrito("SAN ANTONIO DE CHACLLA") == ("san-antonio-de-chaclla", "San Antonio de Chaclla")


def test_zonas_legibles_sin_cambiar_datos():
    assert zonas_txt("JR. HUANCAVELICA CDRAS. 2, 4, AV. EL NARANJAL CDRA 14, MZ H2.") == \
        "Jr. Huancavelica cdras. 2, 4, Av. el Naranjal cdra. 14, Mz. H2"
    assert zonas_txt("LAS LOMAS FTE.763.ESQ.SANTUARIO(SED1373)") == "Las Lomas FTE.763.ESQ.SANTUARIO(SED1373)"
