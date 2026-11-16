# PRACTIC_APP: tutor universitario con IA (FECI-2026)

Aplicación web hecha con Streamlit que funciona como tutor universitario. Los maestros suben su material de
clase en PDF y los alumnos conversan con una IA que **responde solo con ese material**, practica con ellos
mediante quizzes y ejercicios, y se adapta a su nivel en cada tema.

## Qué hace

**Alumno**
- Chat de estudio por tema. La respuesta incluye las fuentes (archivo y página del PDF).
- Puede estudiar las materias de su cuatrimestre o elegir **«Todas las materias»**, y cambiar su universidad,
  carrera y cuatrimestre desde el menú lateral.
- Tres vistas separadas en la página de estudio: **Conversación**, **Ejercicio práctico** y **Examen**. Cada una
  guarda su propia conversación en el historial.
- **Conversación guiada por el tutor:** en un chat nuevo el tutor saluda y pregunta si inician la lección o hay una
  pregunta. Al volver a una conversación anterior (se elige en el selector de arriba) pregunta si quieres
  retroalimentación, continuar donde lo dejaron u otra pregunta. También entiende órdenes escritas como
  «comencemos», «continuemos» o «dame retroalimentación», que no son preguntas sobre el contenido. Con «pasemos al
  siguiente tema» (o «otro tema», «cambiemos de tema») el menú pasa solo al tema que sigue en la retícula, aunque sea
  de otra unidad, y no gasta consultas a la IA; «siguiente lección» sigue la explicación del tema actual. Cuando el
  alumno contesta la pregunta de comprobación del tutor (una respuesta corta, sin «?»), el tutor la **evalúa** con el
  material —correcta, parcial o incorrecta, y por qué— en lugar de tratarla como una pregunta nueva.
- **Examen** de varias preguntas (de 3 a 10) en **modo concentración**: mientras dura, se oculta el menú lateral,
  la conversación y las otras vistas. Después de cada pregunta se ve la respuesta correcta y su explicación. La
  dificultad empieza según su nivel en el tema, sube un nivel cuando acierta y baja uno cuando falla (básica,
  intermedia, avanzada y experta). Al terminar muestra el resultado y la dificultad más alta que resolvió.
- **🔁 Repasar errores:** las preguntas que fallaste y todavía no has acertado, con su respuesta y explicación, y
  una práctica sin distracciones que las vuelve a plantear. Las que corriges salen de la lista.
- **Qué estudiar ahora** (en «Mi progreso»): sugiere los siguientes temas según la retícula y tus niveles: primero
  reforzar lo de precisión baja, luego continuar lo empezado y después un tema nuevo. Solo propone temas con material.
- **Ejercicio práctico** en su propia pantalla: el enunciado, tu respuesta y la calificación de la IA (0 a 10).
- La explicación y el nivel inicial se adaptan por tema: modo *refuerzo* si le cuesta (menos de 50% de
  aciertos), *normal*, o *avanzado* (80% o más).
- Las preguntas priorizan el material de lo que el alumno falló y evitan repetir las recientes.
- **Revisión de cada pregunta:** antes de mostrarla, una segunda llamada a la IA la resuelve sin ver la
  respuesta. Si elige otra opción, la considera ambigua o la clave no coincide con el cálculo, se descarta y se
  genera otra (hasta 4 intentos). Las preguntas deben indicar si el circuito es en serie, en paralelo o mixto y
  llevar unidades. Esto usa unas 2 llamadas a Groq por pregunta.
- **Niveles por tema, unidad y materia (según la retícula):** cada acierto suma XP igual a su dificultad (1 a 4) y
  los ejercicios de 0 a 3. Niveles: Principiante (1 XP), Intermedio (6), Avanzado (14) y Experto (24). Con menos
  de 50% de aciertos en 4 o más intentos no pasa de Principiante. El nivel de una unidad o de la materia es el
  promedio de sus temas. Se ve en «Mi progreso», en el chat y al terminar cada examen.
- Página «Mi progreso» con tiempo de estudio, aciertos por tema, promedio en ejercicios y temas por repasar.
- Historial de conversaciones con búsqueda.

**Maestro**
- **Retícula:** sube el programa de la asignatura (PDF). La IA extrae las unidades, los temas y lo que el
  alumno debe saber y saber hacer en cada uno, muestra una vista previa y crea la materia con su universidad,
  carrera y cuatrimestre. Si la materia ya existe, la completa sin duplicar.
