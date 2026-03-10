"""
fase 1 (v2 - calibrado): extractor con layout de dos columnas.
valores de split calibrados con diagnostico.py sobre el PDF real:
  - GIRO en x0=323.7 sobre ancho=612.0  → SPLIT_X = 0.529
  - UBICACION en top=511.3 sobre alto=792.0 → SPLIT_Y = 0.645

estructura del PDF por pagina:
  col izquierda (x0 < 323.7): nombre empresa + logo
  col derecha   (x0 > 323.7): GIRO, ACTIVIDADES
  zona inferior (top > 511.3): UBICACION, TEL, WEB (ancho completo)
"""
import pdfplumber
import re
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = BASE_DIR / "data" / "raw" / "EMPRESAS-para-practicas.pdf"

# valores calibrados con diagnostico.py — ajustar si cambia el PDF
SPLIT_X = 0.529   # x0=323.7 / ancho=612.0
SPLIT_Y = 0.645   # top=511.3 / alto=792.0


def extraer_columnas(pagina) -> tuple[str, str, str]:
    """
    divide la pagina en 3 zonas con bounding boxes y extrae texto de cada una.
    retorna (col_izq, col_der, inferior)
    """
    w = float(pagina.width)
    h = float(pagina.height)

    split_x = w * SPLIT_X
    split_y = h * SPLIT_Y

    col_izq  = pagina.within_bbox((0,       0,       split_x, split_y)).extract_text() or ""
    col_der  = pagina.within_bbox((split_x, 0,       w,       split_y)).extract_text() or ""
    inferior = pagina.within_bbox((0,       split_y, w,       h      )).extract_text() or ""

    return col_izq, col_der, inferior


def limpiar_nombre_empresa(texto: str) -> str:
    """
    extrae el nombre de empresa del texto de la columna izquierda.
    descarta lineas que son ruido del logo o texto decorativo.
    """
    if not texto:
        return "NULL"

    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    lineas_utiles = []

    for linea in lineas:
        if re.match(r'^[\d\s.\-]+$', linea):   # solo numeros/puntos
            continue
        if len(linea) <= 2:                      # muy corta
            continue
        if re.match(r'^(http|www\.)', linea, re.IGNORECASE):  # url
            continue
        lineas_utiles.append(linea)

    return " ".join(lineas_utiles) if lineas_utiles else "NULL"


def extraer_giro_actividades(texto: str) -> tuple[str, str]:
    """parsea col derecha: extrae giro y actividades."""
    giro = "NULL"
    actividades = "NULL"

    if not texto:
        return giro, actividades

    match_giro = re.search(
        r'GIRO\s*(.*?)\s*(?:ACTIVIDADES|$)',
        texto, re.DOTALL | re.IGNORECASE
    )
    if match_giro:
        val = match_giro.group(1).replace('\n', ' ').strip()
        if val:
            giro = val

    match_act = re.search(
        r'ACTIVIDADES\.?\s*(.*)',
        texto, re.DOTALL | re.IGNORECASE
    )
    if match_act:
        val = match_act.group(1).replace('\n', ' ').strip()
        if val:
            actividades = val

    return giro, actividades


def extraer_ubicacion_tel_web(texto: str) -> tuple[str, str, str]:
    """
    parsea la zona inferior: extrae ubicacion, telefono y webs.
    maneja variantes del PDF: TEL., TELÉFONO, Tel. Conmutador, Servicios:, etc.
    no filtra emails genericos (hotmail/gmail incluidos) — se clasifica despues.
    """
    ubicacion = "NULL"
    telefono  = "NULL"
    webs      = "NULL"

    if not texto:
        return ubicacion, telefono, webs

    # ubicacion: desde UBICACION hasta PAGINA WEB o TEL
    match_ubi = re.search(
        r'UBICACI[O\xd3]N\s*(.*?)(?=P[A\xc1]GINA\s*WEB|TEL[E\xc9]?FONO?\.?|TEL\.|$)',
        texto, re.DOTALL | re.IGNORECASE
    )
    if match_ubi:
        val = match_ubi.group(1).replace('\n', ' ').strip()
        if val:
            ubicacion = val

    # telefono: numero principal (linea de TEL. Conmutador)
    # captura digitos, parentesis, guiones. Se detiene en salto de linea
    match_tel = re.search(
        r'TEL[E\xc9]?(?:FONO)?\.?\s*(?:Conmutador:?\s*)?([\d\s\(\)\-]+)',
        texto, re.IGNORECASE
    )
    if match_tel:
        val = re.sub(r'\s{2,}', ' ', match_tel.group(1)).strip()
        if val:
            telefono = val

    # webs: todas las urls — no filtrar por dominio, gmail/hotmail son validos en MX
    urls = re.findall(r'(?:https?://|www\.)[^\s,\)]+', texto, re.IGNORECASE)
    if urls:
        webs = " | ".join(u.rstrip('.') for u in urls)

    return ubicacion, telefono, webs


def evaluar_estatus(datos: dict) -> str:
    campos = ["empresa", "giro_y_subempresas", "actividades", "ubicacion", "telefono", "webs"]
    n = sum(1 for c in campos if datos.get(c) not in ("NULL", "", None))
    if n == len(campos): return "completo"
    if n >= 4:           return "parcial"
    if n >= 2:           return "pobre"
    return "incompleto"


def extraer_datos_pagina(pagina) -> dict:
    datos = {
        "empresa": "NULL",
        "giro_y_subempresas": "NULL",
        "actividades": "NULL",
        "ubicacion": "NULL",
        "telefono": "NULL",
        "webs": "NULL",
        "estatus_extraccion": "incompleto",
    }

    col_izq, col_der, inferior = extraer_columnas(pagina)

    datos["empresa"] = limpiar_nombre_empresa(col_izq)
    datos["giro_y_subempresas"], datos["actividades"] = extraer_giro_actividades(col_der)
    datos["ubicacion"], datos["telefono"], datos["webs"] = extraer_ubicacion_tel_web(inferior)
    datos["estatus_extraccion"] = evaluar_estatus(datos)

    return datos


def procesar_catalogo() -> None:
    print(f"procesando catalogo desde: {PDF_PATH}")

    registros = []

    try:
        with pdfplumber.open(PDF_PATH) as pdf:
            total = len(pdf.pages)
            for i in range(1, total):   # skip portada (indice 0)
                pagina = pdf.pages[i]
                print(f"  pagina {i}/{total-1}...", end="\r")
                datos = extraer_datos_pagina(pagina)
                registros.append(datos)

        if registros:
            ruta_csv = BASE_DIR / "data" / "processed" / "extraccion_cruda.csv"
            ruta_csv.parent.mkdir(parents=True, exist_ok=True)

            df = pd.DataFrame(registros)
            df.to_csv(ruta_csv, index=False, encoding="utf-8")

            completos = len(df[df["estatus_extraccion"] == "completo"])
            parciales  = len(df[df["estatus_extraccion"] == "parcial"])
            pobres     = len(df[df["estatus_extraccion"] == "pobre"])

            print(f"\nextraccion terminada -> {ruta_csv}")
            print(f"  total    : {len(registros)}")
            print(f"  completo : {completos}")
            print(f"  parcial  : {parciales}")
            print(f"  pobre    : {pobres}")

    except FileNotFoundError:
        print(f"error: no encontre el pdf en {PDF_PATH}")
        print("verifica que PDF_PATH apunte al archivo correcto.")


if __name__ == "__main__":
    procesar_catalogo()