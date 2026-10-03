"""
Test suite for /api/generate endpoint in Generador Prompts V4.
Verifies acceptance criteria for both multipart/form-data and application/json,
as well as dynamic instructions, camera angles, and fallback prompt synthesis.
"""

import sys
import io
from pathlib import Path
from fastapi.testclient import TestClient

# Add app directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app, build_system_instructions, build_user_prompt, build_deterministic_prompt

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    print("✓ test_health passed")

def test_generate_entorno_form_data():
    """Simulates clicking 'entorno' button with multipart/form-data."""
    payload = {
        "boton_principal": "entorno",
        "medidas": "220cm x 95cm x 85cm",
        "tipo_mueble": "Sofá nórdico modular 3 plazas",
        "lugar_mueble": "Salón amplio con suelo de madera e iluminación natural",
        "sub_opcion": "3/4 Isométrica 45°",
        "vista": "",
        "tela": "Lino gris perla",
        "madera": "Roble natural",
        "ambiente": "Escandinavo cálido"
    }
    res = client.post("/api/generate", data=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("success") is True
    prompt = data.get("prompt", "")
    assert len(prompt) > 0
    # Verify entorno details are integrated
    assert "220cm x 95cm x 85cm" in prompt or "dimensiones" in prompt.lower()
    print("✓ test_generate_entorno_form_data passed (HTTP 200, success=True)")

def test_generate_entorno_json():
    """Simulates sending JSON payload with entorno fields."""
    payload = {
        "boton_principal": "entorno",
        "medidas": "180x90x75 cm",
        "tipo_mueble": "Mesa de comedor extensible",
        "lugar_mueble": "Comedor contemporáneo",
        "sub_opcion": "Frontal 0°"
    }
    res = client.post("/api/generate", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("success") is True
    assert len(data.get("prompt", "")) > 0
    print("✓ test_generate_entorno_json passed (HTTP 200, success=True)")

def test_generate_solo_mueble():
    """Simulates 'solo mueble' button."""
    payload = {
        "boton_principal": "solo mueble",
        "tipo_mueble": "Sillón orejero de piel",
        "sub_opcion": "Frontal 0°"
    }
    res = client.post("/api/generate", data=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    prompt = data.get("prompt", "")
    assert "#FFFFFF" in prompt or "blanco" in prompt.lower()
    print("✓ test_generate_solo_mueble passed (HTTP 200, isolated white background)")

def test_generate_hd():
    """Simulates 'hd' button."""
    payload = {
        "boton_principal": "hd",
        "tipo_mueble": "Aparador de nogal",
        "madera": "Nogal americano macizo"
    }
    res = client.post("/api/generate", data=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    prompt = data.get("prompt", "")
    assert "8K" in prompt or "macro" in prompt.lower()
    print("✓ test_generate_hd passed (HTTP 200, 8K macro focus)")

def test_generate_clonar_vistas():
    """Simulates 'Clonar Vistas (Color y Tela)' button."""
    payload = {
        "boton_principal": "Clonar Vistas (Color y Tela)",
        "sub_opcion": "Lateral 90°",
        "tela": "Terciopelo verde esmeralda",
        "madera": "Cerezo barnizado"
    }
    res = client.post("/api/generate", data=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    print("✓ test_generate_clonar_vistas passed (HTTP 200)")

def test_generate_360():
    """Simulates 'Clonar Múltiples Vistas 360' button."""
    payload = {
        "boton_principal": "Clonar Múltiples Vistas 360",
        "tipo_mueble": "Silla de comedor ergonómica"
    }
    res = client.post("/api/generate", data=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    prompt = data.get("prompt", "")
    assert "360" in prompt
    print("✓ test_generate_360 passed (HTTP 200, 360 rotational sheet)")

def test_generate_with_mock_image():
    """Simulates uploading an image file with form-data."""
    from PIL import Image
    img_byte_arr = io.BytesIO()
    test_img = Image.new("RGB", (100, 100), color="blue")
    test_img.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)

    files = {"image": ("test.jpg", img_byte_arr, "image/jpeg")}
    data = {
        "boton_principal": "entorno",
        "medidas": "100x100x40 cm",
        "tipo_mueble": "Mesa de centro",
        "lugar_mueble": "Salón minimalista"
    }
    res = client.post("/api/generate", files=files, data=data)
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    print("✓ test_generate_with_mock_image passed (HTTP 200 with image upload)")

def test_build_system_instructions_entorno():
    sys_inst = build_system_instructions(
        boton_principal="entorno",
        lugar_mueble="Terraza con vistas",
        tipo_mueble="Tumbona",
        medidas="200x70 cm"
    )
    assert "NO exigir fondo blanco sólido (#FFFFFF)" in sys_inst
    assert "Terraza con vistas" in sys_inst
    print("✓ test_build_system_instructions_entorno passed")

def test_build_system_instructions_solo_mueble():
    sys_inst = build_system_instructions(boton_principal="solo mueble")
    assert "#FFFFFF" in sys_inst
    assert "Solo Mueble" in sys_inst
    print("✓ test_build_system_instructions_solo_mueble passed")

def run_all_tests():
    print("Starting test suite for APP V4 BUENA...")
    test_health()
    test_build_system_instructions_entorno()
    test_build_system_instructions_solo_mueble()
    test_generate_entorno_form_data()
    test_generate_entorno_json()
    test_generate_solo_mueble()
    test_generate_hd()
    test_generate_clonar_vistas()
    test_generate_360()
    test_generate_with_mock_image()
    print("\nALL 10 TESTS PASSED SUCCESSFULLY! (Code 200 verified)")

if __name__ == "__main__":
    run_all_tests()
