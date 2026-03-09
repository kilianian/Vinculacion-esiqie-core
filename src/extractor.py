"""
Fase 1: Extractor de Catálogos.
Utiliza pdfplumber para extraer información estructurada del PDF de la ESIQIE.
"""

"""
Fase 1: Extractor de Catálogos.
Utiliza pdfplumber para extraer información estructurada del PDF de la ESIQIE.
"""
import pdfplumber
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = BASE_DIR / "data" / "raw" / "EMPRESAS-para-prácticas.pdf · versión 1.pdf"

def probar_extraccion_basica() -> None:
    """
    Abre el PDF y extrae el texto de la primera página para analizar su estructura.
    """
    print(f"Buscando el catálogo en: {PDF_PATH}")
    
    try:
        # Abrimos el PDF
        with pdfplumber.open(PDF_PATH) as pdf:
            # Seleccionamos solo la primera página (índice 0) para hacer pruebas rápidas
            primera_pagina = pdf.pages[1]
            
            # Extraemos el texto respetando la disposición visual (layout)
            texto = primera_pagina.extract_text(layout=True)
            
            print("\n--- INICIO DEL TEXTO EXTRAÍDO ---")
            print(texto)
            print("--- FIN DEL TEXTO EXTRAÍDO ---\n")
            
    except FileNotFoundError:
        print("❌ Error: No se encontró el archivo PDF. Verifica que esté en data/raw/ y tenga el nombre correcto.")

if __name__ == "__main__":
    probar_extraccion_basica()