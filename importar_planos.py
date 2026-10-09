"""Agrega un juego de planos (laminas) a la app: se ven con el explorador, una tira de miniaturas y deslizar para pasar de lamina.

Uso:
    python importar_planos.py --id PRY-0005_planos --titulo "Nhà Nước · planos" --proyecto PRY-0005 LAMINA1.jpg LAMINA2.png ...
                              [--nombre "G-03=Planta de la casa · 1:25"] [--orden G,A,T,I,F,D] [--concurso "..."]

El codigo de cada lamina sale del nombre del archivo (G-03, T-04, F-01...): "G-03 Planta de la casa.jpg" da
codigo G-03 y titulo "Planta de la casa". --nombre cambia el titulo de un codigo (se puede repetir).
Si el juego ya existe, las laminas nuevas se suman y las de un codigo repetido se reemplazan.
El orden va por serie (--orden, por defecto G, A, T, I, F, D) y luego por numero.
Despues: python publicar.py --subir
"""
import argparse, datetime, json, os, re, sys
from PIL import Image, ImageOps

from importar_visor import RECORRIDOS, CATALOGO, WEB, artefacto

Image.MAX_IMAGE_PIXELS = None
MEDIA, MINI = 2400, 240


def guarda(im, ruta, lado, calidad):
    if max(im.size) > lado:
        im = im.copy(); im.thumbnail((lado, lado), Image.LANCZOS)
    im.save(ruta, quality=calidad, optimize=True, progressive=True, subsampling=0 if calidad >= 90 else 2)
    return im.size


def codigo_y_titulo(ruta):
    base = os.path.splitext(os.path.basename(ruta))[0]
    m = re.match(r"\s*([A-Za-z]{1,3})[-_ ]?(\d{1,3})[\s_\-·.]*(.*)$", base)
    if not m:
        return None, base.replace("_", " ").strip()
    return f"{m.group(1).upper()}-{int(m.group(2)):02d}", m.group(3).replace("_", " ").strip()


def clave_orden(orden):
    def k(h):
        m = re.match(r"([A-Z]+)-(\d+)", h["codigo"])
        serie, num = (m.group(1), int(m.group(2))) if m else (h["codigo"], 0)
        return (orden.index(serie) if serie in orden else len(orden), serie, num)
    return k


def importa(rutas, ident, titulo, proyecto="", concurso=None, nombres=None, orden="G,A,T,I,F,D"):
    ident = re.sub(r"[^A-Za-z0-9._~-]", "-", ident)        # el id viaja en el #hash de la URL
    carpeta = os.path.join(RECORRIDOS, ident)
    os.makedirs(carpeta, exist_ok=True)
    cat = json.load(open(CATALOGO, encoding="utf-8")) if os.path.exists(CATALOGO) else []
    previo = next((c for c in cat if c["id"] == ident), {})
    hojas = {h["codigo"]: h for h in previo.get("laminas", [])}
    nombres = nombres or {}

    for i, ruta in enumerate(rutas):
        codigo, tit = codigo_y_titulo(ruta)
        codigo = codigo or f"L-{len(hojas) + 1:02d}"
        tit = nombres.get(codigo, tit or (hojas.get(codigo) or {}).get("titulo", ""))
        im = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
        nom = codigo.lower()
        ancho, alto = guarda(im, os.path.join(carpeta, nom + ".jpg"), 8192, 90)
        media = f"recorridos/{ident}/{nom}.jpg"
        if max(ancho, alto) > MEDIA:
            guarda(im, os.path.join(carpeta, nom + "-media.jpg"), MEDIA, 84)
            media = f"recorridos/{ident}/{nom}-media.jpg"
        guarda(im, os.path.join(carpeta, nom + "-mini.jpg"), MINI, 80)
        hojas[codigo] = {"codigo": codigo, "titulo": tit, "ancho": ancho, "alto": alto, "fuente": os.path.basename(ruta),
                         "imagen": f"recorridos/{ident}/{nom}.jpg", "media": media, "mini": f"recorridos/{ident}/{nom}-mini.jpg"}
        print(f"    {codigo}  {tit}  ({ancho} x {alto} px)")
    for codigo, tit in nombres.items():
        if codigo in hojas:
            hojas[codigo]["titulo"] = tit

    laminas = sorted(hojas.values(), key=clave_orden([s.strip().upper() for s in orden.split(",")]))

    # portada: la primera lamina entera sobre su propio color de papel
    primera = Image.open(os.path.join(RECORRIDOS, ident, os.path.basename(laminas[0]["imagen"]))).convert("RGB")
    fondo = primera.getpixel((4, 4))
    lienzo = Image.new("RGB", (1200, 700), fondo)
    p = primera.copy(); p.thumbnail((1140, 660), Image.LANCZOS)
    lienzo.paste(p, ((1200 - p.width) // 2, (700 - p.height) // 2))
    lienzo.save(os.path.join(carpeta, "portada.jpg"), quality=86, optimize=True, progressive=True)

    ficha = {
        "id": ident,
        "tipo": "planos",
        "titulo": titulo or previo.get("titulo", ident),
        "proyecto": proyecto or previo.get("proyecto", ""),
        "concurso": concurso if concurso is not None else previo.get("concurso", ""),
        "fecha": datetime.date.today().isoformat(),
        "laminas": laminas,
        "portada": f"recorridos/{ident}/portada.jpg",
    }
    cat = [c for c in cat if c["id"] != ident] + [ficha]
    cat.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    with open(CATALOGO, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)

    # quitar archivos de laminas que ya no estan
    vivos = {"portada.jpg"} | {os.path.basename(h[k]) for h in laminas for k in ("imagen", "media", "mini")}
    for n in os.listdir(carpeta):
        if n not in vivos:
            os.remove(os.path.join(carpeta, n))
    peso = sum(os.path.getsize(os.path.join(carpeta, n)) for n in os.listdir(carpeta)) / 1e6
    print(f"OK  {ident}: {len(laminas)} lamina(s), {peso:.1f} MB en web/recorridos/{ident}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("laminas", nargs="+", help="las laminas (jpg, png...); el codigo sale del nombre del archivo")
    ap.add_argument("--id", required=True, help="id del juego de planos, p. ej. PRY-0005_planos")
    ap.add_argument("--titulo", default="", help="titulo en la galeria")
    ap.add_argument("--proyecto", default="", help="codigo del proyecto, p. ej. PRY-0005")
    ap.add_argument("--concurso", default=None, help="nombre del concurso que agrupa en la galeria")
    ap.add_argument("--nombre", action="append", default=[], help='titulo de una lamina: "G-03=Planta de la casa · 1:25"')
    ap.add_argument("--orden", default="G,A,T,I,F,D", help="orden de las series (por defecto G,A,T,I,F,D)")
    a = ap.parse_args()
    falta = [r for r in a.laminas if not os.path.exists(r)]
    if falta:
        sys.exit("No encuentro: " + ", ".join(falta))
    nombres = {}
    for n in a.nombre:
        if "=" not in n:
            sys.exit('--nombre va asi: "G-03=Planta de la casa · 1:25"')
        c, t = n.split("=", 1); nombres[c.strip().upper()] = t.strip()
    importa(a.laminas, a.id, a.titulo, a.proyecto, a.concurso, nombres, a.orden)
    if os.path.exists(os.path.join(WEB, "index.html")):
        artefacto()
