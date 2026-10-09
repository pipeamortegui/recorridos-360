"""Agrega una imagen (render plano) a la app, para verla con el explorador: arrastrar, pellizcar, doble toque, mini-mapa.

Uso:
    python importar_imagen.py RUTA_A_LA_IMAGEN --titulo "Nombre que se ve" [--proyecto PRY-0005] [--concurso "..."] [--texto "..."] [--id ID]

Que hace:
  - Guarda la imagen completa en web/recorridos/<id>/imagen.jpg (hasta --max px de lado largo; por defecto 8192, para que abra en el iPhone).
  - Crea una copia liviana de 2400 px (media.jpg): la app la muestra de inmediato y cambia a la completa cuando termina de bajar.
  - Crea la portada 1200x700 de la galeria y agrega la ficha a web/recorridos/catalogo.json (tipo "imagen").
Despues: python publicar.py --subir   (la cifra y la sube, igual que los recorridos 360).
"""
import argparse, datetime, json, os, re, sys
from PIL import Image, ImageOps

from importar_visor import RECORRIDOS, CATALOGO, WEB, artefacto

Image.MAX_IMAGE_PIXELS = None     # los renders en 8K pasan el limite de seguridad de Pillow
MEDIA = 2400


def guarda(im, ruta, lado, calidad):
    if max(im.size) > lado:
        im = im.copy(); im.thumbnail((lado, lado), Image.LANCZOS)
    im.save(ruta, quality=calidad, optimize=True, progressive=True, subsampling=0 if calidad >= 90 else 2)
    return im.size


def importa(ruta, titulo, proyecto="", concurso=None, texto="", ident=None, maximo=8192):
    im = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    if not ident:
        ident = os.path.splitext(os.path.basename(ruta))[0]
    ident = re.sub(r"[^A-Za-z0-9._~-]", "-", ident)        # el id viaja en el #hash de la URL
    carpeta = os.path.join(RECORRIDOS, ident)
    os.makedirs(carpeta, exist_ok=True)

    ancho, alto = guarda(im, os.path.join(carpeta, "imagen.jpg"), maximo, 90)
    media = os.path.join(carpeta, "media.jpg")
    if max(ancho, alto) > MEDIA:
        guarda(im, media, MEDIA, 84)
    elif os.path.exists(media):
        os.remove(media)                                  # imagen pequena: basta con la completa

    # portada 12:7 desde el centro
    W, H = im.size
    if W / H > 12 / 7:
        cw, ch = round(H * 12 / 7), H
    else:
        cw, ch = W, round(W * 7 / 12)
    caja = ((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)
    im.crop(caja).resize((1200, 700), Image.LANCZOS).save(os.path.join(carpeta, "portada.jpg"), quality=84, optimize=True, progressive=True)

    proyecto = proyecto or (re.search(r"PRY-\d+", os.path.basename(ruta)) or [""])[0]
    cat = json.load(open(CATALOGO, encoding="utf-8")) if os.path.exists(CATALOGO) else []
    previo = next((c for c in cat if c["id"] == ident), {})
    ficha = {
        "id": ident,
        "tipo": "imagen",
        "titulo": titulo,
        "proyecto": proyecto,
        "concurso": concurso if concurso is not None else previo.get("concurso", ""),
        "texto": texto,
        "fecha": datetime.date.fromtimestamp(os.path.getmtime(ruta)).isoformat(),
        "fuente": os.path.basename(ruta),
        "ancho": ancho,
        "alto": alto,
        "imagen": f"recorridos/{ident}/imagen.jpg",
        "media": f"recorridos/{ident}/media.jpg" if max(ancho, alto) > MEDIA else f"recorridos/{ident}/imagen.jpg",
        "portada": f"recorridos/{ident}/portada.jpg",
    }
    cat = [c for c in cat if c["id"] != ident] + [ficha]
    cat.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    with open(CATALOGO, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)

    peso = sum(os.path.getsize(os.path.join(carpeta, n)) for n in os.listdir(carpeta)) / 1e6
    print(f"OK  {ident}: imagen {ancho} x {alto} px, {peso:.1f} MB en web/recorridos/{ident}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("imagen", help="la imagen (jpg, png, tif...)")
    ap.add_argument("--titulo", required=True, help="titulo que se ve en la galeria y en el explorador")
    ap.add_argument("--proyecto", default="", help="codigo del proyecto, p. ej. PRY-0005 (si no, se busca en el nombre del archivo)")
    ap.add_argument("--concurso", default=None, help="nombre del concurso que agrupa en la galeria")
    ap.add_argument("--texto", default="", help="una linea de descripcion bajo el titulo")
    ap.add_argument("--id", default=None, help="id (por defecto, el nombre del archivo)")
    ap.add_argument("--max", type=int, default=8192, help="lado largo maximo en px de la imagen completa (por defecto 8192)")
    a = ap.parse_args()
    if not os.path.exists(a.imagen):
        sys.exit("No encuentro la imagen: " + a.imagen)
    importa(a.imagen, a.titulo, a.proyecto, a.concurso, a.texto, a.id, a.max)
    if os.path.exists(os.path.join(WEB, "index.html")):
        artefacto()
