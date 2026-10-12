"""Arma el sitio publico CIFRADO en sitio/ y, si se pide, lo sube a GitHub.

Uso:
    python publicar.py                 pide la contrasena, cifra lo nuevo y deja sitio/ listo
    python publicar.py --subir         ademas hace commit y push (GitHub Pages se actualiza solo)
    python publicar.py --nueva-clave   cambia la contrasena: vuelve a cifrar todo con la nueva
    python publicar.py --ventana       pide la contrasena en una ventana de Windows (sin terminal)
    python publicar.py --enlace        imprime el enlace con llave: entra sin escribir la contrasena
                                       (deja de servir cuando cambias la contrasena con --nueva-clave)
    python publicar.py --enlace --para "Cliente A"
                                       el enlace lleva el nombre de esa persona: los avisos dicen quien entro
    python publicar.py --aviso TEMA    avisos de visitas al celular por ntfy (app gratuita, sin cuenta);
                                       --aviso no los apaga. El tema queda dentro del indice cifrado.
    python publicar.py --quitar ID     quita ese recorrido, imagen, orbita o juego de laminas del sitio

Antes de publicar baja lo ultimo de GitHub (git pull) y recupera del sitio publicado lo que no este en
web/recorridos de este equipo (lo descifra con la contrasena): publicar desde otro equipo no borra nada.

Que se publica:
  - sitio/index.html, iconos y manifiesto (la app, sin ningun dato del proyecto).
  - sitio/datos/acceso.json: la sal y las iteraciones de PBKDF2 (no la contrasena).
  - sitio/datos/indice.bin: el catalogo y el mapa de archivos, cifrado.
  - sitio/datos/<aleatorio>.bin: cada panorama, miniatura, portada y recorrido.json, cifrado (AES-256-GCM).
Los nombres de los .bin son aleatorios: ni siquiera el nombre del proyecto queda a la vista.
Solo se cifra lo que cambio; lo demas se reutiliza, asi git no sube de nuevo los panoramas.
"""
import argparse, base64, getpass, hashlib, json, os, re, secrets, shutil, subprocess, sys
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
VENTANA = False
URL = "https://pipeamortegui.github.io/recorridos-360/"
APP = ["index.html", "manifest.webmanifest", "icono-180.png", "icono-192.png", "icono-512.png"]


def cifra(clave, datos):
    iv = secrets.token_bytes(12)
    return iv + AESGCM(clave).encrypt(iv, datos, None)


def descifra(clave, blob):
    return AESGCM(clave).decrypt(blob[:12], blob[12:], None)


def pide_clave_ventana(confirmar, texto=None):
    """Ventana de Windows para escribir la contrasena (sin terminal)."""
    import tkinter as tk
    raiz = tk.Tk()
    raiz.title("Recorridos 360 · contraseña")
    raiz.configure(bg="#12181b", padx=24, pady=20)
    raiz.resizable(False, False)
    raiz.attributes("-topmost", True)
    fuente, tenue, texto, oro = ("Segoe UI", 11), "#a3aca9", "#ece7df", "#d9b36c"
    tk.Label(raiz, text="Contraseña de acceso a los recorridos", font=("Segoe UI", 13, "bold"), bg="#12181b", fg=texto).pack(anchor="w")
    tk.Label(raiz, text=texto or ("Mínimo 10 caracteres. Mejor una frase de 3 o 4 palabras.\nGuárdala bien: si se olvida, hay que publicar con una nueva."
                         if confirmar else "Escribe la contraseña con la que publicaste."),
             font=("Segoe UI", 10), bg="#12181b", fg=tenue, justify="left").pack(anchor="w", pady=(4, 12))
    campos = []
    for etiqueta in (["Contraseña", "Repítela"] if confirmar else ["Contraseña"]):
        tk.Label(raiz, text=etiqueta, font=("Segoe UI", 10), bg="#12181b", fg=tenue).pack(anchor="w")
        e = tk.Entry(raiz, show="•", font=fuente, width=34, bg="#0c1012", fg=texto, insertbackground=texto, relief="flat",
                     highlightthickness=1, highlightbackground="#3a4245", highlightcolor=oro)
        e.pack(fill="x", ipady=6, pady=(2, 10)); campos.append(e)
    error = tk.Label(raiz, text="", font=("Segoe UI", 10), bg="#12181b", fg="#e8a08a"); error.pack(anchor="w")
    res = {"pw": None}

    def aceptar(_=None):
        v = [c.get() for c in campos]
        if confirmar and len(v[0]) < 10:
            error.config(text="Usa al menos 10 caracteres."); return
        if confirmar and v[0] != v[1]:
            error.config(text="Las dos no coinciden."); return
        if not v[0]:
            return
        res["pw"] = v[0]; raiz.destroy()

    tk.Button(raiz, text="Cifrar y guardar", command=aceptar, font=("Segoe UI", 11, "bold"), bg=oro, fg="#1a1408",
              activebackground="#e6c588", relief="flat", padx=16, pady=6).pack(anchor="e", pady=(8, 0))
    raiz.bind("<Return>", aceptar)
    raiz.update_idletasks()
    x = (raiz.winfo_screenwidth() - raiz.winfo_width()) // 2; y = (raiz.winfo_screenheight() - raiz.winfo_height()) // 3
    raiz.geometry(f"+{x}+{y}")
    raiz.after(200, lambda: (raiz.focus_force(), campos[0].focus_set()))
    raiz.mainloop()
    if not res["pw"]:
        sys.exit("Cancelado: no se cambio nada.")
    return res["pw"]


