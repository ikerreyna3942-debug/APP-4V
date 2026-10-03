import os
import io
import json
import base64
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from PIL import Image, ImageOps

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.v4")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Generador Prompts V4")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ===========================================================================
# Canonical Perspective Formulas (V1-V3 Historical Standards)
# ===========================================================================
CAMERA_SPECS: Dict[str, Dict[str, str]] = {
    "frontal_0": {
        "id": "frontal_0",
        "titulo": "Vista Frontal (0°)",
        "name_es": "Vista Frontal 0°",
        "directive": "STRICT DIRECT FRONT VIEW (0-DEGREE FLAT ELEVATION)",
        "geometry": "Cámara perfectamente a nivel de los ojos (0° elevación), apuntando directo al eje frontal del mueble. Cero distorsión de perspectiva, elevación 2D ortogonal limpia, cero visibilidad de laterales o parte superior.",
        "negative": "angled, isometric, 3/4 view, side view, back view, top view, perspective distortion, visible sides, vanishing lines"
    },
    "isometrica_45": {
        "id": "isometrica_45",
        "titulo": "Vista 3/4 Isométrica (45°)",
        "name_es": "Vista 3/4 Isométrica 45°",
        "directive": "ELEVATED THREE-QUARTER 3/4 FRONT ISOMETRIC STUDIO PERSPECTIVE",
        "geometry": "Perspectiva isométrica comercial de catálogo 3/4 a 45 grados, ángulo elevado 15 grados hacia abajo. Exhibe tridimensionalidad, volumen de cojines, inclinación de descansabrazos y postura de patas.",
        "negative": "flat front, flat side, pure orthogonal, rear view, bird's-eye, high overhead, extreme wide angle distortion"
    },
    "lateral_90": {
        "id": "lateral_90",
        "titulo": "Vista Lateral Perfil (90°)",
        "name_es": "Vista Lateral 90°",
        "directive": "STRICT ORTHOGONAL SIDE PROFILE (90-DEGREE LATERAL VIEW)",
        "geometry": "Cámara en ángulo ortogonal estricto de 90 grados desde el lateral. Silueta de perfil completa de borde a borde, inclinación de respaldo y ensamble de patas. Cero puntos de fuga frontales.",
        "negative": "front view, 3/4 view, back view, top view, visible front cushions, perspective distortion"
    },
    "cenital_arriba": {
        "id": "cenital_arriba",
        "titulo": "Vista Cenital Superior (Arriba lineal 90°)",
        "name_es": "Vista Arriba lineal",
        "directive": "DIRECT TOP-DOWN CENITAL BIRD'S-EYE VIEW (90-DEGREE FLAT LAY)",
        "geometry": "Cámara posicionada directamente arriba del mueble apuntando verticalmente hacia abajo a 90 grados. Huella geométrica superior real, profundidad de asientos y cojines en planta ortogonal pura.",
        "negative": "front view, side view, legs visible from front, angled view, perspective distortion, eye level"
    },
    "arriba_3_4": {
        "id": "arriba_3_4",
        "titulo": "Vista Superior 3/4 (Arriba 3/4)",
        "name_es": "Vista Arriba 3/4",
        "directive": "ELEVATED TOP-DOWN THREE-QUARTER VIEW (HIGH-ANGLE 3/4 ISOMETRIC)",
        "geometry": "Perspectiva elevada superior tres cuartos (inclinación de 35° a 45° hacia abajo, 45° de rotación). Captura armónicamente planos horizontales de asiento, profundidad y estructura inferior.",
        "negative": "ground level, eye-level flat front, flat side profile, pure zenithal 90-degree flat lay"
    },
    "trasera_135": {
        "id": "trasera_135",
        "titulo": "Vista Trasera (135°)",
        "name_es": "Vista Trasera 135°",
        "directive": "3/4 REAR ISOMETRIC PERSPECTIVE (135-DEGREE BACK 3/4 VIEW)",
        "geometry": "Perspectiva comercial tres cuartos posterior a 135 grados (45 grados desde el perfil trasero). Revela confección del respaldo, costuras traseras, tapicería posterior y patas traseras.",
        "negative": "front view, front cushions, direct front face, top-down flat lay"
    }
}