- **Editar la retícula:** renombrar la materia, las unidades y los temas, y corregir lo que el alumno debe saber
  y saber hacer. Cambiar un nombre no afecta el material ni el avance de los alumnos (cuelgan del tema, no de
  su nombre).
- **Avance por unidad:** en Estadísticas, el nivel y el % de cada alumno por unidad de la retícula.
- **Material:** sube los PDFs de toda la materia y la app reparte cada fragmento entre los temas de la
  retícula según su parecido (lo que no se parece a ningún tema no se guarda). También puede subir un PDF
  a un tema específico. Los PDF deben tener texto, no ser escaneos.
- **Cobertura de la materia:** qué temas ya tienen material, cuáles no, y los temas con un PDF registrado
  cuyo contenido no está en la base. Desde ahí también se puede borrar un PDF.
- Estadísticas: preguntas por tema, aciertos, alumnos más activos, preguntas de quiz más falladas.
- **Preguntas sin respuesta:** lo que el tutor no pudo contestar, es decir, material que falta subir.
- **Tiempo en la app** por alumno y **actividad a revisar** (respuestas demasiado rápidas, ráfagas de
  respuestas, mejoras bruscas). Son indicios, no prueba de trampa.
- **Aviso de material faltante:** si varios alumnos distintos preguntan lo que el material no cubre en un mismo
  tema, aparece un aviso en Estadísticas y en la página de material.
- **Descargas:** resumen por alumno en CSV y reporte completo en Excel (una hoja por tabla; respeta las materias
  y la búsqueda elegidas).

**Administrador**
- Crea usuarios, asigna materias a maestros y ve lo mismo que el maestro.
- **Restablece la contraseña** de cualquier usuario que la olvidó (en «Mi cuenta»).

**Clases**
- **Clases del maestro** (menú «Clases»): cada clase es un grupo de UNA materia que el maestro tiene asignada (el
  administrador puede crearlas de cualquiera). Tiene un código de 6 letras y números que se comparte; se puede
  cambiar si se filtra. La clase puede pedir que el maestro apruebe a cada alumno o dejar entrar al instante.
  Desde ahí el maestro ve la lista de alumnos, acepta o rechaza solicitudes, quita alumnos, publica avisos,
  desactiva o elimina la clase (el progreso de los alumnos no se borra).
- **Mis clases** (alumno): se une escribiendo el código (5 intentos fallidos por sesión), ve sus clases, su estado
  (aceptado o esperando aprobación), puede salirse y lee los avisos. En Estudio, «Mis clases» muestra las materias
  de las clases donde ya fue aceptado, y los últimos avisos aparecen arriba.
- **Estadísticas por clase:** filtro «Clase» en Estadísticas (también afecta al reporte de Excel y al aviso de
  material faltante). Tablas `clases`, `inscripciones` y `avisos`.
- **Tareas con fecha límite:** en la pestaña «Tareas» de cada clase, el maestro elige un tema de la materia, qué debe
  lograr cada alumno (responder N preguntas de examen, resolver N ejercicios o llegar a un nivel del tema), la fecha y
  unas indicaciones. No hay nada que entregar: se cumplen solas con lo que el alumno hace en Estudio (cuentan las
  preguntas y ejercicios hechos desde que se asignó). El maestro ve cuántos la cumplieron y el avance de cada alumno;
  el alumno las ve en «Mis clases» y un resumen arriba de Estudio, con su estado (pendiente, por vencer, vencida o
  hecha). Tabla `tareas`.

- **Avisos y cumplimiento:** al asignar una tarea se publica un aviso en la clase. «Mis clases (2)» muestra en el menú
  cuántas tareas faltan. El maestro descarga en Excel quién cumplió cada tarea (y el reporte de Estadísticas la
  incluye cuando eliges una clase). Las fechas límite aparecen como puntos ámbar en el calendario de «Mi progreso».
- **Boletín semanal** (Clases → pestaña «Boletín»): los últimos 7 días contra la semana anterior; cuántos alumnos
  estuvieron activos, preguntas y quizzes, a quién buscar (con poco acierto, sin actividad o que aún no entran), quién
  destaca, temas con más errores, tareas de la semana y temas donde falta material. Se descarga como texto para pegar
  en un correo o como Excel. Solo lo ve el maestro de la clase (o un administrador).

