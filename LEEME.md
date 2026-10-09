# Recorridos 360

App web para mostrar los 360 de concurso en iPad y iPhone: una galería de recorridos y un visor (arrastrar, pellizcar, anillos y rótulos para saltar, plano con cono de visión, giroscopio, notas, ocultar controles). También muestra órbitas 360 alrededor de la casa, imágenes planas (renders), juegos de planos y diseños técnicos, cada tipo en su sección.

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

## Agregar una imagen (render plano) para explorarla

```
python importar_imagen.py "C:\Users\obeda\Downloads\render_8k.jpg" --titulo "Nhà Nước · vista exterior" --proyecto PRY-0005
python publicar.py --subir
```

En la galería sale con el botón **Explorar la imagen**: se arrastra para recorrerla, se pellizca (o rueda del ratón) para acercar, doble toque para acercar donde tocaste, y el mini-mapa de la esquina lleva a cualquier zona. Acepta imágenes de hasta 8K (8192 px de lado largo; `--max` cambia el tope). La app abre primero una copia liviana de 2400 px y cambia a la completa cuando termina de bajar.

## Agregar planos (un juego de láminas)

```
python importar_planos.py --id PRY-0005_planos --titulo "Nhà Nước · planos" --proyecto PRY-0005 "C:\ruta\G-03 Planta de la casa.jpg" "C:\ruta\G-04 Planta de cubierta.jpg"
python publicar.py --subir
```

El código de cada lámina sale del nombre del archivo (`G-03`, `T-04`, `F-01`...) y el resto del nombre es su título. `--nombre "G-03=Planta de la casa · 1:25"` cambia un título. Si el juego ya existe, las láminas nuevas se suman y las de un código repetido se reemplazan; el orden va por serie (G, A, T, I, F, D) y número. En la app: tira de miniaturas abajo, deslizar de lado (o flechas ← →) con la lámina completa para pasar a la siguiente, y cada lámina tiene su enlace (`#PRY-0005_planos?l=G-03`). Mejor exportarlas grandes (PNG o JPG de 4000 a 8000 px) para leer los textos al acercar.

## Agregar diseños técnicos (sección aparte)

Igual que los planos, con `--tipo tecnico`. Si las láminas no traen código, nómbralas `S-01`, `S-02`... y dales un nombre corto para la tira con `|`:

```
python importar_planos.py --id PRY-0005_tecnicos --titulo "Nhà Nước · sistemas" --proyecto PRY-0005 --tipo tecnico "C:\ruta\S-01.png" "C:\ruta\S-02.png" --nombre "S-01=Dónde vive cada sistema|Sistemas" --nombre "S-02=Energía: del techo al enchufe|Energía"
python publicar.py --subir
```

## Agregar una órbita 360 (fotogramas alrededor de la casa)

```
python importar_orbita.py "C:\Users\obeda\Downloads\FACHADA-A-ORBITA-360_visor.html" --id PRY-0005_orbita_fachada_A --titulo "Nhà Nước · órbita · fachada del perímetro A"
python publicar.py --subir
```

Saca los fotogramas, las vistas fijas y los rumbos del visor. En la app: arrastrar de lado gira la casa, pellizcar acerca, girar solo (20, 10 o 5 s por vuelta), giroscopio, brújula y vistas fijas. Primero baja unos fotogramas repartidos en la vuelta para poder girar de inmediato y luego rellena los demás.

## Secciones de la galería

La galería se ordena en Recorridos 360, Órbitas, Imágenes, Planos y Diseños técnicos; los botones de arriba muestran una sola sección o todas.

## Probar en local

```
python -m http.server 8360 --directory web
```

Abre http://localhost:8360 (versión sin cifrar). Para probar la versión cifrada usa `--directory sitio` y el puerto 8361.