def resolve_camera_spec(camera_query: str) -> Optional[Dict[str, str]]:
    q = (camera_query or "").strip().lower()
    if not q:
        return None
    if "lateral" in q or "perfil" in q:
        return CAMERA_SPECS["lateral_90"]
    if "cenital" in q or "lineal" in q or ("arriba" in q and "3/4" not in q and "superior" not in q):
        return CAMERA_SPECS["cenital_arriba"]
    if ("arriba" in q and ("3/4" in q or "superior" in q)) or "superior 3/4" in q:
        return CAMERA_SPECS["arriba_3_4"]
    if "trasera" in q or "135" in q or "posterior" in q or "back" in q:
        return CAMERA_SPECS["trasera_135"]
    if "isom" in q or "45" in q or "3/4" in q:
        return CAMERA_SPECS["isometrica_45"]
    if "frontal" in q or "0°" in q or "0 deg" in q or "0deg" in q or "frente" in q:
        return CAMERA_SPECS["frontal_0"]
    if "90" in q:
        return CAMERA_SPECS["lateral_90"]
    if "0" in q:
        return CAMERA_SPECS["frontal_0"]
    return None

def is_multiview_request(boton_principal: str, sub_opcion: str) -> bool:
    btn = (boton_principal or "").strip().lower()
    sub = (sub_opcion or "").strip().lower()
    
    # 1. Explicit 360 mode
    if "360" in btn or "clonar múltiples vistas 360" in btn or "clonar multiples vistas 360" in btn:
        return True
    
    # 2. Vistas modes without a specific single angle selected
    if btn in ("vistas", "vistas + tela y madera", "vistas + tela"):
        if not sub or sub in ("todas las vistas", "todas", "all", "vistas", "múltiples", "multiples"):
            return True
            
    return False

# ===========================================================================
# Image Preprocessing & Sanitization Engine (<50MB RAM Guard)
# ===========================================================================
def optimize_image_bytes(raw_bytes: Optional[bytes], max_dim: int = 1600) -> Optional[bytes]:
    if not raw_bytes or len(raw_bytes) == 0:
        return None
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Auto-orient based on EXIF tags
            img = ImageOps.exif_transpose(img)
            # Flatten alpha/transparency onto pure #FFFFFF background
            if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
                
            # Proportional resize maintaining aspect ratio
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85, optimize=True)
            return out.getvalue()
    except Exception as e:
        logger.warning(f"Error procesando bytes de imagen: {e}")
        return None

def decode_base64_image(val: Any) -> Optional[bytes]:
    if not val or not isinstance(val, str):
        return None
    try:
        if "base64," in val:
            _, b64data = val.split("base64,", 1)
        elif val.startswith("data:image"):
            _, b64data = val.split(",", 1)
        else:
            b64data = val
        decoded = base64.b64decode(b64data)
        return decoded if len(decoded) > 0 else None
    except Exception as e:
        logger.warning(f"Error decodificando imagen base64: {e}")
        return None

