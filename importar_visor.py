"""Importa un visor 360 autocontenido (r360_*_visor*.html) a la app web.

Uso:
    python importar_visor.py RUTA_AL_VISOR.html [--concurso "Nombre del concurso"] [--id ID]
    python importar_visor.py --artefacto        (solo regenera publicar/artefacto.html)

Que hace:
  - Saca los panoramas y miniaturas embebidos (base64) a web/recorridos/<id>/ como .jpg.
  - Guarda los datos del recorrido (puntos, saltos, plano SVG, notas, estados) en recorridos/<id>/recorrido.json.
  - Crea una portada 1200x700 para la galeria desde el punto de inicio.
  - Agrega o actualiza el recorrido en web/recorridos/catalogo.json (lo mas reciente primero).
  - Regenera publicar/artefacto.html (la misma app sin <html>/<head>, para publicar como Artifact).
"""
import argparse, base64, datetime, html, io, json, os, re, sys
from PIL import Image

RAIZ = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(RAIZ, "web")
RECORRIDOS = os.path.join(WEB, "recorridos")
CATALOGO = os.path.join(RECORRIDOS, "catalogo.json")


def texto(s):
    """Quita etiquetas y desescapa entidades."""
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def busca(patron, s, grupo=1, flags=re.S):
    m = re.search(patron, s, flags)
    return m.group(grupo) if m else None


def importa(ruta, concurso=None, ident=None):
    s = open(ruta, encoding="utf-8").read()
    datos = json.loads(busca(r'<script type="application/json" id="datos">(.*?)</script>', s))

    if not ident:
        base = os.path.splitext(os.path.basename(ruta))[0]
        ident = re.sub(r"_visor.*$", "", base)
    ident = re.sub(r"[^A-Za-z0-9._~-]", "-", ident)        # el id viaja en el #hash de la URL
    carpeta = os.path.join(RECORRIDOS, ident)
    os.makedirs(carpeta, exist_ok=True)

    # ---- imagenes embebidas
    imagenes = {}
    for m in re.finditer(r'id="(img|th)-(\d+)-(\d+)" data-src="data:image/(jpeg|png|webp);base64,([^"]+)"', s):
        tipo, est, pto, ext, b64 = m.groups()
        ext = "jpg" if ext == "jpeg" else ext
        nombre = f"{'pano' if tipo == 'img' else 'mini'}-{est}-{pto}.{ext}"
        with open(os.path.join(carpeta, nombre), "wb") as f:
            f.write(base64.b64decode(b64))
        imagenes.setdefault(est, {}).setdefault(pto, {})["pano" if tipo == "img" else "mini"] = nombre

    # ---- piezas del visor que no estan en el JSON
    ceja = texto(busca(r'<div class="ceja">(.*?)</div>', s) or "")
    estados = [texto(b) for b in re.findall(r'<button[^>]*data-m="\d+"[^>]*>(.*?)</button>', busca(r'<div id="momento".*?</div>', s, 0) or "")]
    plano = busca(r'<aside id="plano"[^>]*>(<svg.*?</svg>)', s)
    notas = re.findall(r"<li>(.*?)</li>", busca(r'<section id="notas".*?</section>', s, 0) or "", re.S)

    # ---- portada: 120 grados alrededor de la mirada inicial (yaw 0 = centro del panorama)
    inicio = datos.get("inicio")
    i0 = next((i for i, p in enumerate(datos["puntos"]) if p["id"] == inicio), 0)
    m0 = str(datos.get("momento_inicial", 0))
    pano0 = imagenes.get(m0, {}).get(str(i0), {}).get("pano") or imagenes["0"]["0"]["pano"]
    im = Image.open(os.path.join(carpeta, pano0)).convert("RGB")
    W, H = im.size
    cw = W // 3; ch = round(cw * 7 / 12)
    caja = (W // 2 - cw // 2, H // 2 - ch // 2, W // 2 + cw // 2, H // 2 + ch // 2)
    im.crop(caja).resize((1200, 700), Image.LANCZOS).save(os.path.join(carpeta, "portada.jpg"), quality=84, optimize=True, progressive=True)

    proyecto = busca(r"(PRY-\d+)", ceja or os.path.basename(ruta), flags=0) or ""
    fecha = datetime.date.fromtimestamp(os.path.getmtime(ruta)).isoformat()

    recorrido = {
        "id": ident,
        "titulo": datos.get("titulo", ident),
        "proyecto": proyecto,
        "concurso": concurso or "",
        "ceja": ceja,
        "fecha": fecha,
        "fuente": os.path.basename(ruta),
        "estados_nombres": estados or datos.get("estados", []),
        "imagenes": imagenes,
        "plano_svg": plano or "",
        "notas": notas,
        "datos": datos,
    }
    with open(os.path.join(carpeta, "recorrido.json"), "w", encoding="utf-8") as f:
        json.dump(recorrido, f, ensure_ascii=False, separators=(",", ":"))

    # ---- catalogo
    cat = []
    if os.path.exists(CATALOGO):
        cat = json.load(open(CATALOGO, encoding="utf-8"))
    previo = next((c for c in cat if c["id"] == ident), {})
    ficha = {
        "id": ident,
        "titulo": recorrido["titulo"],
        "proyecto": proyecto,
        "concurso": concurso if concurso is not None else previo.get("concurso", ""),
        "ceja": ceja,
        "fecha": fecha,
        "puntos": len(datos["puntos"]),
        "estados": recorrido["estados_nombres"],
        "portada": f"recorridos/{ident}/portada.jpg",
    }
    cat = [c for c in cat if c["id"] != ident] + [ficha]
    cat.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    with open(CATALOGO, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)

    peso = sum(os.path.getsize(os.path.join(carpeta, n)) for n in os.listdir(carpeta)) / 1e6
    print(f"OK  {ident}: {len(datos['puntos'])} puntos, {len(recorrido['estados_nombres'])} estado(s), {peso:.1f} MB en web/recorridos/{ident}/")


def artefacto():
    """La app sin doctype/html/head/body, para publicarla como Artifact (que pone su propio esqueleto)."""
    s = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
    titulo = busca(r"<title>.*?</title>", s, 0)
    estilos = busca(r"(<link rel=\"preconnect\".*?)</head>", s)
    estilos = re.sub(r"<meta[^>]*>\s*", "", estilos)
    estilos = re.sub(r"<link rel=\"(manifest|apple-touch-icon|icon)\"[^>]*>\s*", "", estilos)
    cuerpo = busca(r"<body>(.*)</body>", s)
    os.makedirs(os.path.join(RAIZ, "publicar"), exist_ok=True)
    with open(os.path.join(RAIZ, "publicar", "artefacto.html"), "w", encoding="utf-8") as f:
        f.write(titulo + "\n" + estilos.strip() + "\n" + cuerpo.strip() + "\n")
    print("OK  publicar/artefacto.html")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("visor", nargs="*", help="uno o varios visores HTML")
    ap.add_argument("--concurso", default=None, help="nombre del concurso que se muestra en la galeria")
    ap.add_argument("--id", default=None, help="id del recorrido (por defecto, el nombre del archivo sin _visor...)")
    ap.add_argument("--artefacto", action="store_true", help="solo regenerar publicar/artefacto.html")
    a = ap.parse_args()
    if not a.visor and not a.artefacto:
        ap.print_help(); sys.exit(1)
    for v in a.visor:
        importa(v, a.concurso, a.id if len(a.visor) == 1 else None)
    if os.path.exists(os.path.join(WEB, "index.html")):
        artefacto()
