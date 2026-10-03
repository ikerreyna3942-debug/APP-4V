import os
import io
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from PIL import Image

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

def build_system_instructions(
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
    btn = (boton_principal or "").strip().lower()
    is_entorno = (btn == "entorno") or bool((lugar_mueble or "").strip())

    intro = (
        "Actúa como un experto en diseño industrial, catalogación e-commerce y director de fotografía de producto. "
        "Tu tarea es analizar detalladamente la imagen de referencia del mueble y redactar un prompt visual ultra-técnico "
        "para recrear exactamente la misma pieza.\n\n"
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
            "sin accesorios distractores ni entorno decorativo, con iluminación de catálogo limpio y sombra de contacto neutra.\n"
        )
    else:
        rule_1 = (
            "1. Configuraciones Base: Siempre debes iniciar el prompt con: 'Tamaño de lienzo: 2080x2080 px', "
            "'Fondo: Blanco sólido (#FFFFFF)' y 'Posición: Perfectamente centrado'.\n"
        )

    rule_2 = "2. Fidelidad Estructural: Describe la geometría, proporciones y detalles de ensamble del mueble de la foto con precisión técnica.\n"

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
            "reflejos especulares exactos y uniones estructurales de alta precisión sin artefactos de compresión."
        )
    elif "clonar vistas (color y tela)" in btn:
        specialized_rules.append(
            "Directiva Especial (Clonar Vistas - Color y Tela): Obligación estricta de reproducir con fidelidad 100% idéntica "
            "el color exacto, veta y acabado de la madera, la textura, tono y tramado de la tela, y el ángulo de cámara especificado. "
            "No alterar ni sustituir los materiales ni la geometría de la pieza original bajo ninguna circunstancia."
        )
    elif "clonar múltiples vistas 360" in btn or "360" in btn:
        specialized_rules.append(
            "Directiva Especial (Clonar Múltiples Vistas 360): Estructurar el prompt técnico para una hoja de consistencia rotacional "
            "multi-ángulo 360 grados (turntable studio sheet). Especificar iluminación de estudio constante, mismo nivel de horizonte, "
            "y rigurosa coherencia geométrica en todas las fases de rotación."
        )
    elif btn == "vistas + tela y madera":
        specialized_rules.append(
            "Directiva Especial (Vistas + Tela y Madera): Integrar con máxima prioridad la perspectiva de cámara seleccionada junto con la especificación "
            "detallada del acabado de madera indicado y el patrón/textura textil solicitado."
        )
    elif btn == "vistas + tela":
        specialized_rules.append(
            "Directiva Especial (Vistas + Tela): Enfocar la atención en el ángulo de cámara exacto y en la sustitución/descripción fotorrealista de la tapicería textil."
        )
    elif btn == "madera":
        specialized_rules.append(
            "Directiva Especial (Madera): Describir en detalle el tipo de madera, patrón de veta, corte, tonalidad, barniz y tratamiento superficial."
        )

    spec_text = ""
    if specialized_rules:
        spec_text = "\n" + "\n".join(specialized_rules) + "\n"

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

