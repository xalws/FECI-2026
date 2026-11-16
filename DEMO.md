# Guion de demostración (5 minutos)

Para presentar PRACTIC_APP en la feria. Todo el recorrido usa la materia **Metrología**. Sus cinco primeros temas
(Introducción, Conversión de unidades, Normatividad, Clasificación de instrumentos y Técnicas de medición) tienen
material completo; los demás temas y materias tienen todavía un solo fragmento, así que **durante la demo quédate en
esos cinco temas**.

> **Cuota de Groq:** el plan gratuito permite 200 000 tokens por día por modelo. No hagas pruebas largas con el tutor el
> día de la presentación. Si el modelo principal llega a su límite, el tutor cambia solo al modelo de respaldo
> (`GROQ_MODEL_RESPALDO`, por defecto `openai/gpt-oss-20b`, con cuota propia).

## Antes de empezar (10 minutos antes)

1. **Preparar los datos de ejemplo** (crea o rehace maestro, administrador, cuatro alumnos y una clase con dos semanas
   de actividad, tareas y avisos):

   ```bash
   python scripts/preparar_demo.py
   ```

2. **Respaldo de la base:** en *Administración → Respaldo de la base → Preparar respaldo*, o con
   `python scripts/respaldo.py`. La base la comparte todo el equipo.
3. **Arrancar la app** con el entorno virtual activo: `streamlit run app.py`. Si cambiaste algo en `core/`, reinicia el
   servidor.
4. **Dos ventanas del navegador:** una normal para la maestra y una **privada** para la alumna. «Mantener mi sesión
   iniciada» guarda la sesión por navegador, y así los dos roles no se pisan.
5. **Calentar el tutor:** entra como Ana y haz una pregunta cualquiera. La primera búsqueda carga el modelo de
   búsqueda y tarda unos segundos; después responde rápido.
6. Revisa que la clave de Groq tenga cuota (el plan gratuito tiene límite por minuto y por día).

## Cuentas de la demostración

Todas usan la contraseña `Demo-FECI-2026`.

| Rol | Correo | Para qué |
|---|---|---|
| Alumna | `ana@feci.local` | La alumna destacada: racha, logros, repaso y tareas |
| Alumno | `luis@feci.local` | El que necesita apoyo (25 % de aciertos) |
| Alumna | `sofia@feci.local` | Desempeño regular |
| Alumno | `diego@feci.local` | Lleva días sin entrar |
| Maestra | `maestro@feci.local` | Clase «Metrología · Grupo FECI», código `FECI26` |
| Administrador | `admin@feci.local` | Usuarios, errores y respaldo |

## El recorrido

**0:00 – 0:45 · Presentación.** «Un tutor que responde solo con el material que sube el maestro, practica con el alumno y le
dice al maestro a quién ayudar.» Muestra la pantalla de inicio de sesión.

**0:45 – 2:15 · La alumna (ventana privada, Ana).**
1. En *Estudio* señala el panel **Tu día**: tarjetas de repaso, reto de la semana y tareas con fecha.
2. Elige *Metrología → Fundamentos de Metrología → Conversión entre Sistemas de Unidades de Medida*.
3. Pulsa **Iniciar la lección**. El tutor explica con el material y cita el archivo y la página.
4. Pregunta: *«¿Cómo convierto 5 km a millas?»* y luego usa el atajo **Explícamelo más simple**.
5. Escribe una pregunta que el material no cubre (por ejemplo, *«¿Quién ganó el mundial?»*). El tutor lo dice y no inventa:
   es la característica clave.

**2:15 – 3:15 · Examen y repaso.**
1. Pestaña **Examen → Comenzar examen** (3 preguntas). Muestra que la dificultad sube si acierta y baja si falla, y la
   explicación después de cada pregunta.
2. Abre **Repaso** en el menú: las preguntas falladas vuelven como tarjetas con espaciado.

**3:15 – 4:15 · Progreso y motivación.**
*Mi progreso* (racha, calendario de estudio con las fechas de tareas, qué estudiar ahora), *Mi perfil* (logros) y el
ranking de la clase en *Mis clases*.

**4:15 – 5:00 · La maestra (ventana normal, `maestro@feci.local`).**
1. *Clases → Boletín:* **A quién buscar** (Luis con 25 %, Diego sin actividad), **temas con más errores** y **falta
   material** (la pregunta que el tutor no pudo contestar sobre tolerancias).
2. Descarga el **Texto para enviar** o el Excel.
3. *Clases → Tareas* y *Estadísticas*, si queda tiempo.

**Cierre.** El administrador ve *Errores* y *Respaldo*: la app registra sus propios fallos, sin contraseñas, y tiene
copia de seguridad.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| «El tutor está atendiendo muchas consultas» | Se acabó la cuota de Groq (por minuto o por día) en los dos modelos. Espera medio minuto y pulsa **Reintentar**; si es la cuota diaria, hasta mañana. En *Administración → Errores* se ve el motivo exacto. |
| «No se logró generar una pregunta confiable» | El generador verifica cada pregunta y a veces la rechaza. Pulsa **Reintentar**. |
| «No tengo información sobre eso…» | La pregunta no está en el material del tema. Es lo esperado: usa las preguntas sugeridas de abajo. |
| Un correo queda bloqueado por intentos | Espera 15 minutos o ejecuta `python -c "from core import seguridad; seguridad.limpiar('correo@feci.local')"`. |
| Datos raros o cambiados | Repite `python scripts/preparar_demo.py`. |

## Preguntas que el tutor contesta bien (Metrología)

Se probaron con el material cargado; sirven si el público pide ejemplos.

- *Conversión entre sistemas de unidades:* «¿Cómo convierto 5 km a millas?».
- *Introducción a la Metrología:* «¿Qué es la trazabilidad?».
- *Técnicas de medición dimensional:* «¿Cómo mido el diámetro exterior de un eje con un calibrador vernier?».

El tutor solo responde con lo que dice el material. Si preguntas algo que no está (por ejemplo, la conversión de psi a
pascales, que solo aparece en un ejemplo que la búsqueda no siempre trae), contesta «No tengo información…».

## Al terminar

```bash
python scripts/preparar_demo.py --borrar   # elimina solo las cuentas y datos de la demostración
```

No toca las cuentas `@demo.local` ni el resto de la base.