# ===========================================================================
# System Instructions & Multimodal Prompt Generation
# ===========================================================================
def build_system_instructions(
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = "",
    multiview: bool = False
) -> str:
    btn = (boton_principal or "").strip().lower()
    is_entorno = (btn == "entorno") or bool((lugar_mueble or "").strip())

    intro = (
        "Actúa como un Director de Arte de Mobiliario Comercial galardonado, Diseñador de Interiores de Alta Gama "
        "y Director de Fotogrametría CGI e Hiperrealismo técnico especializado en motores de difusión "
        "(Google AI Studio, Gemini, ChatGPT DALL-E 3, Midjourney v6.1 e Imagen 3).\n\n"
        "DOCTRINA DE VERDAD ÚNICA Y DESCONSTRUCCIÓN TOPOLÓGICA EN 4 PILARES:\n"
        "1. GEOMETRÍA Y TOPOLOGÍA (ABSOLUTE SINGLE TRUTH REFERENCE): Las fotos del mueble principal representan la verdad "
        "geométrica absoluta e inmutable. Debes preservar al 100% la silueta original, curvaturas, uniones, descansabrazos, "
        "patas, acolchado, capitoné y proporciones exactas. PROHIBIDO rediseñar, distorsionar, añadir o quitar piezas estructurales.\n"
        "2. COLOR Y CROMÁTICA: Identifica tonos dominantes, subtonos sutiles, brillo y códigos HEX representativos.\n"
        "3. TEXTURA Y MICRO-MATERIALIDAD: Disecciona propiedades micro-textiles (densidad de bouclé, trama de lino, poro de cuero, "
        "terciopelo) y vetas lígneas. Reduce la escala de muestras macro (~97%-98%) y envuelve el material de forma conforme "
        "sobre el volumen 3D respetando pliegues y sombras.\n"
        "4. ILUMINACIÓN Y ÓPTICA: Parámetros comerciales de cámara (Hasselblad H6D-100c formato medio, lente 85mm/120mm macro, "
        "f/11 para nitidez total de catálogo, iluminación de estudio 5500K balanceada con sombras de oclusión ambiental pura).\n\n"
        "Reglas estrictas para estructurar el prompt de salida:\n"
    )

    if is_entorno:
        target_setting = (lugar_mueble or "").strip() or "el entorno arquitectónico especificado"
        target_furniture = (tipo_mueble or "").strip() or "el mueble de referencia"
        target_scale = (medidas or "").strip() or "escala y proporciones reales"
        rule_1 = (
            f"1. Configuraciones Base y Ambientación: NO exigir fondo blanco sólido (#FFFFFF). "
            f"En su lugar, escenificar fotográficamente la pieza '{target_furniture}' integrada de forma fotorrealista "
            f"en su contexto espacial de destino: '{target_setting}'. Mantener rigurosamente escala real, volumen y proporciones "
            f"arquitectónicas basadas en: '{target_scale}', con iluminación ambiental coherente, sombras de contacto naturales y oclusión ambiental precisa.\n"
        )
    elif btn == "solo mueble":
        rule_1 = (
            "1. Configuraciones Base (Solo Mueble): Siempre iniciar el prompt con: 'Tamaño de lienzo: 2080x2080 px', "
            "'Fondo: Blanco sólido (#FFFFFF)' y 'Posición: Perfectamente centrado'. Mueble aislado en estudio de producto, "
            "sin accesorios distractores ni entorno decorativo, con iluminación de catálogo limpio y sombra de contacto neutra muy suave en base inferior.\n"
        )
    else:
        rule_1 = (
            "1. Configuraciones Base: Siempre debes iniciar el prompt con: 'Tamaño de lienzo: 2080x2080 px', "
            "'Fondo: Blanco sólido (#FFFFFF)' y 'Posición: Perfectamente centrado'.\n"
        )

    rule_2 = (
        "2. Fidelidad Estructural: Describe la geometría, proporciones y detalles de ensamble del mueble de la foto con precisión técnica. "
        "El mueble debe ser una réplica geométrica exacta del objeto físico suministrado.\n"
    )

    camera_target = (sub_opcion or vista or "").strip()
    if camera_target:
        rule_3 = (
            f"3. Vistas y Ángulo de Cámara: Aplica estrictamente el ángulo de cámara indicado: '{camera_target}'. "
            "Ajusta la perspectiva, altura de lente y punto focal para reflejar exactamente esta vista.\n"
        )
    else:
        rule_3 = "3. Vistas y Estilos: Aplica estrictamente la vista solicitada. Si es dibujo técnico, especifica ilustraciones isométricas puramente lineales sin sombras/color. Si es toma superior, especifica inclinación del 25%.\n"

    rule_4 = "4. Materiales: Integra las texturas indicadas con precisión fotorrealista.\n"
    rule_5 = "5. Exclusiones: Indica claramente qué NO generar.\n"

    specialized_rules = []
    if btn == "hd":
        specialized_rules.append(
            "Directiva Especial (Modo HD 8K): Priorizar máxima definición y nitidez de micro-texturas (enfoque macro 8K UHD). "
            "Detallar a nivel hiperrealista la porosidad del material, vetas de madera a nivel de fibra, textura de tejido/trama de tela a nivel milimétrico, "
            "reflejos especulares exactos y uniones estructurales de alta precisión sin artefactos de compresión ni acabados CGI plásticos."
        )
    elif "clonar vistas (color y tela)" in btn:
        specialized_rules.append(
            "Directiva Especial (Clonar Vistas - Color y Tela): Obligación estricta de reproducir con fidelidad 100% idéntica "
            "el color exacto, veta y acabado de la madera, la textura, tono y tramado de la tela, y el ángulo de cámara especificado. "
            "No alterar ni sustituir los materiales ni la geometría de la pieza original bajo ninguna circunstancia."
        )
    elif "clonar múltiples vistas 360" in btn or "360" in btn or multiview:
        specialized_rules.append(
            "Directiva Especial (Clonar Múltiples Vistas 360): Estructurar el prompt técnico para una hoja de consistencia rotacional "
            "multi-ángulo 360 grados (turntable studio sheet). Especificar iluminación de estudio 360 constante, mismo nivel de horizonte, "
            "y rigurosa coherencia geométrica en todas las fases de rotación."
        )
    elif btn == "vistas + tela y madera":
        specialized_rules.append(
            "Directiva Especial (Vistas + Tela y Madera): Integrar con máxima prioridad la perspectiva de cámara seleccionada junto con la especificación "
            "detallada del acabado de madera indicado y el patrón/textura textil solicitado, preservando 100% la geometría estructural."
        )
    elif btn == "vistas + tela":
        specialized_rules.append(
            "Directiva Especial (Vistas + Tela): Enfocar la atención en el ángulo de cámara exacto y en la sustitución/descripción fotorrealista de la tapicería textil. "
            "BLOQUEO DE PRESERVACIÓN ESTRICTO: Las patas y estructura de madera/metal deben permanecer 100% idénticas e inalteradas."
        )
    elif btn == "madera":
        specialized_rules.append(
            "Directiva Especial (Madera): Describir en detalle el tipo de madera, patrón de veta, corte, tonalidad, barniz y tratamiento superficial. "
            "BLOQUEO DE PRESERVACIÓN ESTRICTO: Toda la tapicería y cojines existentes deben permanecer 100% idénticos e inalterados."
        )

    spec_text = ""
    if specialized_rules:
        spec_text = "\n" + "\n".join(specialized_rules) + "\n"

    if multiview:
        outro = (
            "\nFORMATO DE RESPUESTA EXCLUSIVO PARA MODO MULTI-VISTA:\n"
            "Debes responder ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:\n"
            "{\n"
            '  "vistas": [\n'
            '    {"id": "frontal_0", "titulo": "Vista Frontal (0°)", "prompt": "..."},\n'
            '    {"id": "isometrica_45", "titulo": "Vista 3/4 Isométrica (45°)", "prompt": "..."},\n'
            '    {"id": "lateral_90", "titulo": "Vista Lateral Perfil (90°)", "prompt": "..."},\n'
            '    {"id": "cenital_arriba", "titulo": "Vista Cenital Superior (Arriba lineal 90°)", "prompt": "..."},\n'
            '    {"id": "arriba_3_4", "titulo": "Vista Superior 3/4 (Arriba 3/4)", "prompt": "..."},\n'
            '    {"id": "trasera_135", "titulo": "Vista Trasera (135°)", "prompt": "..."}\n'
            "  ]\n"
            "}"
        )
    else:
        outro = (
            "\nSalida requerida: Devuelve ÚNICAMENTE el prompt final estructurado, optimizado y listo para ser procesado por un modelo generador de imágenes. "
            "No incluyas saludos, confirmaciones ni análisis."
        )

    return intro + rule_1 + rule_2 + rule_3 + rule_4 + rule_5 + spec_text + outro