def pide_clave(confirmar, entorno="RECORRIDOS360_CLAVE", texto=None):
    pw = os.environ.get(entorno)
    if pw:
        return pw
    if VENTANA:
        return pide_clave_ventana(confirmar, texto)
    pw = getpass.getpass((texto or "Contrasena de acceso") + ": ")
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
    ap.add_argument("--ventana", action="store_true", help="pedir la contrasena en una ventana en vez de la terminal")
    ap.add_argument("--enlace", action="store_true", help="imprimir el enlace con llave (entra sin contrasena)")
    ap.add_argument("--para", default="", help='con --enlace: a quien se le manda (p. ej. "Cliente A"); los avisos dicen ese nombre')
    ap.add_argument("--aviso", default=None, help='tema de ntfy para los avisos de visitas al celular; "no" los apaga')
    ap.add_argument("--quitar", action="append", default=[], help="id a quitar del sitio (se puede repetir)")
    a = ap.parse_args()
    global VENTANA
    VENTANA = a.ventana

    if a.enlace:
        if not os.path.exists(ACCESO):
            sys.exit("Todavia no hay sitio cifrado: corre primero python publicar.py")
        acceso = json.load(open(ACCESO, encoding="utf-8"))
        pw = pide_clave(confirmar=False)
        clave = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), base64.b64decode(acceso["sal"]), acceso["iter"], 32)
        try:
            descifra(clave, open(os.path.join(DATOS, INDICE), "rb").read())
        except InvalidTag:
            sys.exit("Esa no es la contrasena con la que esta publicado el sitio.")
        # la llave va despues de #: el navegador no la envia a ningun servidor
        enlace = URL + "#k=" + base64.urlsafe_b64encode(clave).decode().rstrip("=")
        if a.para:          # el nombre tal cual: los avisos al celular dicen "Entro <nombre>"
            from urllib.parse import quote
            enlace += "&de=" + quote(a.para.strip()[:40], safe="")
            print(f"Para: {a.para.strip()[:40]}")
        print(enlace)
        print("Quien tenga este enlace entra sin contrasena. Para anularlo: python publicar.py --nueva-clave --subir")
        return

    catalogo_ruta = os.path.join(RECORRIDOS, "catalogo.json")
    os.makedirs(RECORRIDOS, exist_ok=True)
    os.makedirs(DATOS, exist_ok=True)

    if a.subir:      # lo ultimo publicado, para no pisar lo que se subio desde otro equipo
        r = subprocess.run(["git", "pull", "--ff-only", "-q"], cwd=RAIZ)
        if r.returncode != 0:
            sys.exit("No se pudo bajar lo ultimo de GitHub (git pull). Revisa la conexion o los cambios sin guardar.")

    nueva = a.nueva_clave or not os.path.exists(ACCESO)
    ruta_indice = os.path.join(DATOS, INDICE)
    ind_previo, clave_previa, acceso_previo = {}, None, None
    if os.path.exists(ACCESO) and os.path.exists(ruta_indice):
        acceso_previo = json.load(open(ACCESO, encoding="utf-8"))
        pw0 = pide_clave(False, texto="Contrasena ACTUAL" if nueva else None)
        clave_previa = hashlib.pbkdf2_hmac("sha256", pw0.encode("utf-8"), base64.b64decode(acceso_previo["sal"]), acceso_previo["iter"], 32)
        try:
            ind_previo = json.loads(descifra(clave_previa, open(ruta_indice, "rb").read()))
        except InvalidTag:
            sys.exit("Esa no es la contrasena con la que esta publicado el sitio.")
    if nueva:
        acceso = {"v": 1, "sal": base64.b64encode(secrets.token_bytes(16)).decode(), "iter": ITER, "indice": INDICE}
        print("Contrasena NUEVA: todo se vuelve a cifrar.")
        pw = pide_clave(True, entorno="RECORRIDOS360_CLAVE_NUEVA" if ind_previo else "RECORRIDOS360_CLAVE",
                        texto="Contrasena NUEVA" if ind_previo else None)
        clave = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), base64.b64decode(acceso["sal"]), acceso["iter"], 32)
    elif clave_previa is not None:
        acceso, clave = acceso_previo, clave_previa
    else:            # hay acceso.json pero no indice: se cifra con la contrasena de siempre
        acceso = json.load(open(ACCESO, encoding="utf-8"))
        pw = pide_clave(False)
        clave = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), base64.b64decode(acceso["sal"]), acceso["iter"], 32)

    # recuperar del sitio lo que este equipo no tiene (lo subido desde otro equipo); --quitar lo descarta
    quitar = set(a.quitar)
    catalogo = json.load(open(catalogo_ruta, encoding="utf-8")) if os.path.exists(catalogo_ruta) else []
    locales = {c["id"] for c in catalogo}
    recuperados = 0
    for c in ind_previo.get("catalogo", []):
        if c["id"] in locales or c["id"] in quitar:
            continue
        for logica, (bin_, sha) in ind_previo.get("archivos", {}).items():
            if logica.startswith(f"recorridos/{c['id']}/"):
                ruta = os.path.join(WEB, *logica.split("/"))
                os.makedirs(os.path.dirname(ruta), exist_ok=True)
                open(ruta, "wb").write(descifra(clave_previa, open(os.path.join(DATOS, bin_), "rb").read()))
        catalogo.append(c); recuperados += 1
    for ident in quitar:
        catalogo = [c for c in catalogo if c["id"] != ident]
        shutil.rmtree(os.path.join(RECORRIDOS, ident), ignore_errors=True)
    if not catalogo:
        sys.exit("No hay recorridos: primero corre importar_visor.py.")
    catalogo.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    with open(catalogo_ruta, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=1)
    if recuperados:
        print(f"Recuperados del sitio publicado: {recuperados} (no estaban en este equipo).")

    # lo ya publicado con esta misma clave (para reutilizar lo que no cambio)
    previo = ind_previo.get("archivos", {}) if not nueva else {}
    aviso = ind_previo.get("aviso")
    if a.aviso is not None:
        aviso = None if a.aviso.lower() in ("no", "") else re.sub(r"[^A-Za-z0-9_-]", "", a.aviso)

    # cifrar cada archivo de cada recorrido
    archivos, nuevos, reusados = {}, 0, 0
    vigentes = {c["id"] for c in catalogo}
    for ident in sorted(os.listdir(RECORRIDOS)):
        carpeta = os.path.join(RECORRIDOS, ident)
        if not os.path.isdir(carpeta) or ident not in vigentes:
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

    indice = {"catalogo": catalogo, "archivos": archivos}
    if aviso:
        indice["aviso"] = aviso        # tema de ntfy: va cifrado, solo lo lee quien entra
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

    print(f"OK  sitio/ listo: {len(indice['catalogo'])} recorrido(s), {nuevos} archivo(s) cifrados, {reusados} reutilizados, {borrados} borrados."
          + (f" Avisos al celular: ntfy, tema {aviso}." if aviso else ""))

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