**Alumno: repaso y retos**
- **Repaso espaciado** (menú «Repaso (n)»): cada pregunta fallada y nunca acertada se vuelve una tarjeta; acertarla la
  espacia (1, 3, 7 y 14 días) y fallarla la regresa al inicio; tras cuatro aciertos queda dominada. No suma XP.
  Tabla `tarjetas_repaso` (`core/repaso.py`).
- **Reto de la semana y liga:** cada lunes cambia el reto (preguntas, días, ejercicios, XP o minutos) y la liga semanal de
  la clase vuelve a cero. Se mide con la actividad existente, sin tabla propia (`core/retos.py`); hay un logro
  «Retador».
- **Tu día** (arriba de Estudio): aviso de racha en riesgo, tarjetas de repaso para hoy y avance del reto.
- **Atajos del tutor** bajo cada respuesta: «Explícamelo más simple», «Dame un ejemplo», «Hazme una pregunta» y «Resumen
  del tema» (también se puede escribir «resumen»).

**Respaldo**
- En Administración, «Respaldo de la base» descarga un .zip con todas las tablas. `python scripts/respaldo.py` guarda uno
  en `respaldos/` (ignorada por git) y conserva los últimos 10; sirve con el Programador de tareas de Windows.
  `python scripts/latencia.py` mide el tiempo de ida y vuelta a la base.

**Rendimiento**
- Con una base remota cada consulta cuesta ~70 ms, así que las pantallas guardan en caché sus lecturas (`core/cache.py`,
  decorador `@memo`): se vacía sola cuando algo se escribe en la base y, a lo más, a los 60 s. Esas lecturas usan una
  conexión sin transacción (1 viaje a la base en lugar de 3) y la conexión solo se comprueba si estuvo sin usarse
  30 s. Con la variable de entorno `PRACTIC_SIN_CACHE=1` la caché se apaga.

**Alumno: metas y logros**
- **Respuestas en vivo:** el tutor escribe la respuesta mientras el modelo la genera. Si la IA falla (límite del
  plan gratuito, sin conexión) se muestra un mensaje claro con botón «Reintentar».
- **Meta diaria de estudio** (10 a 60 minutos) y calendario de las últimas 5 semanas en «Mi progreso».
- **Logros:** 76 logros en 7 categorías (Constancia, Dominio, Práctica, Exámenes, Exploración, Comunidad y
  Especiales), cada uno con 4 niveles: Bronce, Plata, Élite (con el color de su categoría) y Oro, que es el más alto
  y brilla con una animación. Son 304 medallas. Se calculan con la actividad ya guardada.
- **Mi perfil:** título según los XP (Novato a Leyenda), gráfica de XP por semana, temas que domina y el catálogo
  completo de logros. El alumno elige hasta 6 logros para su **vitrina** (`usuarios.vitrina`).
- **Competencia en la clase:** ranking por XP de todos los compañeros (total o de la semana) y perfil de cada uno
  con su vitrina, racha, minutos de estudio, temas dominados y gráfica de XP por semana. Solo se comparte esfuerzo:
  no se muestran calificaciones ni errores. Solo lo ven los compañeros de clase, su maestro y el administrador.

**Todos los roles**
- **Animación de carga:** mientras la IA prepara una pregunta, un ejercicio, una calificación o una explicación, debajo
  del indicador aparece una animación distinta cada vez (11 en total, sin repetir la anterior): un libro que pasa sus páginas, un lápiz que
  escribe, un birrete que se lanza, una pila de libros, una lupa, una bombilla, engranes, barras, una lista de tareas,
  un cohete y un átomo (`core/estudiante.py` y `core/cargas.py`). Es un SVG con
  CSS (`core/estudiante.py`), funciona en tema claro y oscuro, y con «reducir movimiento» queda quieta.
- **Sesión recordada:** al marcar «Mantener mi sesión iniciada» (14 días) no hay que volver a entrar al recargar
  la página. En el navegador solo queda un código aleatorio; la base guarda su huella SHA-256 (tabla `sesiones`).
  Cerrar sesión, cambiar la contraseña o desactivar la cuenta lo invalidan. No usarla en equipos compartidos.