def build_user_prompt(
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = ""
) -> str:
    lines = ["MODIFICADORES Y PARÁMETROS TÉCNICOS APLICADOS:"]

    if boton_principal:
        lines.append(f"Botón / Modo Principal: {boton_principal.strip()}")

    camera_angle = (sub_opcion or vista or "").strip()
    if camera_angle:
        lines.append(f"Vista requerida / Ángulo de cámara: {camera_angle}")

    if tipo_mueble.strip():
        lines.append(f"Tipo de mueble: {tipo_mueble.strip()}")

    if medidas.strip():
        lines.append(f"Medidas y Proporciones: {medidas.strip()}")

    if lugar_mueble.strip():
        lines.append(f"Lugar / Entorno del mueble: {lugar_mueble.strip()}")

    if tela.strip():
        lines.append(f"Tela / Material textil: {tela.strip()}")

    if madera.strip():
        lines.append(f"Madera / Acabado: {madera.strip()}")

    if ambiente.strip():
        lines.append(f"Ambiente / Estilo: {ambiente.strip()}")

    return "\n".join(lines)

def build_gemini_contents(
    mueble_bytes_list: List[bytes],
    madera_bytes: Optional[bytes] = None,
    tela_bytes: Optional[bytes] = None,
    user_prompt: str = ""
) -> List[Any]:
    contents = []

    # 1. Main Furniture Geometric References
    if mueble_bytes_list:
        contents.append(
            "=== REFERENCIA DE GEOMETRÍA Y VERDAD TOPOLÓGICA (MUEBLE PRINCIPAL) ===\n"
            "Las siguientes imágenes contienen la pieza de mobiliario física exacta. "
            "Debes analizar su geometría tridimensional, silueta, curvaturas, uniones, patas, descansabrazos "
            "y proporciones exactas. Esta geometría es la ÚNICA Y ABSOLUTA REFERENCIA DE VERDAD TRIDIMENSIONAL (Absolute Single Truth Reference). "
            "Es ESTRICTAMENTE INMUTABLE. NO rediseñes, NO alteres la forma ni agregues elementos estructurales inexistentes."
        )
        for idx, raw_b in enumerate(mueble_bytes_list, 1):
            opt_b = optimize_image_bytes(raw_b)
            if opt_b:
                contents.append(f"--- [FOTO {idx} DEL MUEBLE: ÁNGULO / DETALLE ESTRUCTURAL] ---")
                contents.append(types.Part.from_bytes(data=opt_b, mime_type="image/jpeg"))

    # 2. Wood Texture Swatch (Optional)
    if madera_bytes:
        opt_madera = optimize_image_bytes(madera_bytes)
        if opt_madera:
            contents.append(
                "=== MUESTRA DE REFERENCIA DE MADERA (SOLO ACABADO SUPERFICIAL) ===\n"
                "La siguiente imagen es EXCLUSIVAMENTE una muestra de material y textura de madera. "
                "NO copies la forma de este objeto. Extrae únicamente el tipo de madera, patrón de veta anatómica, "
                "porosidad, tonalidad cromática exacta y acabado (mate/satinado/barniz) para aplicarlo a las partes lígneas del mueble, "
                "SIN alterar bajo ninguna circunstancia la geometría del mueble original."
            )
            contents.append(types.Part.from_bytes(data=opt_madera, mime_type="image/jpeg"))

    # 3. Fabric Texture Swatch (Optional)
    if tela_bytes:
        opt_tela = optimize_image_bytes(tela_bytes)
        if opt_tela:
            contents.append(
                "=== MUESTRA DE REFERENCIA TEXTIL / TELA (SOLO TEXTURA Y COLOR) ===\n"
                "La siguiente imagen es EXCLUSIVAMENTE una muestra textil de tapicería. "
                "NO modifiques la forma de los cojines, pliegues ni la estructura del mueble. "
                "Extrae únicamente el tramado de tejido, densidad de hilo, textura micro-táctil (lino, bouclé, terciopelo, piel) "
                "y tonalidad cromática para la tapicería del mueble, reduciendo la escala macro (~97%-98%) y mapeándola conforme "
                "a las curvaturas 3D originales sin alterar la geometría."
            )
            contents.append(types.Part.from_bytes(data=opt_tela, mime_type="image/jpeg"))

    # 4. User Prompt and Technical Directives
    contents.append(user_prompt)
    return contents