def build_deterministic_prompt(
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
    btn = (boton_principal or "").strip().lower()
    is_entorno = (btn == "entorno") or bool((lugar_mueble or "").strip())

    mueble_nombre = (tipo_mueble or "").strip() or "Pieza de mobiliario de diseño de autor"
    medidas_desc = (medidas or "").strip() or "proporciones ergonómicas estándar a escala 1:1"
    angulo_desc = (sub_opcion or vista or "").strip() or "Perspectiva 3/4 isométrica fotorrealista"
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
        sections.append("Fondo: Estudio neutral de catalogación e-commerce")
        sections.append("Fidelidad de Clonación: Coincidencia 100% idéntica en tono y textura de madera, patrón textil y ángulo de toma")
    elif "360" in btn:
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Formato: Hoja técnica de consistencia rotacional multi-ángulo 360°")
        sections.append("Iluminación: Estudio 360 simétrico sin variación cromática")
    else:
        sections.append("Tamaño de lienzo: 2080x2080 px")
        sections.append("Fondo: Blanco sólido (#FFFFFF)")
        sections.append("Posición: Perfectamente centrado")

    # 2. Structural & Design Description
    sections.append(f"Pieza de Mobiliario: {mueble_nombre}, dimensiones {medidas_desc}. Geometría equilibrada con detalles constructivos limpios y aristas de alta definición.")

    # 3. View & Camera Setup
    sections.append(f"Ángulo de Cámara y Vista: {angulo_desc}. Distancia focal 85mm para perspectiva sin distorsión óptica, apertura f/5.6 con nitidez total en todo el volumen del mueble.")

    # 4. Materials & Textures
    mat_parts = []
    if btn in ("vistas + tela", "vistas + tela y madera") or tela:
        mat_parts.append(f"Tapicería: {tela_desc}")
    if btn in ("madera", "vistas + tela y madera") or madera:
        mat_parts.append(f"Acabado en Madera: {madera_desc}")
    if not mat_parts:
        mat_parts.append(f"Materiales: {madera_desc}, complementado con {tela_desc}")
    sections.append("Materiales y Texturas: " + " | ".join(mat_parts) + ".")

    # 5. Environment / Style modifier
    if ambiente.strip():
        sections.append(f"Estilo y Atmósfera: {ambiente.strip()}.")

    # 6. Quality & Render Directives
    if btn == "hd":
        sections.append("Calidad y Render: Enfoque macro fotorrealista 8K, porosidad y micro-fibras visibles, reflejos especulares físicos precisos, render Octane/Unreal 5.4, sin aberraciones cromáticas.")
    else:
        sections.append("Calidad y Render: Fotografía comercial de producto fotorrealista 8K UHD, iluminación de estudio difusa balanceada, profundidad de campo calibrada, render sin artefactos.")

    sections.append("Exclusiones: Sin elementos superpuestos, sin personas, sin marcas de agua, sin texto, sin artefactos digitales, sin distorsión de perspectiva ni bordes dentados.")

    return "\n".join(sections)

async def execute_generation(
    image_bytes: Optional[bytes],
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
    opt_bytes = None
    if image_bytes:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            max_size = 1600
            if max(pil_image.size) > max_size:
                pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            opt_bytes_io = io.BytesIO()
            pil_image.save(opt_bytes_io, format="JPEG", quality=85)
            opt_bytes = opt_bytes_io.getvalue()
        except Exception as img_err:
            logger.warning(f"Error procesando imagen: {img_err}")
            opt_bytes = None

    sys_instructions = build_system_instructions(
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

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY no encontrada. Generando síntesis determinista de alta calidad.")
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
        return {"success": True, "prompt": fallback}

    try:
        client = genai.Client(api_key=api_key)
        contents = []
        if opt_bytes:
            contents.append(types.Part.from_bytes(data=opt_bytes, mime_type='image/jpeg'))
        contents.append(user_prompt)

        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=sys_instructions,
                temperature=0.2
            )
        )
        if response and response.text:
            return {"success": True, "prompt": response.text}
        else:
            raise ValueError("Respuesta vacía recibida del modelo Gemini")
    except Exception as gemini_err:
        logger.warning(f"Llamada a Gemini API no disponible o fallida ({gemini_err}). Empleando síntesis determinista.")
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
        return {"success": True, "prompt": fallback}

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

    image_bytes = None
    image_val = body.get("image")
    if image_val and isinstance(image_val, str) and image_val.startswith("data:image"):
        try:
            import base64
            _, b64data = image_val.split(",", 1)
            image_bytes = base64.b64decode(b64data)
        except Exception as b64_err:
            logger.warning(f"Error decodificando imagen base64 desde JSON: {b64_err}")

    result = await execute_generation(
        image_bytes=image_bytes,
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
    image: Optional[UploadFile] = File(None),
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

        image_bytes = None
        if image is not None:
            try:
                raw_bytes = await image.read()
                if raw_bytes and len(raw_bytes) > 0:
                    image_bytes = raw_bytes
            except Exception as read_err:
                logger.warning(f"Error leyendo archivo de imagen: {read_err}")

        result = await execute_generation(
            image_bytes=image_bytes,
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
        return JSONResponse(status_code=200, content={"success": True, "prompt": fallback})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
