"""Repaso espaciado: las preguntas que fallaste vuelven a aparecer cada vez más separadas hasta que las dominas."""
import streamlit as st

from core import repaso
from core.auth import require_login
from core.estilo import datos, encabezado, fecha_local, svg

user = require_login(["alumno"])
ss = st.session_state
LETRAS = "ABCD"

res = repaso.resumen(user["id"])
encabezado("Repaso", "Las preguntas que fallaste vuelven cada vez más espaciadas hasta que las dominas.", "refresh",
           chips=[("clock", f"{res['hoy']} por repasar hoy"), ("check", f"{res['dominadas']} dominadas")])
datos([{"icono": "refresh", "etiqueta": "Por repasar hoy", "valor": res["hoy"], "detalle": "tarjetas que te tocan",
        "tono": "ambar" if res["hoy"] else "verde"},
       {"icono": "layers", "etiqueta": "En repaso", "valor": res["en_repaso"], "detalle": "preguntas que aún practicas",
        "tono": "indigo"},
       {"icono": "award", "etiqueta": "Dominadas", "valor": res["dominadas"], "detalle": "acertadas en las 4 cajas",
        "tono": "verde"}])
with st.expander("¿Cómo funciona?"):
    st.markdown(
        "- Cada pregunta que fallas en un examen se vuelve una **tarjeta** y te toca verla al día siguiente.\n"
        "- Si la aciertas, vuelve en **3 días**, luego en **7** y luego en **14**; después queda **dominada**.\n"
        "- Si la fallas, regresa al principio y la ves mañana.\n"
        "- Repasar tarjetas no suma XP: sirve para que de verdad se te quede.")

sesion = ss.get("repaso")  # {"cola": [ids], "total", "ok", "vistas", "resultado": None | dict, "fin": bool}

# ----- Sin tanda en curso -----
if sesion is None:
    if not res["hoy"]:
        if res["en_repaso"]:
            st.success("¡Al día! No tienes tarjetas por repasar hoy.", icon=":material/check_circle:")
            if res["proxima"]:
                st.caption(f"La próxima te toca el {fecha_local(res['proxima']):%d/%m/%Y}.")
        else:
            st.info("Aún no tienes tarjetas. Cuando falles una pregunta en un examen, aparecerá aquí para repasarla.",
                    icon=":material/inbox:")
    elif st.button(f"Empezar el repaso ({res['hoy']})", type="primary", icon=":material/play_arrow:"):
        ids = [t["id"] for t in repaso.pendientes(user["id"])]
        ss["repaso"] = {"cola": ids, "total": len(ids), "ok": 0, "vistas": 0, "resultado": None, "fin": False}
        st.rerun()
    st.stop()

# ----- Terminó la tanda -----
if sesion["fin"]:
    st.success(f"Terminaste el repaso: acertaste {sesion['ok']} de {sesion['vistas']}.", icon=":material/emoji_events:")
    if st.button("Listo", type="primary", icon=":material/check:"):
        ss.pop("repaso")
        st.rerun()
    st.stop()

# ----- Una tarjeta a la vez -----
resultado = sesion["resultado"]
t = repaso.detalle(user["id"], sesion["cola"][0])
if t is None:  # la tarjeta ya no existe: se salta
    sesion["cola"].pop(0)
    sesion["fin"] = not sesion["cola"]
    st.rerun()
hechas = sesion["total"] - len(sesion["cola"]) + (1 if resultado else 0)
st.progress(hechas / max(1, sesion["total"]),
            text=f"Tarjeta {min(sesion['total'], sesion['total'] - len(sesion['cola']) + 1)} de {sesion['total']}")
with st.container(border=True):
    st.caption(f"{t['tema']} · caja {t['caja'] + 1} de {repaso.DOMINADA}")
    st.markdown(f"**{t['pregunta']}**")
    if resultado is None:
        eleccion = st.radio("Elige tu respuesta", range(len(t["opciones"])), index=None, key=f"rep_{t['id']}",
                            format_func=lambda i: f"{LETRAS[i]}) {t['opciones'][i]}", label_visibility="collapsed")
        if st.button("Responder", type="primary", disabled=eleccion is None, icon=":material/check:"):
            r = repaso.responder(user["id"], t["id"], eleccion)
            sesion["vistas"] += 1
            sesion["ok"] += 1 if r and r["correcta"] else 0
            sesion["resultado"] = {"eleccion": eleccion, **(r or {"correcta": False, "indice_correcto": -1,
                                                                  "explicacion": "", "dominada": False, "proxima": None})}
            st.rerun()
    else:
        for i, op in enumerate(t["opciones"]):
            estado = "ok" if i == resultado["indice_correcto"] else ("mal" if i == resultado["eleccion"] else "neutro")
            color = {"ok": "#059669", "mal": "#DC2626"}.get(estado, "#94A3B8")
            icono = {"ok": "check", "mal": "x"}.get(estado, "circle")
            st.markdown(f'<span style="display:inline-flex;vertical-align:-3px;margin-right:6px">{svg(icono, 18, color, 2.2)}</span>'
                        f"**{LETRAS[i]})** {op}", unsafe_allow_html=True)
        cuando = f"{fecha_local(resultado['proxima']):%d/%m}" if resultado.get("proxima") else ""
        if resultado["correcta"]:
            st.success("¡Correcto! " + ("Esta pregunta ya está dominada." if resultado["dominada"]
                                        else f"Volverás a verla el {cuando}."), icon=":material/check_circle:")
        else:
            st.error(f"Esta vez no. La verás de nuevo el {cuando}.", icon=":material/refresh:")
        if resultado["explicacion"]:
            st.caption(resultado["explicacion"])
        if st.button("Siguiente" if len(sesion["cola"]) > 1 else "Terminar", type="primary", icon=":material/arrow_forward:"):
            sesion["cola"].pop(0)
            sesion["resultado"] = None
            sesion["fin"] = not sesion["cola"]
            st.rerun()