# ===========================================================================
# Deterministic Prompts Engine & Multi-View Fallback Generator
# ===========================================================================
def build_deterministic_prompt(
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = "",
    camera_override: Optional[Dict[str, str]] = None
) -> str:
    btn = (boton_principal or "").strip().lower()
    is_entorno = (btn == "entorno") or bool((lugar_mueble or "").strip())

    mueble_nombre = (tipo_mueble or "").strip() or "Pieza de mobiliario de diseño de autor"
    medidas_desc = (medidas or "").strip() or "proporciones ergonómicas estándar a escala 1:1"

    # Resolve camera angle
    camera_spec = camera_override or resolve_camera_spec(sub_opcion or vista)
    if camera_spec:
        angulo_desc = f"{camera_spec['directive']}. {camera_spec['geometry']}"
        camera_neg = camera_spec['negative']
    else:
        raw_angle = (sub_opcion or vista or "").strip() or "Perspectiva 3/4 isométrica fotorrealista"
        angulo_desc = f"{raw_angle}. Distancia focal 85mm para perspectiva sin distorsión óptica, apertura f/5.6 con nitidez total en todo el volumen del mueble."
        camera_neg = "perspectiva distorsionada, aberración óptica"

    tela_desc = (tela or "").strip() or "tapicería textil premium con trama de lino/algodón de alta densidad"
    madera_desc = (madera or "").strip() or "madera natural con veta noble definida y acabado satinado"

    sections = []

    # 1. Base Setup & Background
    if is_entorno:
        lugar_desc = (lugar_mueble or "").strip() or "espacio arquitectónico contemporáneo de concepto abierto"
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append(f"Ambientación y Fondo: Entorno fotorrealista en '{lugar_desc}'. Iluminación natural arquitectónica difusa, sombras de contacto suaves y oclusión ambiental realista sobre el pavimento.")
        sections.append(f"Integración Espacial: {mueble_nombre} posicionado armónicamente dentro del espacio, respetando las dimensiones ({medidas_desc}) en escala coherente con la arquitectura circundante.")
    elif btn == "solo mueble":
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Fondo: Blanco sólido (#FFFFFF), sin elementos secundarios ni decoración de fondo")
        sections.append("Posición: Perfectamente centrado en encuadre, sombra de contacto neutra muy suave en base inferior")
    elif btn == "hd":
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Fondo: Blanco sólido (#FFFFFF) con iluminación de estudio fotográfico high-key")
        sections.append("Enfoque: Macro 8K UHD ultra-nítido centrado en la textura de materiales y detalles de ensamble")
    elif "clonar vistas (color y tela)" in btn:
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Fondo: Estudio neutral de catalogación e-commerce (#FFFFFF)")
        sections.append("Fidelidad de Clonación: Coincidencia 100% idéntica en tono y textura de madera, patrón textil y ángulo de toma")
    elif "360" in btn:
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Formato: Hoja técnica de consistencia rotacional multi-ángulo 360° (Turntable Studio Sheet)")
        sections.append("Iluminación: Estudio 360 simétrico sin variación cromática (5500K softbox)")
    else:
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Fondo: Blanco sólido (#FFFFFF)")
        sections.append("Posición: Perfectamente centrado")

    # 2. Structural & Design Description (Absolute Single Truth Reference)
    sections.append(f"Pieza de Mobiliario: {mueble_nombre}, dimensiones {medidas_desc}. Geometría equilibrada con detalles constructivos limpios, aristas de alta definición y fidelidad topológica 100% idéntica al mueble de referencia.")

    # 3. View & Camera Setup
    sections.append(f"Ángulo de Cámara y Vista: {angulo_desc}")

    # 4. Materials & Textures (4-Pillar Deconstruction & Conformal Mapping)
    mat_parts = []
    if btn in ("vistas + tela", "vistas + tela y madera") or tela:
        mat_parts.append(f"Tapicería: {tela_desc} (tejido adaptado conforme a las curvas 3D, reducción macro ~97%)")
    if btn in ("madera", "vistas + tela y madera") or madera:
        mat_parts.append(f"Acabado en Madera: {madera_desc} (veta anatómica alineada en dirección estructural)")
    if not mat_parts:
        mat_parts.append(f"Materiales: {madera_desc}, complementado con {tela_desc}")
    sections.append("Materiales y Texturas: " + " | ".join(mat_parts) + ".")

    # 5. Environment / Style modifier
    if ambiente.strip():
        sections.append(f"Estilo y Atmósfera: {ambiente.strip()}.")

    # 6. Quality & Render Directives
    if btn == "hd":
        sections.append("Calidad y Render: Enfoque macro fotorrealista 8K UHD, porosidad y micro-fibras visibles, reflejos especulares físicos precisos, cámara Hasselblad H6D-100c, render Octane/Unreal 5.4, sin aberraciones cromáticas.")
    else:
        sections.append("Calidad y Render: Fotografía comercial de producto fotorrealista 8K UHD, cámara Hasselblad H6D-100c con lente 85mm f/11, iluminación de estudio difusa balanceada 5500K, profundidad de campo calibrada, render sin artefactos.")

    # 7. Exclusions & Specialized Negative Prompt
    base_negative = "sin elementos superpuestos, sin personas, sin marcas de agua, sin texto, sin artefactos digitales, sin aspecto plástico CGI"
    if camera_neg:
        sections.append(f"Exclusiones y Negative Prompt: {base_negative}, {camera_neg}.")
    else:
        sections.append(f"Exclusiones: {base_negative}.")

    return "\n".join(sections)

def build_deterministic_multiview(
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = ""
) -> Dict[str, Any]:
    order = ["frontal_0", "isometrica_45", "lateral_90", "cenital_arriba", "arriba_3_4", "trasera_135"]
    vistas = []
    
    combined_lines = ["=== HOJA DE CONSISTENCIA ROTACIONAL MULTI-ÁNGULO 360° (TURNTABLE STUDIO SHEET) ===\n"]
    
    for key in order:
        spec = CAMERA_SPECS[key]
        p = build_deterministic_prompt(
            boton_principal=boton_principal,
            sub_opcion=spec["titulo"],
            medidas=medidas,
            tipo_mueble=tipo_mueble,
            lugar_mueble=lugar_mueble,
            vista="",
            tela=tela,
            madera=madera,
            ambiente=ambiente,
            camera_override=spec
        )
        vistas.append({
            "id": spec["id"],
            "titulo": spec["titulo"],
            "prompt": p
        })
        combined_lines.append(f"[{spec['titulo']}]\n{p}\n")
        
    master_prompt = "\n".join(combined_lines).strip()
    
    return {
        "success": True,
        "is_multiview": True,
        "prompt": master_prompt,
        "vistas": vistas
    }

# ===========================================================================
# Gemini Response Parser
# ===========================================================================
def parse_gemini_response(
    response_text: str,
    multiview: bool,
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = ""
) -> Dict[str, Any]:
    text = (response_text or "").strip()
    if not text:
        raise ValueError("Respuesta vacía de Gemini API")

    if multiview:
        clean_text = text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, dict) and "vistas" in parsed and isinstance(parsed["vistas"], list):
                vistas = parsed["vistas"]
                combined_lines = ["=== HOJA DE CONSISTENCIA ROTACIONAL MULTI-ÁNGULO 360° (TURNTABLE STUDIO SHEET) ===\n"]
                for v in vistas:
                    combined_lines.append(f"[{v.get('titulo', 'Vista')}]\n{v.get('prompt', '')}\n")
                master_prompt = "\n".join(combined_lines).strip()

                return {
                    "success": True,
                    "is_multiview": True,
                    "prompt": master_prompt,
                    "vistas": vistas
                }
        except Exception as json_err:
            logger.warning(f"No se pudo parsear JSON directo de Gemini ({json_err}). Aplicando síntesis determinista multi-vista.")

        return build_deterministic_multiview(
            boton_principal=boton_principal,
            sub_opcion=sub_opcion,
            medidas=medidas,
            tipo_mueble=tipo_mueble,
            lugar_mueble=lugar_mueble,
            vista=vista,
            tela=tela,
            madera=madera,
            ambiente=ambiente
        )
    else:
        clean_text = text
        if clean_text.startswith("```") and clean_text.endswith("```"):
            lines = clean_text.splitlines()
            if len(lines) >= 2:
                clean_text = "\n".join(lines[1:-1]).strip()

        title = "Prompt Principal"
        if sub_opcion:
            title = f"Vista: {sub_opcion}"
        elif vista:
            title = f"Vista: {vista}"
        elif boton_principal:
            title = f"Modo: {boton_principal.capitalize()}"

        return {
            "success": True,
            "is_multiview": False,
            "prompt": clean_text,
            "vistas": [
                {
                    "id": "principal",
                    "titulo": title,
                    "prompt": clean_text
                }
            ]
        }

# ===========================================================================
# Execution Orchestrator
# ===========================================================================
async def execute_generation(
    mueble_bytes_list: Optional[List[bytes]] = None,
    madera_bytes: Optional[bytes] = None,
    tela_bytes: Optional[bytes] = None,
    boton_principal: str = "",
    sub_opcion: str = "",
    medidas: str = "",
    tipo_mueble: str = "",
    lugar_mueble: str = "",
    vista: str = "",
    tela: str = "",
    madera: str = "",
    ambiente: str = "",
    image_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    # Normalize furniture bytes
    files_list: List[bytes] = list(mueble_bytes_list) if mueble_bytes_list else []
    if image_bytes and len(image_bytes) > 0:
        files_list.append(image_bytes)

    multiview = is_multiview_request(boton_principal, sub_opcion)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY no encontrada. Generando síntesis determinista de alta calidad.")
        if multiview:
            return build_deterministic_multiview(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
        else:
            single_prompt = build_deterministic_prompt(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
            title = "Prompt Principal"
            if sub_opcion:
                title = f"Vista: {sub_opcion}"
            elif boton_principal:
                title = f"Modo: {boton_principal.capitalize()}"

            return {
                "success": True,
                "is_multiview": False,
                "prompt": single_prompt,
                "vistas": [{"id": "principal", "titulo": title, "prompt": single_prompt}]
            }

    try:
        user_prompt = build_user_prompt(
            boton_principal=boton_principal,
            sub_opcion=sub_opcion,
            medidas=medidas,
            tipo_mueble=tipo_mueble,
            lugar_mueble=lugar_mueble,
            vista=vista,
            tela=tela,
            madera=madera,
            ambiente=ambiente
        )
        sys_instructions = build_system_instructions(
            boton_principal=boton_principal,
            sub_opcion=sub_opcion,
            medidas=medidas,
            tipo_mueble=tipo_mueble,
            lugar_mueble=lugar_mueble,
            vista=vista,
            tela=tela,
            madera=madera,
            ambiente=ambiente,
            multiview=multiview
        )
        contents = build_gemini_contents(
            mueble_bytes_list=files_list,
            madera_bytes=madera_bytes,
            tela_bytes=tela_bytes,
            user_prompt=user_prompt
        )

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=sys_instructions,
                temperature=0.2
            )
        )
        if response and response.text:
            return parse_gemini_response(
                response_text=response.text,
                multiview=multiview,
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
        else:
            raise ValueError("Respuesta vacía recibida del modelo Gemini")
    except Exception as gemini_err:
        logger.warning(f"Llamada a Gemini API no disponible o fallida ({gemini_err}). Empleando síntesis determinista.")
        if multiview:
            return build_deterministic_multiview(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
        else:
            single_prompt = build_deterministic_prompt(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
            title = "Prompt Principal"
            if sub_opcion:
                title = f"Vista: {sub_opcion}"
            elif boton_principal:
                title = f"Modo: {boton_principal.capitalize()}"

            return {
                "success": True,
                "is_multiview": False,
                "prompt": single_prompt,
                "vistas": [{"id": "principal", "titulo": title, "prompt": single_prompt}]
            }

async def handle_json_generate(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"Error decodificando payload JSON: {e}")
        body = {}

    boton_principal = str(body.get("boton_principal") or "")
    sub_opcion = str(body.get("sub_opcion") or "")
    medidas = str(body.get("medidas") or "")
    tipo_mueble = str(body.get("tipo_mueble") or "")
    lugar_mueble = str(body.get("lugar_mueble") or "")
    vista = str(body.get("vista") or "")
    tela = str(body.get("tela") or "")
    madera = str(body.get("madera") or "")
    ambiente = str(body.get("ambiente") or "")

    mueble_bytes_list: List[bytes] = []
    muebles_val = body.get("mueble_images")
    if isinstance(muebles_val, list):
        for item in muebles_val:
            b = decode_base64_image(item)
            if b:
                mueble_bytes_list.append(b)
    elif isinstance(muebles_val, str):
        b = decode_base64_image(muebles_val)
        if b:
            mueble_bytes_list.append(b)

    # Legacy image fallback
    legacy_image_val = body.get("image")
    if not mueble_bytes_list and legacy_image_val:
        b = decode_base64_image(legacy_image_val)
        if b:
            mueble_bytes_list.append(b)

    madera_bytes = decode_base64_image(body.get("madera_image"))
    tela_bytes = decode_base64_image(body.get("tela_image"))

    result = await execute_generation(
        mueble_bytes_list=mueble_bytes_list,
        madera_bytes=madera_bytes,
        tela_bytes=tela_bytes,
        boton_principal=boton_principal,
        sub_opcion=sub_opcion,
        medidas=medidas,
        tipo_mueble=tipo_mueble,
        lugar_mueble=lugar_mueble,
        vista=vista,
        tela=tela,
        madera=madera,
        ambiente=ambiente
    )
    return JSONResponse(status_code=200, content=result)

@app.middleware("http")
async def json_payload_middleware(request: Request, call_next):
    if request.url.path == "/api/generate" and request.method == "POST":
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return await handle_json_generate(request)
    return await call_next(request)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>V4 Ready</h1>")

@app.get("/health")
async def healthcheck():
    return {"status": "ok"}

@app.post("/api/generate")
async def generate_prompt(
    request: Request,
    mueble_images: List[UploadFile] = File(default=[]),
    image: Optional[UploadFile] = File(default=None),
    madera_image: Optional[UploadFile] = File(default=None),
    tela_image: Optional[UploadFile] = File(default=None),
    vista: str = Form(""),
    boton_principal: str = Form(""),
    sub_opcion: str = Form(""),
    medidas: str = Form(""),
    tipo_mueble: str = Form(""),
    lugar_mueble: str = Form(""),
    tela: str = Form(""),
    madera: str = Form(""),
    ambiente: str = Form("")
):
    try:
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return await handle_json_generate(request)

        # 1. Process furniture images (mueble_images + legacy image)
        raw_mueble_files = list(mueble_images) if mueble_images else []
        if image is not None:
            raw_mueble_files.append(image)

        mueble_bytes_list: List[bytes] = []
        for f in raw_mueble_files:
            if f and getattr(f, "filename", ""):
                try:
                    content = await f.read()
                    if content and len(content) > 0:
                        mueble_bytes_list.append(content)
                except Exception as read_err:
                    logger.warning(f"Error leyendo archivo de mueble: {read_err}")

        # 2. Process wood reference image
        madera_bytes: Optional[bytes] = None
        if madera_image and getattr(madera_image, "filename", ""):
            try:
                content = await madera_image.read()
                if content and len(content) > 0:
                    madera_bytes = content
            except Exception as read_err:
                logger.warning(f"Error leyendo imagen de madera: {read_err}")

        # 3. Process fabric reference image
        tela_bytes: Optional[bytes] = None
        if tela_image and getattr(tela_image, "filename", ""):
            try:
                content = await tela_image.read()
                if content and len(content) > 0:
                    tela_bytes = content
            except Exception as read_err:
                logger.warning(f"Error leyendo imagen de tela: {read_err}")

        result = await execute_generation(
            mueble_bytes_list=mueble_bytes_list,
            madera_bytes=madera_bytes,
            tela_bytes=tela_bytes,
            boton_principal=boton_principal,
            sub_opcion=sub_opcion,
            medidas=medidas,
            tipo_mueble=tipo_mueble,
            lugar_mueble=lugar_mueble,
            vista=vista,
            tela=tela,
            madera=madera,
            ambiente=ambiente
        )
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        logger.error(f"Error en generate_prompt: {e}", exc_info=True)
        multiview = is_multiview_request(boton_principal, sub_opcion)
        if multiview:
            fallback = build_deterministic_multiview(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
            return JSONResponse(status_code=200, content=fallback)
        else:
            fallback = build_deterministic_prompt(
                boton_principal=boton_principal,
                sub_opcion=sub_opcion,
                medidas=medidas,
                tipo_mueble=tipo_mueble,
                lugar_mueble=lugar_mueble,
                vista=vista,
                tela=tela,
                madera=madera,
                ambiente=ambiente
            )
            title = "Prompt Principal"
            if sub_opcion:
                title = f"Vista: {sub_opcion}"
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "is_multiview": False,
                    "prompt": fallback,
                    "vistas": [{"id": "principal", "titulo": title, "prompt": fallback}]
                }
            )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
