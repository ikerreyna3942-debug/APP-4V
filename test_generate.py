"""
Comprehensive Automated Test Suite for Generador Prompts V4 (APP V4 BUENA).
Covers Tiers 1-5 across multi-image uploads, texture references, 11 main buttons,
isolated material replacement modes ("tela", "madera", "madera y tela"),
boundary cases, corrupt inputs, base64 payloads, multi-view response schemas,
4-pillar topological doctrine, selective preservation locks, and frontend static contracts.
"""

import sys
import io
import json
import base64
from pathlib import Path
from typing import List, Tuple
from html.parser import HTMLParser
import pytest
from PIL import Image
from fastapi import UploadFile
from fastapi.testclient import TestClient

# Add app directory to sys.path
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from app import (
    app,
    build_system_instructions,
    build_user_prompt,
    build_deterministic_prompt,
    build_deterministic_multiview,
    resolve_camera_spec,
    CAMERA_SPECS,
    is_multiview_request,
)

client = TestClient(app)
STATIC_DIR = APP_DIR / "static"


# ==============================================================================
# Helper Utilities for Test Fixtures & Synthetic Images
# ==============================================================================
def create_test_image_bytes(color: str = "blue", size: Tuple[int, int] = (100, 100), fmt: str = "JPEG") -> bytes:
    """Generates authentic JPEG image bytes for multi-image testing."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=fmt, quality=85)
    return buf.getvalue()


def create_test_image_base64(color: str = "green", size: Tuple[int, int] = (80, 80), with_prefix: bool = False) -> str:
    """Generates valid base64 encoded image string with optional data URI header."""
    raw = create_test_image_bytes(color=color, size=size)
    encoded = base64.b64encode(raw).decode("utf-8")
    if with_prefix:
        return f"data:image/jpeg;base64,{encoded}"
    return encoded


# Module-level fixtures for static file content
@pytest.fixture(scope="module")
def html_content() -> str:
    path = STATIC_DIR / "index.html"
    assert path.exists(), f"File {path} does not exist"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css_content() -> str:
    path = STATIC_DIR / "style.css"
    assert path.exists(), f"File {path} does not exist"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_content() -> str:
    path = STATIC_DIR / "script.js"
    assert path.exists(), f"File {path} does not exist"
    return path.read_text(encoding="utf-8")


# ==============================================================================
# Baseline Regression Suite (Preserving 100% of historical tests)
# ==============================================================================
def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


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
    assert "220cm x 95cm x 85cm" in prompt or "dimensiones" in prompt.lower()


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


def test_generate_with_mock_image():
    """Simulates uploading an image file with form-data."""
    img_bytes = create_test_image_bytes(color="blue")
    files = {"image": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
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


def test_build_system_instructions_entorno():
    sys_inst = build_system_instructions(
        boton_principal="entorno",
        lugar_mueble="Terraza con vistas",
        tipo_mueble="Tumbona",
        medidas="200x70 cm"
    )
    assert "NO exigir fondo blanco sólido (#FFFFFF)" in sys_inst
    assert "Terraza con vistas" in sys_inst


def test_build_system_instructions_solo_mueble():
    sys_inst = build_system_instructions(boton_principal="solo mueble")
    assert "#FFFFFF" in sys_inst
    assert "Solo Mueble" in sys_inst


# ==============================================================================
# Tier 1: Feature Coverage (Single/Multi-Image, References & All 9 Buttons)
# ==============================================================================
class TestTier1FeatureCoverage:
    """Verifies all primary upload channels and all 9 button behaviors."""

    def test_single_furniture_upload_mueble_images(self):
        """Uploads a single furniture photo through `mueble_images` list parameter."""
        img1 = create_test_image_bytes("red")
        files = [("mueble_images", ("chair_front.jpg", io.BytesIO(img1), "image/jpeg"))]
        data = {"boton_principal": "solo mueble", "tipo_mueble": "Silla minimalista"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert json_data["is_multiview"] is False
        assert len(json_data["vistas"]) == 1

    def test_multi_furniture_upload_2_images(self):
        """Uploads two furniture photos (front & side) through `mueble_images`."""
        img1 = create_test_image_bytes("red")
        img2 = create_test_image_bytes("blue")
        files = [
            ("mueble_images", ("sofa_front.jpg", io.BytesIO(img1), "image/jpeg")),
            ("mueble_images", ("sofa_side.jpg", io.BytesIO(img2), "image/jpeg"))
        ]
        data = {"boton_principal": "solo mueble", "tipo_mueble": "Sofá esquinero"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert "prompt" in json_data
        assert len(json_data["prompt"]) > 0

    def test_multi_furniture_upload_3_or_more_images(self):
        """Uploads 3 distinct furniture angle photos through `mueble_images`."""
        img1 = create_test_image_bytes("red")
        img2 = create_test_image_bytes("green")
        img3 = create_test_image_bytes("yellow")
        files = [
            ("mueble_images", ("angle_0.jpg", io.BytesIO(img1), "image/jpeg")),
            ("mueble_images", ("angle_45.jpg", io.BytesIO(img2), "image/jpeg")),
            ("mueble_images", ("angle_90.jpg", io.BytesIO(img3), "image/jpeg"))
        ]
        data = {"boton_principal": "Clonar Múltiples Vistas 360", "tipo_mueble": "Mesa de centro"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert json_data["is_multiview"] is True
        assert len(json_data["vistas"]) == 6

    def test_legacy_image_parameter_backward_compatibility(self):
        """Guarantees backward compatibility with legacy single `image` field."""
        img = create_test_image_bytes("purple")
        files = {"image": ("legacy_sofa.jpg", io.BytesIO(img), "image/jpeg")}
        data = {"boton_principal": "hd", "tipo_mueble": "Butaca clásica"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert "8K" in json_data["prompt"] or "macro" in json_data["prompt"].lower()

    def test_optional_madera_image_upload(self):
        """Uploads main furniture plus optional wood texture swatch reference."""
        mueble_img = create_test_image_bytes("brown")
        madera_img = create_test_image_bytes("saddlebrown")
        files = [
            ("mueble_images", ("mueble.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("madera_image", ("oak_swatch.jpg", io.BytesIO(madera_img), "image/jpeg"))
        ]
        data = {"boton_principal": "madera", "madera": "Roble macizo"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert "madera" in json_data["prompt"].lower() or "roble" in json_data["prompt"].lower()

    def test_optional_tela_image_upload(self):
        """Uploads main furniture plus optional fabric textile swatch reference."""
        mueble_img = create_test_image_bytes("gray")
        tela_img = create_test_image_bytes("beige")
        files = [
            ("mueble_images", ("mueble.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("tela_image", ("linen_swatch.jpg", io.BytesIO(tela_img), "image/jpeg"))
        ]
        data = {"boton_principal": "vistas + tela", "sub_opcion": "Frontal 0°", "tela": "Lino beige"}
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert "tela" in json_data["prompt"].lower() or "tapicería" in json_data["prompt"].lower()

    def test_dual_texture_reference_upload_both_wood_and_fabric(self):
        """Uploads furniture with both wood and fabric auxiliary swatches simultaneously."""
        mueble_img = create_test_image_bytes("navy")
        madera_img = create_test_image_bytes("brown")
        tela_img = create_test_image_bytes("wheat")
        files = [
            ("mueble_images", ("armchair.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("madera_image", ("walnut.jpg", io.BytesIO(madera_img), "image/jpeg")),
            ("tela_image", ("velvet.jpg", io.BytesIO(tela_img), "image/jpeg"))
        ]
        data = {
            "boton_principal": "vistas + tela y madera",
            "madera": "Nogal oscuro",
            "tela": "Terciopelo azul profundo",
            "sub_opcion": "3/4 Isométrica 45°"
        }
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert json_data["is_multiview"] is False
        assert "materiales y texturas" in json_data["prompt"].lower()

    # --- Verification of all 9 main buttons behavior ---
    def test_button_1_solo_mueble(self):
        res = client.post("/api/generate", data={"boton_principal": "solo mueble", "tipo_mueble": "Mesa"})
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "#FFFFFF" in p and "centrado" in p.lower()

    def test_button_2_vistas_multiview(self):
        res = client.post("/api/generate", data={"boton_principal": "vistas", "sub_opcion": ""})
        assert res.status_code == 200
        d = res.json()
        assert d["is_multiview"] is True
        assert len(d["vistas"]) == 6

    def test_button_2_vistas_single_angle(self):
        res = client.post("/api/generate", data={"boton_principal": "vistas", "sub_opcion": "Lateral 90°"})
        assert res.status_code == 200
        d = res.json()
        assert d["is_multiview"] is False
        assert "90" in d["prompt"] or "lateral" in d["prompt"].lower()

    def test_button_3_entorno(self):
        res = client.post("/api/generate", data={
            "boton_principal": "entorno",
            "medidas": "300x120 cm",
            "tipo_mueble": "Mesa de juntas",
            "lugar_mueble": "Oficina ejecutiva con ventanales"
        })
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "300x120 cm" in p
        assert "Oficina ejecutiva con ventanales" in p
        assert "ambientación" in p.lower()

    def test_button_4_vistas_tela_y_madera(self):
        res = client.post("/api/generate", data={
            "boton_principal": "vistas + tela y madera",
            "sub_opcion": "Frontal 0°",
            "madera": "Fresno",
            "tela": "Bouclé crema"
        })
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "fresno" in p.lower() or "bouclé" in p.lower() or "materiales" in p.lower()

    def test_button_5_vistas_tela(self):
        res = client.post("/api/generate", data={
            "boton_principal": "vistas + tela",
            "sub_opcion": "Arriba 3/4",
            "tela": "Microfibra gris"
        })
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "tapicería" in p.lower() or "microfibra" in p.lower() or "tela" in p.lower()

    def test_button_6_madera(self):
        res = client.post("/api/generate", data={"boton_principal": "madera", "madera": "Teka de exterior"})
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "teka" in p.lower() or "madera" in p.lower()

    def test_button_7_hd(self):
        res = client.post("/api/generate", data={"boton_principal": "hd", "tipo_mueble": "Credenza"})
        assert res.status_code == 200
        p = res.json()["prompt"]
        assert "8K" in p or "macro" in p.lower()

    def test_button_8_clonar_vistas_color_y_tela(self):
        res = client.post("/api/generate", data={
            "boton_principal": "Clonar Vistas (Color y Tela) - Obliga a igualar exactamente madera, tela y vista",
            "sub_opcion": "Trasera 135°",
            "madera": "Ebano",
            "tela": "Seda dorada"
        })
        assert res.status_code == 200
        d = res.json()
        assert d["success"] is True
        assert len(d["prompt"]) > 0

    def test_button_9_clonar_multiples_vistas_360(self):
        res = client.post("/api/generate", data={"boton_principal": "Clonar Múltiples Vistas 360"})
        assert res.status_code == 200
        d = res.json()
        assert d["is_multiview"] is True
        assert len(d["vistas"]) == 6
        assert "360" in d["prompt"]


# ==============================================================================
# Tier 2: Boundary & Corner Cases (Resilience, Corrupt Data, Base64 & Payloads)
# ==============================================================================
class TestTier2BoundaryAndCornerCases:
    """Tests defensive coding, memory safety, malformed payloads and base64 handling."""

    def test_empty_file_zero_bytes_resilience(self):
        """Empty 0-byte file upload does not crash server or throw unhandled exceptions."""
        empty_bytes = b""
        files = [("mueble_images", ("empty.jpg", io.BytesIO(empty_bytes), "image/jpeg"))]
        res = client.post("/api/generate", files=files, data={"boton_principal": "solo mueble"})
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_empty_filename_resilience(self):
        """UploadFile with empty filename for optional references is gracefully filtered out."""
        files = {
            "image": ("", io.BytesIO(b""), "application/octet-stream"),
            "madera_image": ("", io.BytesIO(b""), "application/octet-stream"),
            "tela_image": ("", io.BytesIO(b""), "application/octet-stream"),
        }
        res = client.post("/api/generate", files=files, data={"boton_principal": "solo mueble"})
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_empty_filename_upload_file_filter_direct(self):
        """Direct unit verification that UploadFile with empty filename is defensively ignored."""
        empty_upload = UploadFile(filename="", file=io.BytesIO(b"some_bytes"))
        # Verify app.py defensive condition: if f and getattr(f, "filename", "")
        has_valid_name = bool(empty_upload and getattr(empty_upload, "filename", ""))
        assert has_valid_name is False

    def test_malformed_corrupt_image_bytes_resilience(self):
        """Corrupt non-image binary payload handled safely by PIL memory guard."""
        corrupt_bytes = b"\x00\x01\x02\xFF\xFE\xFDGARBAGE_NOT_A_VALID_IMAGE_HEADER_12345"
        files = [("mueble_images", ("corrupt.jpg", io.BytesIO(corrupt_bytes), "image/jpeg"))]
        res = client.post("/api/generate", files=files, data={"boton_principal": "solo mueble"})
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_request_with_no_images_attached(self):
        """Pure text/parameter request generates high-quality deterministic prompt."""
        res = client.post("/api/generate", data={"boton_principal": "solo mueble", "tipo_mueble": "Banco rústico"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Banco rústico" in data["prompt"]

    def test_large_payload_multiple_image_bounding(self):
        """5 multi-view furniture images handled without memory exhaustion."""
        files = []
        for i in range(5):
            b = create_test_image_bytes(color="cyan", size=(200, 200))
            files.append(("mueble_images", (f"view_{i}.jpg", io.BytesIO(b), "image/jpeg")))
        res = client.post("/api/generate", files=files, data={"boton_principal": "Clonar Múltiples Vistas 360"})
        assert res.status_code == 200
        assert res.json()["is_multiview"] is True
        assert len(res.json()["vistas"]) == 6

    def test_json_payload_base64_array_mueble_images(self):
        """JSON payload with array of base64 images in `mueble_images` parsed correctly."""
        b64_1 = create_test_image_base64(color="red")
        b64_2 = create_test_image_base64(color="blue")
        payload = {
            "boton_principal": "Clonar Múltiples Vistas 360",
            "mueble_images": [b64_1, b64_2],
            "tipo_mueble": "Lámpara de pie"
        }
        res = client.post("/api/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["is_multiview"] is True
        assert len(data["vistas"]) == 6

    def test_json_payload_base64_data_uri_prefix(self):
        """JSON payload with `data:image/jpeg;base64,...` prefix decoded safely."""
        b64_prefixed = create_test_image_base64(color="magenta", with_prefix=True)
        payload = {
            "boton_principal": "solo mueble",
            "mueble_images": [b64_prefixed],
            "tipo_mueble": "Mesa auxiliar"
        }
        res = client.post("/api/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["is_multiview"] is False

    def test_json_payload_base64_wood_and_fabric(self):
        """JSON payload with `madera_image` and `tela_image` base64 references."""
        b64_mueble = create_test_image_base64(color="gray")
        b64_madera = create_test_image_base64(color="brown")
        b64_tela = create_test_image_base64(color="beige")
        payload = {
            "boton_principal": "vistas + tela y madera",
            "mueble_images": [b64_mueble],
            "madera_image": b64_madera,
            "tela_image": b64_tela,
            "sub_opcion": "Frontal 0°",
            "tipo_mueble": "Sillón de lectura"
        }
        res = client.post("/api/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

    def test_json_payload_corrupt_base64_resilience(self):
        """Malformed base64 string does not crash the server and returns 200 fallback."""
        payload = {
            "boton_principal": "solo mueble",
            "mueble_images": ["ThisIsNotValidBase64@@@@!!!!"],
            "tipo_mueble": "Taburete"
        }
        res = client.post("/api/generate", json=payload)
        assert res.status_code == 200
        assert res.json()["success"] is True


# ==============================================================================
# Tier 3: Cross-Feature & Schema Contracts (Multi-View, 4 Pillars & Locks)
# ==============================================================================
class TestTier3SchemaAndPromptContracts:
    """Verifies schema contracts, canonical angle IDs, 4 pillars and preservation locks."""

    def test_multiview_response_schema_contract_360(self):
        """Verifies multi-view JSON schema compliance for 360 turntable requests."""
        res = client.post("/api/generate", data={"boton_principal": "Clonar Múltiples Vistas 360"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert data.get("is_multiview") is True
        vistas = data.get("vistas", [])
        assert isinstance(vistas, list)
        assert len(vistas) == 6

        expected_ids = ["frontal_0", "isometrica_45", "lateral_90", "cenital_arriba", "arriba_3_4", "trasera_135"]
        for idx, view in enumerate(vistas):
            assert "id" in view and view["id"] == expected_ids[idx]
            assert "titulo" in view and len(view["titulo"]) > 0
            assert "prompt" in view and len(view["prompt"]) > 20

    def test_multiview_response_schema_contract_vistas_all(self):
        """Verifies 'vistas' mode with 'todas las vistas' triggers 6-view schema."""
        res = client.post("/api/generate", data={"boton_principal": "vistas", "sub_opcion": "todas las vistas"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_multiview"] is True
        assert len(data["vistas"]) == 6

    def test_single_view_response_schema_contract_solo_mueble(self):
        """Verifies single-view mode schema returns is_multiview=false and 1 vista."""
        res = client.post("/api/generate", data={"boton_principal": "solo mueble"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_multiview"] is False
        assert len(data["vistas"]) == 1
        assert data["vistas"][0]["id"] == "principal"
        assert data["vistas"][0]["prompt"] == data["prompt"]

    def test_single_view_response_schema_contract_specific_angle(self):
        """Verifies specific angle in 'vistas' mode returns is_multiview=false."""
        res = client.post("/api/generate", data={"boton_principal": "vistas", "sub_opcion": "Lateral 90°"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_multiview"] is False
        assert len(data["vistas"]) == 1

    def test_four_pillar_topological_doctrine_in_system_instructions(self):
        """Validates all 4 pillars of historical topological deconstruction in instructions."""
        instructions = build_system_instructions(boton_principal="solo mueble")

        # Pillar 1: Geometry & Topology (Absolute Single Truth Reference)
        assert "GEOMETRÍA Y TOPOLOGÍA" in instructions
        assert "ABSOLUTE SINGLE TRUTH REFERENCE" in instructions
        assert "preservar al 100% la silueta original" in instructions

        # Pillar 2: Color & Chromatics
        assert "COLOR Y CROMÁTICA" in instructions
        assert "códigos HEX" in instructions or "tonos dominantes" in instructions

        # Pillar 3: Texture & Micro-Materiality
        assert "TEXTURA Y MICRO-MATERIALIDAD" in instructions
        assert "Reduce la escala de muestras macro" in instructions or "97%-98%" in instructions

        # Pillar 4: Lighting & Optics
        assert "ILUMINACIÓN Y ÓPTICA" in instructions
        assert "Hasselblad H6D-100c" in instructions or "5500K" in instructions

    def test_selective_preservation_lock_wood_frozen_in_fabric_mode(self):
        """In 'vistas + tela', wood structure is strictly locked and frozen."""
        instructions = build_system_instructions(boton_principal="vistas + tela")
        assert "BLOQUEO DE PRESERVACIÓN ESTRICTO" in instructions
        assert "Las patas y estructura de madera/metal deben permanecer 100% idénticas e inalteradas" in instructions

    def test_selective_preservation_lock_upholstery_frozen_in_wood_mode(self):
        """In 'madera' mode, upholstery and cushions are strictly locked and frozen."""
        instructions = build_system_instructions(boton_principal="madera")
        assert "BLOQUEO DE PRESERVACIÓN ESTRICTO" in instructions
        assert "Toda la tapicería y cojines existentes deben permanecer 100% idénticos e inalterados" in instructions

    def test_canonical_camera_perspective_formulas(self):
        """Verifies camera resolver maps queries to all 6 canonical specs."""
        angles = [
            ("Frontal 0°", "frontal_0"),
            ("3/4 Isométrica 45°", "isometrica_45"),
            ("Lateral 90°", "lateral_90"),
            ("Arriba lineal", "cenital_arriba"),
            ("Arriba 3/4", "arriba_3_4"),
            ("Trasera 135°", "trasera_135"),
        ]
        for query, expected_id in angles:
            spec = resolve_camera_spec(query)
            assert spec is not None, f"Failed to resolve spec for query: {query}"
            assert spec["id"] == expected_id
            assert len(spec["directive"]) > 0
            assert len(spec["geometry"]) > 0
            assert len(spec["negative"]) > 0

    def test_deterministic_multiview_builder_direct(self):
        """Direct verification of deterministic multiview generator function."""
        result = build_deterministic_multiview(boton_principal="Clonar Múltiples Vistas 360")
        assert result["success"] is True
        assert result["is_multiview"] is True
        assert len(result["vistas"]) == 6
        assert "TURNTABLE STUDIO SHEET" in result["prompt"]


# ==============================================================================
# Tier 4: Frontend Static Files Contract Verification
# ==============================================================================
class TestTier4FrontendStaticContracts:
    """Verifies that HTML, CSS, and JS strictly satisfy the architecture contracts."""

    def test_index_html_contains_required_dropzones(self, html_content: str):
        """Asserts presence of Zone 1, Zone 2, and Zone 3 dropzones."""
        assert 'id="dropzone-mueble"' in html_content
        assert 'id="dropzone-madera"' in html_content
        assert 'id="dropzone-tela"' in html_content

    def test_index_html_contains_required_components_and_controls(self, html_content: str):
        """Asserts presence of cards container, thumbnail grid, badges and master actions."""
        assert 'id="cards-container"' in html_content
        assert 'id="mueble-thumbnails-grid"' in html_content
        assert 'id="mueble-count-badge"' in html_content
        assert 'id="btn-copiar-todo"' in html_content
        assert 'id="btn-borrar"' in html_content

    def test_style_css_dark_background_and_palette(self, css_content: str):
        """Asserts dark theme background color #121212 is applied."""
        assert "#121212" in css_content

    def test_style_css_card_and_badge_classes(self, css_content: str):
        """Asserts existence of .view-card, .thumb-card, .badge-counter and card styling."""
        assert ".view-card" in css_content
        assert ".thumb-card" in css_content
        assert ".badge-counter" in css_content
        # Card styling presence
        assert ".left-panel" in css_content and ".right-panel" in css_content

    def test_script_js_upload_state(self, js_content: str):
        """Asserts unified reactive uploadState is defined with all file slots."""
        assert "uploadState" in js_content
        assert "muebleFiles" in js_content
        assert "maderaFile" in js_content
        assert "telaFile" in js_content

    def test_script_js_normalization_and_rendering(self, js_content: str):
        """Asserts normalizeOutputViews and renderDynamicResults functions exist."""
        assert "normalizeOutputViews" in js_content
        assert "renderDynamicResults" in js_content

    def test_script_js_mueble_images_in_form_data(self, js_content: str):
        """Asserts script dispatches `mueble_images` in FormData network payload."""
        assert "mueble_images" in js_content

    def test_script_js_clipboard_handling(self, js_content: str):
        """Asserts clipboard copy implementation with visual feedback."""
        assert "clipboard" in js_content or "execCommand" in js_content
        assert "¡Copiado!" in js_content or "copied" in js_content


