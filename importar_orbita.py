"""Importa una orbita 360 (visor *_ORBITA-360_visor.html: fotogramas alrededor de la casa) a la app.

Uso:
    python importar_orbita.py RUTA_AL_VISOR.html [--titulo "..."] [--id ID] [--concurso "..."]

Que hace:
  - Saca los fotogramas embebidos a web/recorridos/<id>/f000.jpg, f001.jpg... y las vistas fijas a fija-1.jpg...
  - Guarda en orbita.json lo que el visor necesita: rumbos (que se ve desde cada lado), vistas fijas, zoom maximo, notas.
  - Crea la portada de la galeria con el primer fotograma (el frente) y agrega la ficha al catalogo (tipo "orbita").
Despues: python publicar.py --subir
"""
import argparse, base64, datetime, html, io, json, os, re, sys
from PIL import Image

from importar_visor import RECORRIDOS, CATALOGO, WEB, artefacto


def lista_js(nombre, s):
    """El literal JS `var NOMBRE = [...];` como JSON (los visores lo escriben con comillas dobles)."""
    m = re.search(r"var\s+" + nombre + r"\s*=\s*(\[.*?\]);", s, re.S)
    return json.loads(m.group(1)) if m else None


def numero_js(nombre, s, defecto):
    m = re.search(r"var\s+" + nombre + r"\s*=\s*([-\d.]+)", s)
    return float(m.group(1)) if m else defecto


def importa(ruta, titulo=None, ident=None, concurso=None):
    s = open(ruta, encoding="utf-8").read()
    fotogramas = lista_js("FRAMES", s)
    if not fotogramas:
        sys.exit("No encuentro los fotogramas (var FRAMES = [...]) en " + ruta)
    fijas = lista_js("FIJAS", s) or []
    rumbos = lista_js("RUMBOS", s) or []

    if not ident:
        base = os.path.splitext(os.path.basename(ruta))[0]
        ident = re.sub(r"_visor.*$", "", base)
    ident = re.sub(r"[^A-Za-z0-9._~-]", "-", ident)        # el id viaja en el #hash de la URL
    carpeta = os.path.join(RECORRIDOS, ident)
    os.makedirs(carpeta, exist_ok=True)
    for n in os.listdir(carpeta):                           # una orbita nueva reemplaza todos los fotogramas
        if re.match(r"(f\d{3}|fija-\d+)\.jpg$", n):
            os.remove(os.path.join(carpeta, n))

    for k, b64 in enumerate(fotogramas):
        with open(os.path.join(carpeta, f"f{k:03d}.jpg"), "wb") as f:
            f.write(base64.b64decode(b64))
    nombres_fijas = []
    for k, (txt, b64) in enumerate(fijas, 1):
        with open(os.path.join(carpeta, f"fija-{k}.jpg"), "wb") as f:
            f.write(base64.b64decode(b64))
        nombres_fijas.append({"titulo": txt, "imagen": f"recorridos/{ident}/fija-{k}.jpg"})

    im = Image.open(os.path.join(carpeta, "f000.jpg")).convert("RGB")
    W, H = im.size
    cw, ch = (round(H * 12 / 7), H) if W / H > 12 / 7 else (W, round(W * 7 / 12))
    im.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((1200, 700), Image.LANCZOS) \
      .save(os.path.join(carpeta, "portada.jpg"), quality=84, optimize=True, progressive=True)

    h1 = re.search(r'<div class="panel"><h1>(.*?)</h1>', s, re.S)
    p1 = re.search(r'<div class="panel"><h1>.*?</h1><p>(.*?)</p>', s, re.S)
    h1 = html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip() if h1 else ident
    proyecto = (re.search(r"PRY-\d+", h1 + " " + os.path.basename(ruta)) or [""])[0]
    if not titulo:
        titulo = re.sub(r"^PRY-\d+\s*", "", h1)
    datos = {
        "fotogramas": len(fotogramas), "ancho": W, "alto": H,
        "zmax": numero_js("ZMAX", s, 2.5),
        "rumbos": rumbos,                                   # [azimut matematico, nombre, que se ve]; giro 0 = camara al sur (azimut -90)
        "fijas": nombres_fijas,
        "notas": html.unescape(re.sub(r"<[^>]+>", "", p1.group(1))).strip() if p1 else "",
        "encabezado": h1,
    }
    with open(os.path.join(carpeta, "orbita.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))

    cat = json.load(open(CATALOGO, encoding="utf-8")) if os.path.exists(CATALOGO) else []
    previo = next((c for c in cat if c["id"] == ident), {})
    ficha = {
        "id": ident, "tipo": "orbita", "titulo": titulo, "proyecto": proyecto,
        "concurso": concurso if concurso is not None else previo.get("concurso", ""),
        "fecha": datetime.date.fromtimestamp(os.path.getmtime(ruta)).isoformat(),
        "fuente": os.path.basename(ruta),
        "fotogramas": len(fotogramas), "fijas": len(nombres_fijas),
        "portada": f"recorridos/{ident}/portada.jpg",
    }
    cat = [c for c in cat if c["id"] != ident] + [ficha]
    cat.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    with open(CATALOGO, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)

    peso = sum(os.path.getsize(os.path.join(carpeta, n)) for n in os.listdir(carpeta)) / 1e6
    print(f"OK  {ident}: {len(fotogramas)} fotogramas de {W} x {H}, {len(nombres_fijas)} vista(s) fija(s), {peso:.1f} MB en web/recorridos/{ident}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("visor", help="el visor de la orbita (html)")
    ap.add_argument("--titulo", default=None, help="titulo en la galeria (por defecto, el del visor)")
    ap.add_argument("--id", default=None, help="id (por defecto, el nombre del archivo sin _visor...)")
    ap.add_argument("--concurso", default=None, help="nombre del concurso")
    a = ap.parse_args()
    importa(a.visor, a.titulo, a.id, a.concurso)
    if os.path.exists(os.path.join(WEB, "index.html")):
        artefacto()
