"""Arma el sitio publico CIFRADO en sitio/ y, si se pide, lo sube a GitHub.

Uso:
    python publicar.py                 pide la contrasena, cifra lo nuevo y deja sitio/ listo
    python publicar.py --subir         ademas hace commit y push (GitHub Pages se actualiza solo)
    python publicar.py --nueva-clave   cambia la contrasena: vuelve a cifrar todo con la nueva

Que se publica:
  - sitio/index.html, iconos y manifiesto (la app, sin ningun dato del proyecto).
  - sitio/datos/acceso.json: la sal y las iteraciones de PBKDF2 (no la contrasena).
  - sitio/datos/indice.bin: el catalogo y el mapa de archivos, cifrado.
  - sitio/datos/<aleatorio>.bin: cada panorama, miniatura, portada y recorrido.json, cifrado (AES-256-GCM).
Los nombres de los .bin son aleatorios: ni siquiera el nombre del proyecto queda a la vista.
Solo se cifra lo que cambio; lo demas se reutiliza, asi git no sube de nuevo los panoramas.
"""
import argparse, base64, getpass, hashlib, json, os, secrets, shutil, subprocess, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

RAIZ = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(RAIZ, "web")
RECORRIDOS = os.path.join(WEB, "recorridos")
SITIO = os.path.join(RAIZ, "sitio")
DATOS = os.path.join(SITIO, "datos")
ACCESO = os.path.join(DATOS, "acceso.json")
INDICE = "indice.bin"
ITER = 400_000
APP = ["index.html", "manifest.webmanifest", "icono-180.png", "icono-192.png", "icono-512.png"]


def cifra(clave, datos):
    iv = secrets.token_bytes(12)
    return iv + AESGCM(clave).encrypt(iv, datos, None)


def descifra(clave, blob):
    return AESGCM(clave).decrypt(blob[:12], blob[12:], None)


def pide_clave(confirmar):
    pw = os.environ.get("RECORRIDOS360_CLAVE")
    if pw:
        return pw
    pw = getpass.getpass("Contrasena de acceso: ")
    if confirmar:
        if len(pw) < 10:
            sys.exit("Usa al menos 10 caracteres (mejor una frase de 3 o 4 palabras).")
        if getpass.getpass("Repitela: ") != pw:
            sys.exit("Las contrasenas no coinciden. No se cambio nada.")
    return pw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subir", action="store_true", help="hacer commit y push al terminar")
    ap.add_argument("--nueva-clave", action="store_true", help="cambiar la contrasena y volver a cifrar todo")
    a = ap.parse_args()

    catalogo_ruta = os.path.join(RECORRIDOS, "catalogo.json")
    if not os.path.exists(catalogo_ruta):
        sys.exit("No hay recorridos: primero corre importar_visor.py.")
    os.makedirs(DATOS, exist_ok=True)

    nueva = a.nueva_clave or not os.path.exists(ACCESO)
    if nueva:
        acceso = {"v": 1, "sal": base64.b64encode(secrets.token_bytes(16)).decode(), "iter": ITER, "indice": INDICE}
        print("Contrasena NUEVA: todo se vuelve a cifrar.")
    else:
        acceso = json.load(open(ACCESO, encoding="utf-8"))
    pw = pide_clave(confirmar=nueva)
    clave = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), base64.b64decode(acceso["sal"]), acceso["iter"], 32)

    # lo ya publicado (para reutilizar lo que no cambio)
    previo = {}
    ruta_indice = os.path.join(DATOS, INDICE)
    if not nueva and os.path.exists(ruta_indice):
        try:
            previo = json.loads(descifra(clave, open(ruta_indice, "rb").read()))["archivos"]
        except InvalidTag:
            sys.exit("Esa no es la contrasena con la que esta publicado el sitio.\n"
                     "Si quieres cambiarla, corre: python publicar.py --nueva-clave")

    # cifrar cada archivo de cada recorrido
    archivos, nuevos, reusados = {}, 0, 0
    for ident in sorted(os.listdir(RECORRIDOS)):
        carpeta = os.path.join(RECORRIDOS, ident)
        if not os.path.isdir(carpeta):
            continue
        for nombre in sorted(os.listdir(carpeta)):
            logica = f"recorridos/{ident}/{nombre}"
            datos = open(os.path.join(carpeta, nombre), "rb").read()
            sha = hashlib.sha256(datos).hexdigest()
            p = previo.get(logica)
            if p and p[1] == sha and os.path.exists(os.path.join(DATOS, p[0])):
                archivos[logica] = p; reusados += 1
                continue
            bin_ = secrets.token_hex(12) + ".bin"
            open(os.path.join(DATOS, bin_), "wb").write(cifra(clave, datos))
            archivos[logica] = [bin_, sha]; nuevos += 1

    indice = {"catalogo": json.load(open(catalogo_ruta, encoding="utf-8")), "archivos": archivos}
    open(ruta_indice, "wb").write(cifra(clave, json.dumps(indice, ensure_ascii=False).encode("utf-8")))
    with open(ACCESO, "w", encoding="utf-8") as f:
        json.dump(acceso, f)

    # borrar los .bin que ya no se usan
    vivos = {v[0] for v in archivos.values()} | {INDICE}
    borrados = 0
    for n in os.listdir(DATOS):
        if n.endswith(".bin") and n not in vivos:
            os.remove(os.path.join(DATOS, n)); borrados += 1

    for n in APP:
        shutil.copy2(os.path.join(WEB, n), os.path.join(SITIO, n))
    open(os.path.join(SITIO, ".nojekyll"), "w").close()

    print(f"OK  sitio/ listo: {len(indice['catalogo'])} recorrido(s), {nuevos} archivo(s) cifrados, {reusados} reutilizados, {borrados} borrados.")

    if a.subir:
        def git(*args):
            subprocess.run(["git", *args], cwd=RAIZ, check=True)
        git("add", "-A")
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode == 0:
            print("No hay cambios que subir."); return
        git("commit", "-q", "-m", "Publicar recorridos (cifrado)")
        git("push", "-q")
        print("Subido. GitHub Pages se actualiza en uno o dos minutos.")


if __name__ == "__main__":
    main()
