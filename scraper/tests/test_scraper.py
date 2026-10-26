from pathlib import Path

from scraper import luzdelsur, pluz

FIX = Path(__file__).parent / "fixtures"


def test_pdf_de_pluz():
    cortes = pluz.parse_pdf((FIX / "pluz_19_25_oct.pdf").read_bytes(), "https://x/pdf")
    assert len(cortes) == 45
    primero = cortes[0]
    assert (primero["fecha"], primero["inicio"], primero["fin"]) == ("2026-10-19", "00:00", "06:00")
    assert primero["distritos"] == ["LIMA CERCADO"]
    assert primero["zonas"].startswith("JR. HUANCAVELICA CDRAS. 2, 4")
    # "SAN MARTÍN DE PORRES / LOS OLIVOS" toca los dos distritos
    assert any(c["distritos"] == ["SAN MARTÍN DE PORRES", "LOS OLIVOS"] for c in cortes)
    assert {c["fecha"] for c in cortes} == {f"2026-10-{d}" for d in range(19, 26)}


def test_enlaces_pdf():
    html = ('<a href="/content/dam/x/cortes/Cortes%20programados%20-%2019.10%20al%2025.10.pdf">aquí</a>'
            '<a href="/content/dam/x/legales/Transferencia.pdf">otro</a>')
    assert pluz.enlaces_pdf(html) == [
        "https://www.pluz.pe/content/dam/x/cortes/Cortes%20programados%20-%2019.10%20al%2025.10.pdf"]


def test_luz_del_sur_vacio_y_tolerante():
    assert luzdelsur.parse({"success": True, "datos": {"listado": []}}) == []
    c = luzdelsur.parse({"success": True, "datos": {"listado": [
        {"NombreDistrito": "Surco", "FechaCorte": "27/10/2026", "HoraInicio": "9:00", "HoraFin": "13:00"}]}})
    assert c[0]["distritos"] == ["Surco"] and c[0]["fecha"] == "2026-10-27"
    assert (c[0]["inicio"], c[0]["fin"]) == ("09:00", "13:00")
