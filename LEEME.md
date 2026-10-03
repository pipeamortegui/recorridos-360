# Recorridos 360

App web para mostrar los 360 de concurso en iPad y iPhone: una galería de recorridos y un visor (arrastrar, pellizcar, anillos y rótulos para saltar, plano con cono de visión, giroscopio, notas, ocultar controles).

URL pública, con contraseña: https://pipeamortegui.github.io/recorridos-360/

Enlace privado en Claude (sin contraseña, solo tu cuenta): https://claude.ai/artifact/RvpoBaj1mdpdimoNZWJsQ5

## Cómo se protege

- En GitHub solo se suben los archivos cifrados (AES-256-GCM). Los panoramas, las miniaturas, las portadas, las notas y hasta el nombre de cada proyecto quedan ilegibles, con nombres aleatorios.
- La contraseña no se guarda en ningún archivo. La app la pide y descifra todo en el navegador.
- "Recordar en este equipo" guarda la llave solo en ese navegador. El botón **Cerrar acceso** de la galería la borra (úsalo si lo abriste en un equipo ajeno).
- No hay registro de quién entra. Para quitarle el acceso a alguien, cambia la contraseña (`python publicar.py --nueva-clave --subir`).
- Usa una frase larga (3 o 4 palabras). La seguridad depende de que no se pueda adivinar.

## Carpetas

- `web/`: la app y los recorridos **sin cifrar** (`web/recorridos/`). Se queda solo en tu equipo; está en `.gitignore`.
- `sitio/`: lo que se publica, que es la app y `datos/` cifrado. Lo genera `publicar.py`; no se edita a mano.
- `publicar/artefacto.html`: la versión para el Artifact de Claude.

## Agregar un paquete nuevo

```
python importar_visor.py "C:\Users\obeda\Downloads\PRY-XXXX_r360_..._visor.html" --concurso "Nombre del concurso"
python publicar.py --subir
```

`publicar.py` pide la contraseña, cifra solo lo nuevo, hace commit y push. La página se actualiza en uno o dos minutos.

## Probar en local

```
python -m http.server 8360 --directory web
```

Abre http://localhost:8360 (versión sin cifrar). Para probar la versión cifrada usa `--directory sitio` y el puerto 8361.