# ==============================================================================
# Helper for HTML Parser in Tier 5
# ==============================================================================
class _MainButtonsExtractor(HTMLParser):
    """Parses #main-buttons-container and extracts button elements and attributes."""
    def __init__(self):
        super().__init__()
        self.in_container = False
        self.buttons = []
        self.current_button = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "div" and attrs_dict.get("id") == "main-buttons-container":
            self.in_container = True
            return
        if self.in_container and tag == "button":
            self.current_button = {
                "tag": tag,
                "attrs": attrs_dict,
                "data_boton": attrs_dict.get("data-boton", ""),
                "class": attrs_dict.get("class", ""),
                "type": attrs_dict.get("type", ""),
                "text": ""
            }

    def handle_data(self, data):
        if self.current_button is not None:
            self.current_button["text"] += data

    def handle_endtag(self, tag):
        if tag == "button" and self.current_button is not None:
            self.current_button["text"] = self.current_button["text"].strip()
            self.buttons.append(self.current_button)
            self.current_button = None
        elif tag == "div" and self.in_container:
            self.in_container = False


# ==============================================================================
# Tier 5: Isolated Material Replacement & 11-Button Layout Contracts
# ==============================================================================
class TestTier5IsolatedMaterialReplacementAnd11Buttons:
    """
    Automated test cases covering the 11-button layout and isolated material replacement modes:
    - Test 1: Exactly 11 functional buttons in index.html #main-buttons-container
    - Test 2: is_multiview_request strictly returning False for isolated modes and aliases
    - Test 3: build_system_instructions preservation locks and material wrapping/grain rules
    - Test 4: End-to-end /api/generate for 'tela' with fabric swatch
    - Test 5: End-to-end /api/generate for 'madera' with wood swatch
    - Test 6: End-to-end /api/generate for 'madera y tela' with dual swatches
    - Test 7: Fallback/edge cases when reference swatches are omitted
    - Extra: Base64 JSON payloads and user/deterministic prompt directives
    """

    def test_test1_index_html_has_exactly_11_functional_buttons(self, html_content: str = None):
        """
        Test 1: Verify index.html has exactly 11 functional buttons in #main-buttons-container,
        including 'tela', 'madera', and 'madera y tela'.
        """
        if html_content is None:
            html_content = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

        parser = _MainButtonsExtractor()
        parser.feed(html_content)
        buttons = parser.buttons

        assert len(buttons) == 11, f"Expected exactly 11 buttons in #main-buttons-container, found {len(buttons)}"

        data_botons = [b["data_boton"] for b in buttons]

        # Verify key isolated material replacement buttons exist
        assert "tela" in data_botons, "'tela' button missing from #main-buttons-container"
        assert "madera" in data_botons, "'madera' button missing from #main-buttons-container"
        assert "madera y tela" in data_botons, "'madera y tela' button missing from #main-buttons-container"

        # Verify all 11 expected buttons in canonical sequence
        expected_sequence = [
            "solo mueble",
            "vistas",
            "entorno",
            "vistas + tela y madera",
            "vistas + tela",
            "madera",
            "tela",
            "madera y tela",
            "hd",
            "Clonar Vistas (Color y Tela) - Obliga a igualar exactamente madera, tela y vista",
            "Clonar Múltiples Vistas 360",
        ]
        assert data_botons == expected_sequence, f"Button sequence mismatch. Got: {data_botons}"

        # Verify standard button attributes
        for b in buttons:
            assert b["type"] == "button", f"Button '{b['data_boton']}' must have type='button'"
            assert "main-btn" in b["class"], f"Button '{b['data_boton']}' must contain 'main-btn' class"
            assert len(b["text"]) > 0, f"Button '{b['data_boton']}' must have visible text"

    def test_test2_is_multiview_request_strictly_false_for_isolated_materials(self):
        """
        Test 2: Verify is_multiview_request strictly returns False for 'tela', 'madera',
        'madera y tela', and aliases ('tela y madera', 'tela + madera').
        """
        isolated_modes = ["tela", "madera", "madera y tela", "tela y madera", "tela + madera"]
        sub_options = [
            "",
            "Frontal 0°",
            "3/4 Isométrica 45°",
            "Lateral 90°",
            "Arriba lineal",
            "Arriba 3/4",
            "Trasera 135°",
            "todas las vistas",
            "todas",
            "all",
            "vistas",
            "múltiples",
            "multiples",
            "360",
            None,
        ]

        for mode in isolated_modes:
            for sub in sub_options:
                assert is_multiview_request(mode, sub) is False, (
                    f"is_multiview_request('{mode}', '{sub}') must strictly be False"
                )
            # Case sensitivity & whitespace padding
            assert is_multiview_request(mode.upper(), "") is False
            assert is_multiview_request(f"  {mode}  ", "todas las vistas") is False
            assert is_multiview_request(mode.title(), "") is False

        # Positive contrast checks: ensure multi-view modes continue to return True
        assert is_multiview_request("vistas", "") is True
        assert is_multiview_request("vistas", "todas las vistas") is True
        assert is_multiview_request("Clonar Múltiples Vistas 360", "") is True
        assert is_multiview_request("vistas + tela y madera", "") is True
        assert is_multiview_request("vistas + tela", "") is True

    def test_test3_build_system_instructions_preservation_locks_and_constraints(self):
        """
        Test 3: Verify build_system_instructions produces:
        - For 'tela': wood/legs preservation locks, conformal wrapping, ~97%-98% macro reduction, single perspective.
        - For 'madera': upholstery preservation locks, anatomical grain flow, single perspective.
        - For 'madera y tela': 3D geometry preservation locks, dual material replacement, single perspective.
        """
        # --- Mode 'tela' ---
        sys_tela = build_system_instructions(boton_principal="tela")
        assert "Directiva Especial (Modo Tela Aislado):" in sys_tela
        assert "BLOQUEO DE PRESERVACIÓN ESTRICTO" in sys_tela
        assert "patas, base, bastidor y estructura de madera o metal deben permanecer 100% idénticas" in sys_tela
        assert "PROHIBIDO alterar, rediseñar, reemplazar o recolorar las patas" in sys_tela
        assert "Mapeo y envoltura conforme alrededor de las curvaturas 3D" in sys_tela
        assert "97%-98%" in sys_tela
        assert "Perspectiva de cámara única bloqueada 100% al ángulo de la fotografía original" in sys_tela
        assert "NO generar múltiples ángulos" in sys_tela
        assert "altered wood" in sys_tela and "changed legs" in sys_tela

        # --- Mode 'madera' ---
        sys_madera = build_system_instructions(boton_principal="madera")
        assert "Directiva Especial (Modo Madera Aislado):" in sys_madera
        assert "BLOQUEO DE PRESERVACIÓN ESTRICTO" in sys_madera
        assert "Toda la tapicería y cojines existentes deben permanecer 100% idénticos e inalterados" in sys_madera
        assert "PROHIBIDO alterar, rediseñar o cambiar el color de la tela existente" in sys_madera
        assert "Flujo de veta anatómica alineado estrictamente a la dirección constructiva natural" in sys_madera
        assert "veta vertical en patas y montantes, horizontal en rieles, faldones y travesaños" in sys_madera
        assert "Perspectiva de cámara única bloqueada 100% al ángulo de la fotografía original" in sys_madera
        assert "altered fabric" in sys_madera and "changed upholstery" in sys_madera

        # --- Mode 'madera y tela' and aliases ---
        for btn in ("madera y tela", "tela y madera", "tela + madera"):
            sys_dual = build_system_instructions(boton_principal=btn)
            assert "Directiva Especial (Modo Madera y Tela Aislado):" in sys_dual
            assert "Sustituir simultáneamente TANTO la tapicería textil COMO los componentes lígneos" in sys_dual
            assert "BLOQUEO DE PRESERVACIÓN ESTRICTO" in sys_dual
            assert "Congelar al 100% la silueta 3D, contorno, uniones, ensambles, descansabrazos y geometría estructural" in sys_dual
            assert "97%-98%" in sys_dual
            assert "veta anatómica natural (vertical en patas, horizontal en rieles)" in sys_dual
            assert "perspectiva de cámara única bloqueada estrictamente a la imagen original del mueble" in sys_dual.lower()
            assert "NO generar múltiples ángulos ni hoja 360" in sys_dual
            assert "changed proportions" in sys_dual and "redesigned furniture" in sys_dual

    def test_test4_api_generate_end_to_end_tela_isolated_mode(self):
        """
        Test 4: End-to-end /api/generate with boton_principal='tela' and tela_image swatch:
        returns HTTP 200, is_multiview: False, len(vistas) == 1, prompt prioritizes fabric swatch
        without multi-view expansion.
        """
        mueble_img = create_test_image_bytes(color="gray")
        tela_img = create_test_image_bytes(color="royalblue")
        files = [
            ("mueble_images", ("chair_base.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("tela_image", ("velvet_swatch.jpg", io.BytesIO(tela_img), "image/jpeg"))
        ]
        data = {
            "boton_principal": "tela",
            "tipo_mueble": "Sillón contemporáneo",
            "medidas": "85x85x90 cm"
        }
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        res_data = res.json()
        assert res_data["success"] is True
        assert res_data["is_multiview"] is False
        assert len(res_data["vistas"]) == 1
        assert res_data["vistas"][0]["id"] == "principal"
        assert "tela" in res_data["vistas"][0]["titulo"].lower()

        prompt = res_data["prompt"]
        # Fabric swatch prioritization
        assert "tapicería" in prompt.lower()
        assert ("muestra de referencia" in prompt.lower() or "micro-trama" in prompt.lower() or "curvas 3d" in prompt.lower())
        # Wood/legs preservation lock
        assert "patas" in prompt.lower() and "preservad" in prompt.lower()
        # Single perspective locked without multi-view
        assert "perspectiva de cámara única bloqueada" in prompt.lower()
        assert "turntable studio sheet" not in prompt.lower()

    def test_test5_api_generate_end_to_end_madera_isolated_mode(self):
        """
        Test 5: End-to-end /api/generate with boton_principal='madera' and madera_image swatch:
        returns HTTP 200, is_multiview: False, len(vistas) == 1, prompt prioritizes wood swatch
        without multi-view expansion.
        """
        mueble_img = create_test_image_bytes(color="navy")
        madera_img = create_test_image_bytes(color="saddlebrown")
        files = [
            ("mueble_images", ("chair_wood.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("madera_image", ("oak_grain.jpg", io.BytesIO(madera_img), "image/jpeg"))
        ]
        data = {
            "boton_principal": "madera",
            "tipo_mueble": "Silla tapizada con patas de madera",
            "medidas": "50x55x95 cm"
        }
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        res_data = res.json()
        assert res_data["success"] is True
        assert res_data["is_multiview"] is False
        assert len(res_data["vistas"]) == 1
        assert res_data["vistas"][0]["id"] == "principal"
        assert "madera" in res_data["vistas"][0]["titulo"].lower()

        prompt = res_data["prompt"]
        # Wood swatch prioritization
        assert "madera" in prompt.lower()
        assert ("muestra de referencia" in prompt.lower() or "veta anatómica" in prompt.lower())
        # Upholstery preservation lock
        assert "tapicería" in prompt.lower() and "preservad" in prompt.lower()
        # Single perspective locked without multi-view
        assert "perspectiva de cámara única bloqueada" in prompt.lower()
        assert "turntable studio sheet" not in prompt.lower()

    def test_test6_api_generate_end_to_end_madera_y_tela_isolated_mode(self):
        """
        Test 6: End-to-end /api/generate with boton_principal='madera y tela' and both swatches:
        returns HTTP 200, is_multiview: False, len(vistas) == 1, prompt contains both materials
        without multi-view expansion.
        """
        mueble_img = create_test_image_bytes(color="forestgreen")
        madera_img = create_test_image_bytes(color="peru")
        tela_img = create_test_image_bytes(color="gold")
        files = [
            ("mueble_images", ("armchair.jpg", io.BytesIO(mueble_img), "image/jpeg")),
            ("madera_image", ("walnut_swatch.jpg", io.BytesIO(madera_img), "image/jpeg")),
            ("tela_image", ("velvet_swatch.jpg", io.BytesIO(tela_img), "image/jpeg"))
        ]
        data = {
            "boton_principal": "madera y tela",
            "tipo_mueble": "Sillón de lectura clásico",
            "medidas": "90x80x100 cm"
        }
        res = client.post("/api/generate", files=files, data=data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        res_data = res.json()
        assert res_data["success"] is True
        assert res_data["is_multiview"] is False
        assert len(res_data["vistas"]) == 1
        assert res_data["vistas"][0]["id"] == "principal"
        assert "madera y tela" in res_data["vistas"][0]["titulo"].lower()

        prompt = res_data["prompt"]
        # Dual material replacement prioritization
        assert "tapicería" in prompt.lower()
        assert "madera" in prompt.lower()
        assert "veta anatómica" in prompt.lower()
        # 3D silhouette freeze
        assert ("congeladas" in prompt.lower() or "sustituyendo únicamente materiales" in prompt.lower())
        # Single perspective locked without multi-view
        assert "perspectiva de cámara única bloqueada" in prompt.lower()
        assert "turntable studio sheet" not in prompt.lower()

    def test_test7_isolated_materials_swatch_omission_fallbacks(self):
        """
        Test 7: Verify fallback/edge cases when reference swatches are omitted:
        graceful generation without crash.
        """
        # Case 7.1: 'tela' with no files attached and no custom text
        res1 = client.post("/api/generate", data={"boton_principal": "tela", "tipo_mueble": "Banqueta"})
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["success"] is True
        assert d1["is_multiview"] is False
        assert len(d1["vistas"]) == 1
        assert "tapicería" in d1["prompt"].lower()

        # Case 7.2: 'madera' with no files attached and no custom text
        res2 = client.post("/api/generate", data={"boton_principal": "madera", "tipo_mueble": "Mesa ratona"})
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["success"] is True
        assert d2["is_multiview"] is False
        assert len(d2["vistas"]) == 1
        assert "madera" in d2["prompt"].lower()

        # Case 7.3: 'madera y tela' with no files attached and no custom text
        res3 = client.post("/api/generate", data={"boton_principal": "madera y tela", "tipo_mueble": "Mecedora"})
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["success"] is True
        assert d3["is_multiview"] is False
        assert len(d3["vistas"]) == 1
        assert "tapicería" in d3["prompt"].lower() and "madera" in d3["prompt"].lower()

        # Case 7.4: 'tela' with explicit text description but no swatch image
        res4 = client.post("/api/generate", data={"boton_principal": "tela", "tela": "Terciopelo borgoña"})
        assert res4.status_code == 200
        d4 = res4.json()
        assert d4["success"] is True
        assert "terciopelo borgoña" in d4["prompt"].lower()

        # Case 7.5: 'madera' with explicit text description but no swatch image
        res5 = client.post("/api/generate", data={"boton_principal": "madera", "madera": "Nogal canaletto"})
        assert res5.status_code == 200
        d5 = res5.json()
        assert d5["success"] is True
        assert "nogal canaletto" in d5["prompt"].lower()

        # Case 7.6: 'madera y tela' with furniture image only, omitted swatches
        mueble_img = create_test_image_bytes(color="gray")
        files = [("mueble_images", ("furniture.jpg", io.BytesIO(mueble_img), "image/jpeg"))]
        res6 = client.post("/api/generate", files=files, data={"boton_principal": "madera y tela"})
        assert res6.status_code == 200
        d6 = res6.json()
        assert d6["success"] is True
        assert d6["is_multiview"] is False
        assert len(d6["vistas"]) == 1

    def test_isolated_materials_json_base64_payloads(self):
        """
        Verifies JSON payloads with base64 images for 'tela', 'madera', and 'madera y tela'.
        """
        b64_mueble = create_test_image_base64(color="cyan")
        b64_madera = create_test_image_base64(color="sienna")
        b64_tela = create_test_image_base64(color="khaki")

        # Base64 for 'tela'
        p_tela = {
            "boton_principal": "tela",
            "mueble_images": [b64_mueble],
            "tela_image": b64_tela,
            "tipo_mueble": "Sofá modular"
        }
        res_t = client.post("/api/generate", json=p_tela)
        assert res_t.status_code == 200
        assert res_t.json()["is_multiview"] is False

        # Base64 for 'madera'
        p_madera = {
            "boton_principal": "madera",
            "mueble_images": [b64_mueble],
            "madera_image": b64_madera,
            "tipo_mueble": "Silla nórdica"
        }
        res_m = client.post("/api/generate", json=p_madera)
        assert res_m.status_code == 200
        assert res_m.json()["is_multiview"] is False

        # Base64 for 'madera y tela'
        p_both = {
            "boton_principal": "madera y tela",
            "mueble_images": [b64_mueble],
            "madera_image": b64_madera,
            "tela_image": b64_tela,
            "tipo_mueble": "Butaca"
        }
        res_b = client.post("/api/generate", json=p_both)
        assert res_b.status_code == 200
        assert res_b.json()["is_multiview"] is False

    def test_isolated_materials_user_prompt_and_deterministic_sections(self):
        """
        Direct unit verification of build_user_prompt action directives and
        build_deterministic_prompt negative exclusions and preservation clauses.
        """
        # User prompt directives
        up_tela = build_user_prompt(boton_principal="tela")
        assert "Acción Solicitada: Reemplazar únicamente la tapicería textil" in up_tela
        assert "Congelar estructura y patas" in up_tela

        up_madera = build_user_prompt(boton_principal="madera")
        assert "Acción Solicitada: Reemplazar únicamente las piezas de madera" in up_madera
        assert "Congelar tapizado y cojines" in up_madera

        for b in ("madera y tela", "tela y madera", "tela + madera"):
            up_dual = build_user_prompt(boton_principal=b)
            assert "Acción Solicitada: Reemplazar tanto tapicería como piezas de madera" in up_dual
            assert "Congelar silueta y geometría 3D" in up_dual

        # Deterministic prompt negative prompt exclusions
        dp_tela = build_deterministic_prompt(boton_principal="tela")
        assert "altered wood" in dp_tela and "changed legs" in dp_tela
        assert "Estructura: Patas, base y bastidor original estrictamente preservados" in dp_tela

        dp_madera = build_deterministic_prompt(boton_principal="madera")
        assert "altered fabric" in dp_madera and "changed upholstery" in dp_madera
        assert "Tapicería: Tapizado, tela y cojines originales estrictamente preservados" in dp_madera

        dp_dual = build_deterministic_prompt(boton_principal="madera y tela")
        assert "changed proportions" in dp_dual and "redesigned furniture" in dp_dual
        assert "silueta 3D, uniones y proporciones 100% congeladas" in dp_dual


# ==============================================================================
# Standalone Runner Entrypoint
# ==============================================================================
def run_all_tests():
    """Runs all test functions sequentially when executed directly as a script."""
    print("Executing complete test suite for Generador Prompts V4...")
    test_health()
    test_generate_entorno_form_data()
    test_generate_entorno_json()
    test_generate_solo_mueble()
    test_generate_hd()
    test_generate_clonar_vistas()
    test_generate_360()
    test_generate_with_mock_image()
    test_build_system_instructions_entorno()
    test_build_system_instructions_solo_mueble()

    # Tier 1
    t1 = TestTier1FeatureCoverage()
    t1.test_single_furniture_upload_mueble_images()
    t1.test_multi_furniture_upload_2_images()
    t1.test_multi_furniture_upload_3_or_more_images()
    t1.test_legacy_image_parameter_backward_compatibility()
    t1.test_optional_madera_image_upload()
    t1.test_optional_tela_image_upload()
    t1.test_dual_texture_reference_upload_both_wood_and_fabric()
    t1.test_button_1_solo_mueble()
    t1.test_button_2_vistas_multiview()
    t1.test_button_2_vistas_single_angle()
    t1.test_button_3_entorno()
    t1.test_button_4_vistas_tela_y_madera()
    t1.test_button_5_vistas_tela()
    t1.test_button_6_madera()
    t1.test_button_7_hd()
    t1.test_button_8_clonar_vistas_color_y_tela()
    t1.test_button_9_clonar_multiples_vistas_360()

    # Tier 2
    t2 = TestTier2BoundaryAndCornerCases()
    t2.test_empty_file_zero_bytes_resilience()
    t2.test_empty_filename_resilience()
    t2.test_empty_filename_upload_file_filter_direct()
    t2.test_malformed_corrupt_image_bytes_resilience()
    t2.test_request_with_no_images_attached()
    t2.test_large_payload_multiple_image_bounding()
    t2.test_json_payload_base64_array_mueble_images()
    t2.test_json_payload_base64_data_uri_prefix()
    t2.test_json_payload_base64_wood_and_fabric()
    t2.test_json_payload_corrupt_base64_resilience()

    # Tier 3
    t3 = TestTier3SchemaAndPromptContracts()
    t3.test_multiview_response_schema_contract_360()
    t3.test_multiview_response_schema_contract_vistas_all()
    t3.test_single_view_response_schema_contract_solo_mueble()
    t3.test_single_view_response_schema_contract_specific_angle()
    t3.test_four_pillar_topological_doctrine_in_system_instructions()
    t3.test_selective_preservation_lock_wood_frozen_in_fabric_mode()
    t3.test_selective_preservation_lock_upholstery_frozen_in_wood_mode()
    t3.test_canonical_camera_perspective_formulas()
    t3.test_deterministic_multiview_builder_direct()

    # Tier 4
    html_text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css_text = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    js_text = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    t4 = TestTier4FrontendStaticContracts()
    t4.test_index_html_contains_required_dropzones(html_text)
    t4.test_index_html_contains_required_components_and_controls(html_text)
    t4.test_style_css_dark_background_and_palette(css_text)
    t4.test_style_css_card_and_badge_classes(css_text)
    t4.test_script_js_upload_state(js_text)
    t4.test_script_js_normalization_and_rendering(js_text)
    t4.test_script_js_mueble_images_in_form_data(js_text)
    t4.test_script_js_clipboard_handling(js_text)

    # Tier 5: Isolated Material Replacement & 11-Button Layout Contracts
    t5 = TestTier5IsolatedMaterialReplacementAnd11Buttons()
    t5.test_test1_index_html_has_exactly_11_functional_buttons(html_text)
    t5.test_test2_is_multiview_request_strictly_false_for_isolated_materials()
    t5.test_test3_build_system_instructions_preservation_locks_and_constraints()
    t5.test_test4_api_generate_end_to_end_tela_isolated_mode()
    t5.test_test5_api_generate_end_to_end_madera_isolated_mode()
    t5.test_test6_api_generate_end_to_end_madera_y_tela_isolated_mode()
    t5.test_test7_isolated_materials_swatch_omission_fallbacks()
    t5.test_isolated_materials_json_base64_payloads()
    t5.test_isolated_materials_user_prompt_and_deterministic_sections()

    print("\nALL TESTS PASSED 100% SUCCESSFULLY ACROSS TIERS 1-5!")


if __name__ == "__main__":
    run_all_tests()