- **Mi cuenta:** cambiar la propia contraseña (pide la actual y una confirmación). El mínimo son 8 caracteres con al
  menos una letra y un número; se rechazan las más comunes (`password1`, `qwerty123`…), las muy repetitivas y las que
  contienen el correo. El máximo son 72 bytes. Las cuentas que ya existen no se tocan: la regla aplica al crear o cambiar.
- **Intentos de inicio de sesión:** tras 5 contraseñas incorrectas para un correo, ese correo se bloquea 15 minutos
  (cuenta también los correos que no existen, para no revelar quién tiene cuenta). Se guarda en la base (`intentos_login`).
- **Registro de errores:** los fallos del tutor, del material y de cualquier página se guardan en la tabla `errores_app`
  (sin contraseñas ni claves: se tapan antes de guardar) y el administrador los ve en «Administración → Errores».
- Si el administrador olvida la suya, se restablece desde la terminal, con el entorno virtual activo y el `.env`:

```bash
python scripts/restablecer_password.py correo@ejemplo.com
```

## Cómo funciona

1. El PDF se divide en fragmentos y cada uno se guarda con su vector en la tabla `fragmentos` de la base de
   datos compartida (así todas las personas que usen la app ven el mismo contenido).
2. Cuando el alumno pregunta, se buscan los fragmentos más parecidos (embeddings locales con FastEmbed y
   similitud coseno).
3. Groq recibe los fragmentos como contexto y responde solo con ellos. Si el material no contiene la
   respuesta, el tutor lo dice y la pregunta se guarda para el maestro.

## Estructura del proyecto

```
app.py              Router principal: páginas según el rol
.streamlit/         config.toml: tema visual (colores, tipografías, menú lateral)
assets/             Logo e ícono de la app
core/               Lógica
  estilo.py           diseño compartido: encabezados, tarjetas, íconos, gráficas y hoja de estilos
  auth.py             login, usuarios y sesión
  llm.py              prompts y llamadas a Groq (tutor, quiz, calificación)
  rag.py              indexado y búsqueda por significado (tabla `fragmentos` de la base de datos)
  quiz.py             generación y evaluación de preguntas
  examen.py           reglas del examen con dificultad progresiva
  niveles.py          XP, niveles por tema y avance por unidad de la retícula
  reticula.py         lectura del programa de asignatura y creación de materia, unidades y temas
  material.py         subida de PDFs de toda la materia, repartidos por temas
  tutoria.py          el tutor como guía: iniciar la lección, continuarla, retroalimentar, detectar órdenes
  progreso.py         nivel por tema, ejercicios calificados
  actividad.py        registro del tiempo de uso y racha de días seguidos
  sospechas.py        reglas de actividad a revisar
  stats.py            consultas de estadísticas para el maestro
  cuenta.py           cambio y restablecimiento de contraseñas
  logros.py           meta diaria, calendario y logros del alumno
  clases.py           clases: códigos, inscripciones, aprobación y avisos
  tareas.py           tareas con fecha límite: asignar, medir el avance y estados
  repaso.py           repaso espaciado (tarjetas con cajas de 1, 3, 7 y 14 días)
  retos.py            reto de la semana y su avance
  hoy.py              pendientes del día: insignias del menú y panel «Tu día»
  respaldo.py         respaldo de la base en .zip
  boletin.py          boletín semanal de una clase para su maestro
  seguridad.py        límite de intentos al iniciar sesión
  errores.py          registro de fallos de la app (tabla `errores_app`)
  cache.py            caché de lecturas de la base (se vacía al escribir)
  competencia.py      XP, ranking de la clase y perfil público de un alumno
  perfil_ui.py        pantalla de perfil (propio y de compañeros)
  sesion.py           sesión recordada (cookie con código aleatorio; la base guarda solo su huella)
  tema.py             botón de modo claro/oscuro que conserva la sesión
  chat.py, perfil.py, pdf_loader.py, db.py, config.py, passwords.py, ui.py
models/schema.py    Tablas (SQLAlchemy)
vistas/             Pantallas de Streamlit (login, estudio, progreso, historial, cuenta, admin, maestro, estadísticas)
scripts/            datos_demo.py: crea o borra datos de ejemplo
tests/              Pruebas automáticas
```

Jerarquía académica: universidad → carrera → cuatrimestre → materia → unidad → tema.

## Parte 1 - Configuración del entorno local

Necesitas Python 3.11 o 3.12. No uses versiones superiores, porque las dependencias del proyecto pueden no
funcionar.

Clona el repositorio:

```bash
git clone https://github.com/xalws/FECI-2026.git
cd FECI-2026
```

Crea y activa el entorno virtual (Windows):

```bash
py -3.12 -m venv venv
venv\Scripts\activate
```

Instala las librerías:

```bash
pip install -r requirements.txt
```

## Parte 2 - Servicios y variables de entorno

Crea un archivo `.env` en la raíz del proyecto (junto a `app.py`) con estas llaves:

```
GROQ_API_KEY=gsk_tu_clave_aqui
DATABASE_URL=postgresql://usuario:password@ep-host-name.region.aws.neon.tech/neondb?sslmode=require
```

Opcionales: `GROQ_MODEL`, `GROQ_MODEL_RESPALDO` (modelo al que cambia el tutor durante un minuto cuando el principal llega
a su límite de Groq; cada modelo tiene su propia cuota; por defecto `openai/gpt-oss-20b`, vacío para desactivarlo), `MIN_SCORE` (similitud mínima para responder), `UMBRAL_TEMA` (similitud mínima para
asignar un fragmento a un tema de la retícula, 0.30 por defecto), `ADMIN_EMAIL` y `ADMIN_PASSWORD`
(credenciales del administrador inicial). Si no defines `ADMIN_EMAIL` y `ADMIN_PASSWORD`, se usan valores de ejemplo: cámbialos fuera de un
demo.

**Base de datos en la nube (Neon PostgreSQL)**

1. Entra a la consola de Neon (https://console.neon.tech/).
2. En la sección de proyectos, abre la pestaña «Shared with you» y selecciona el proyecto.
3. Haz clic en **Connect**, copia la cadena de conexión y pégala en `.env` como `DATABASE_URL`.

**Proveedor de LLM (Groq)**

1. Entra a GroqCloud (https://console.groq.com/) y abre **API Keys** en el menú izquierdo.
2. Pulsa **Create API Key** y copia la clave (empieza con `gsk_`).
3. Pégala en `.env` como `GROQ_API_KEY`.

Sin `DATABASE_URL` la app usa una base SQLite local (`local.db`).

**Si venías usando una versión anterior** (el material indexado estaba en la carpeta local `chroma_data/`), copia
ese material a la base de datos una sola vez con el entorno virtual activo:

```bash
python scripts/migrar_chroma_a_bd.py
```

Es seguro repetirlo (salta lo ya copiado) y no borra `chroma_data/`. Hazlo en **cada computadora** donde se subió
material con la versión anterior; si no, esos temas aparecen en el panel de cobertura como «Documento sin contenido
indexado» y el tutor no podrá responder con ellos.

## Parte 3 - Ejecución

Con el entorno virtual activado y el `.env` listo:

```bash
streamlit run app.py
```

La aplicación se abre en http://localhost:8501. La primera vez que subas un PDF se descarga el modelo de
embeddings (unos 200 MB).

Reinicia el servidor cada vez que cambies código de `core/`: Streamlit no siempre recarga los módulos ya
importados.

## Datos de ejemplo para un demo

```bash
python scripts/datos_demo.py            # crea un maestro y tres alumnos de ejemplo
python scripts/datos_demo.py --borrar   # elimina solo esos datos
```

Para la feria hay una demostración lista sobre la materia Metrología (maestra, administrador, cuatro alumnos y una clase
con dos semanas de actividad, tareas y avisos), con un guion de 5 minutos en [DEMO.md](DEMO.md):

```bash
python scripts/preparar_demo.py            # crea o rehace la demostración (cuentas @feci.local)
python scripts/preparar_demo.py --borrar   # elimina solo lo que creó
```

Los usuarios usan el dominio `@demo.local` y la contraseña `demo1234`: `maestro@demo.local`,
`ana@demo.local`, `beto@demo.local` y `carla@demo.local`. El script escribe en la base de `DATABASE_URL`,
así que quien comparta esa base verá los datos de ejemplo.

## Pruebas

```bash
python -m unittest discover tests
```

Las pruebas usan una base SQLite temporal y no llaman a Groq.
