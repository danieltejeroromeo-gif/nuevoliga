import streamlit as st
import pandas as pd
import json
import random
import copy

# ============================================================================
# CLUBES VINCULADOS / FILIALES / SUB-19
# ============================================================================

MAPEO_CLUBES_VINCULADOS = {
    # Aquí solo van excepciones manuales si algún nombre no sigue el patrón normal
    # Ejemplo:
    # "Academia CEREZAS": "CEREZAS",
}

SUFIJOS_CLUB_VINCULADO = [
    " B",
    " C",
    " Sub-19",
    " Sub 19",
    " Sub-18",
    " Sub 18",
    " Sub-21",
    " Sub 21",
    " U19",
    " U-19",
    " U18",
    " U-18",
    " U21",
    " U-21",
    " Academy",
]


def normalizar_nombre_club_base(nombre):
    base = str(nombre).strip()

    if base in MAPEO_CLUBES_VINCULADOS:
        return MAPEO_CLUBES_VINCULADOS[base]

    cambiado = True
    while cambiado:
        cambiado = False
        for sufijo in SUFIJOS_CLUB_VINCULADO:
            if base.endswith(sufijo):
                base = base[:-len(sufijo)].strip()
                cambiado = True
                break

    return base


def obtener_club_principal(equipo):
    return normalizar_nombre_club_base(equipo)


def son_clubes_vinculados(equipo_a, equipo_b):
    return obtener_club_principal(equipo_a) == obtener_club_principal(equipo_b)


def es_equipo_vinculado(equipo):
    return obtener_club_principal(equipo) != str(equipo).strip()


def es_mismo_grupo_club(equipo_a, equipo_b):
    return son_clubes_vinculados(equipo_a, equipo_b)

def obtener_liga_data(nombre_liga):
    return st.session_state.db["ligas"][nombre_liga]

def obtener_equipo_data(equipo):
    return st.session_state.db["equipos_data"][equipo]

def es_equipo_sub19(equipo):
    liga = st.session_state.db["equipos_data"].get(equipo, {}).get("liga", "")
    return "Sub-19" in str(liga) or "Sub 19" in str(liga) or "Sub-19" in str(equipo) or "Sub 19" in str(equipo)

def obtener_equipo_pagador(equipo):
    if es_equipo_sub19(equipo):
        return obtener_club_principal(equipo)
    return equipo

def obtener_presupuesto_equipo(equipo):
    db = st.session_state.db
    equipo_real = obtener_equipo_pagador(equipo)
    return float(db["equipos_data"].get(equipo_real, {}).get("presupuesto", 0))

def sumar_presupuesto_equipo(equipo, cantidad):
    db = st.session_state.db
    equipo_real = obtener_equipo_pagador(equipo)
    db["equipos_data"].setdefault(equipo_real, {})
    db["equipos_data"][equipo_real]["presupuesto"] = round(
        float(db["equipos_data"][equipo_real].get("presupuesto", 0)) + float(cantidad), 1
    )

def restar_presupuesto_equipo(equipo, cantidad):
    db = st.session_state.db
    equipo_real = obtener_equipo_pagador(equipo)
    db["equipos_data"].setdefault(equipo_real, {})
    actual = float(db["equipos_data"][equipo_real].get("presupuesto", 0))
    db["equipos_data"][equipo_real]["presupuesto"] = round(max(0, actual - float(cantidad)), 1)

def obtener_filial_b_del_club(club_base):
    db = st.session_state.db
    candidatos = [
        f"{club_base} B",
        f"{club_base} C",
    ]
    for eq in candidatos:
        if eq in db["equipos_data"]:
            return eq
    return None

def obtener_siguiente_equipo_por_edad(equipo_actual):
    club_base = obtener_club_principal(equipo_actual)

    if es_equipo_sub19(equipo_actual):
        filial = obtener_filial_b_del_club(club_base)
        if filial and filial in st.session_state.db["equipos_data"]:
            return filial
        if club_base in st.session_state.db["equipos_data"]:
            return club_base
        return None

    return None

def es_equipo_principal(equipo):
    return not es_equipo_vinculado(equipo)

def obtener_equipos_vinculados_del_club(club_principal):
    db = st.session_state.db
    res = []

    for eq in db["equipos_data"].keys():
        if eq == club_principal:
            continue
        if obtener_club_principal(eq) == club_principal:
            res.append(eq)

    return res

def contar_jugadores_primer_equipo(club_principal):
    db = st.session_state.db
    return len(db["equipos_data"][club_principal]["jugadores"])


def obtener_jugadores_con_ficha_primer_equipo(club_principal):
    db = st.session_state.db
    jugadores = []

    for eq in obtener_equipos_vinculados_del_club(club_principal):
        for j in db["equipos_data"][eq]["jugadores"]:
            if j.get("ficha_primer_equipo", False) and j.get("primer_equipo_asignado") == club_principal:
                jugadores.append(j)

    return jugadores


def contar_total_disponibles_primer_equipo(club_principal):
    permanentes = contar_jugadores_primer_equipo(club_principal)
    con_ficha = len(obtener_jugadores_con_ficha_primer_equipo(club_principal))
    return permanentes + con_ficha


def contar_total_efectivos_primer_equipo(club_principal):
    return contar_total_disponibles_primer_equipo(club_principal)


def puede_promocionar_a_primer_equipo(club_principal):
    return contar_jugadores_primer_equipo(club_principal) < 7


def necesita_fichas_para_convocatoria(club_principal, jornada_actual=None):
    db = st.session_state.db

    propios = []
    for j in db["equipos_data"][club_principal]["jugadores"]:
        if j.get("lesion_jornadas", 0) == 0 and not jugador_ya_jugo_en_jornada(j, jornada_actual):
            propios.append(j)

    disponibles_totales = obtener_plantilla_disponible_partido(club_principal, jornada_actual)
    disponibles_sanos = [j for j in disponibles_totales if j.get("lesion_jornadas", 0) == 0]

    return len(disponibles_sanos) < 8 and len(propios) < 7


def puede_dar_ficha_primer_equipo(club_principal):
    return contar_total_efectivos_primer_equipo(club_principal) < 10


def contar_jugadores_filial(equipo_filial):
    db = st.session_state.db
    return len(db["equipos_data"][equipo_filial]["jugadores"])


def contar_total_disponibles_filial(equipo_filial):
    propios = contar_jugadores_filial(equipo_filial)
    con_ficha = len(obtener_jugadores_con_ficha_filial(equipo_filial))
    return propios + con_ficha


def contar_total_efectivos_filial(equipo_filial):
    return contar_total_disponibles_filial(equipo_filial)


def puede_dar_ficha_filial(equipo_filial):
    return contar_total_efectivos_filial(equipo_filial) < 10


def dar_ficha_filial(jugador_nombre, equipo_origen, equipo_filial):
    db = st.session_state.db

    if equipo_filial not in db["equipos_data"] or equipo_origen not in db["equipos_data"]:
        return False, "Equipo no válido."

    if not (equipo_filial.endswith(" B") or equipo_filial.endswith(" C")):
        return False, "La ficha filial solo se puede asignar a un filial."

    if obtener_club_principal(equipo_origen) != obtener_club_principal(equipo_filial):
        return False, "Solo puedes dar ficha filial a jugadores del mismo club."

    if not es_equipo_sub19(equipo_origen):
        return False, "La ficha filial debe venir desde el Sub-19."

    if not puede_dar_ficha_filial(equipo_filial):
        return False, f"{equipo_filial} ya tiene 10 jugadores efectivos."

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado."

    if jugador.get("cedido", False):
        return False, "No puedes dar ficha filial a un jugador cedido."

    if jugador.get("ficha_filial", False) and jugador.get("filial_asignado") == equipo_filial:
        return False, "Ese jugador ya tiene ficha del filial."

    jugador["equipo_base"] = equipo_origen
    jugador["ficha_filial"] = True
    jugador["filial_asignado"] = equipo_filial
    jugador["bloqueado_filial_sub19"] = False

    db["mercado_log"].append(
        f"🪪 Ficha filial: {jugador_nombre} queda inscrito con {equipo_filial} pero sigue en {equipo_origen}"
    )

    return True, "Ficha filial asignada."

def jugador_ya_jugo_en_jornada(jugador, jornada_actual):
    if jornada_actual is None:
        return False
    return jugador.get("ultima_jornada_jugada") == jornada_actual


def marcar_jugadores_como_usados_en_jornada(jugadores, jornada_actual):
    if jornada_actual is None:
        return

    vistos = set()
    for j in jugadores:
        nombre = j.get("nombre")
        if not nombre or nombre in vistos:
            continue
        j["ultima_jornada_jugada"] = jornada_actual
        vistos.add(nombre)


def obtener_jugadores_con_ficha_filial(equipo_filial):
    db = st.session_state.db
    jugadores = []

    for eq, edata in db["equipos_data"].items():
        if eq == equipo_filial:
            continue
        if obtener_club_principal(eq) != obtener_club_principal(equipo_filial):
            continue

        for j in edata["jugadores"]:
            if j.get("ficha_filial", False) and j.get("filial_asignado") == equipo_filial:
                jugadores.append(j)

    return jugadores


def obtener_plantilla_disponible_partido(equipo, jornada_actual=None):
    db = st.session_state.db
    plantilla = list(db["equipos_data"][equipo]["jugadores"])

    if es_equipo_principal(equipo):
        for j in obtener_jugadores_con_ficha_primer_equipo(equipo):
            if jugador_ya_jugo_en_jornada(j, jornada_actual):
                continue
            plantilla.append(j)

    elif equipo.endswith(" B") or equipo.endswith(" C"):
        for j in obtener_jugadores_con_ficha_filial(equipo):
            if jugador_ya_jugo_en_jornada(j, jornada_actual):
                continue
            plantilla.append(j)

    plantilla_filtrada = []

    for j in plantilla:
        ya_jugo = jugador_ya_jugo_en_jornada(j, jornada_actual)

        puede_jugar_aqui = (
            j.get("equipo_actual") == equipo
            or (j.get("ficha_primer_equipo", False) and j.get("primer_equipo_asignado") == equipo)
            or (j.get("ficha_filial", False) and j.get("filial_asignado") == equipo)
        )

        if not puede_jugar_aqui:
            continue

        if ya_jugo:
            equipo_de_hoy = equipo_en_el_que_juega_hoy(j, equipo)
            if equipo_de_hoy != equipo:
                continue

        plantilla_filtrada.append(j)

    vistos = set()
    plantilla_final = []

    for j in plantilla_filtrada:
        nombre = j.get("nombre")
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        plantilla_final.append(j)

    return plantilla_final

def equipo_en_el_que_juega_hoy(jugador, equipo_convocante):
    if jugador.get("equipo_actual") == equipo_convocante:
        return equipo_convocante

    if jugador.get("ficha_primer_equipo", False) and jugador.get("primer_equipo_asignado") == equipo_convocante:
        return equipo_convocante

    if jugador.get("ficha_filial", False) and jugador.get("filial_asignado") == equipo_convocante:
        return equipo_convocante

    return jugador.get("equipo_actual", equipo_convocante)

def avanzar_control_porteros_liga(nombre_liga):
    db = st.session_state.db
    equipos = db["ligas"][nombre_liga]["equipos"]

    for eq in equipos:
        db["equipos_data"][eq]["control_jornada_porteros"] = int(
            db["equipos_data"][eq].get("control_jornada_porteros", 0)
        ) + 1

        if contar_porteros(eq) >= 2:
            limpiar_alerta_porteria_si_corresponde(eq)


def equipos_incumpliendo_porteria(nombre_liga):
    db = st.session_state.db
    incumplen = []

    for eq in db["ligas"][nombre_liga]["equipos"]:
        if equipo_necesita_regularizar_porteria(eq):
            incumplen.append(eq)

    return incumplen


def intentar_regularizar_porteria_desde_cantera(equipo):
    db = st.session_state.db

    if contar_porteros(equipo) >= 2:
        limpiar_alerta_porteria_si_corresponde(equipo)
        return True, None

    club_base = obtener_club_principal(equipo)
    candidatos = []

    if es_equipo_principal(equipo):
        for eq_vinc in [f"{club_base} B", f"{club_base} C"]:
            if eq_vinc in db["equipos_data"]:
                for j in db["equipos_data"][eq_vinc]["jugadores"]:
                    if j.get("pos") == "POR" and not j.get("cedido", False):
                        candidatos.append((eq_vinc, j))

        if not candidatos:
            for eq_vinc in obtener_equipos_vinculados_del_club(club_base):
                if es_equipo_sub19(eq_vinc):
                    for j in db["equipos_data"][eq_vinc]["jugadores"]:
                        if j.get("pos") == "POR" and not j.get("cedido", False):
                            candidatos.append((eq_vinc, j))

    elif equipo.endswith(" B") or equipo.endswith(" C"):
        for eq_vinc in obtener_equipos_vinculados_del_club(club_base):
            if es_equipo_sub19(eq_vinc):
                for j in db["equipos_data"][eq_vinc]["jugadores"]:
                    if j.get("pos") == "POR" and not j.get("cedido", False):
                        candidatos.append((eq_vinc, j))

    if candidatos:
        eq_origen, portero = sorted(
            candidatos,
            key=lambda x: x[1].get("media", 0),
            reverse=True
        )[0]

        ok, msg = ascender_portero_entre_vinculados(portero["nombre"], eq_origen, equipo)
        if ok:
            limpiar_alerta_porteria_si_corresponde(equipo)
            return True, msg

    return False, f"{equipo} sigue con solo 1 portero y debe fichar o promocionar otro."


def gestion_cantera_ia(jornada_actual=None):
    db = st.session_state.db
    movimientos = []

    clubes_usuario = {
    "CEREZAS",
    "RB Zerkas",
    "EKIPO",
}

    for club in list(db["equipos_data"].keys()):
        if not es_equipo_principal(club):
            continue

        if obtener_club_principal(club) in clubes_usuario:
            continue

        vinculados = obtener_equipos_vinculados_del_club(club)
        puede_subir = puede_promocionar_a_primer_equipo(club)
        puede_ficha = puede_dar_ficha_primer_equipo(club)

        plantilla_primer = db["equipos_data"][club]["jugadores"]
        num_porteros = sum(1 for j in plantilla_primer if j.get("pos") == "POR")

        media_general = media_plantilla(club)
        media_porteros = media_plantilla(club, "POR")

        candidatos = []

        for eq_vinc in vinculados:
            prioridad_base = 0
            if eq_vinc.endswith(" B"):
                prioridad_base = 3
            elif eq_vinc.endswith(" C"):
                prioridad_base = 2
            elif es_equipo_sub19(eq_vinc):
                prioridad_base = 1

            for j in db["equipos_data"][eq_vinc]["jugadores"]:
                if j.get("cedido", False):
                    continue
                if j.get("promocion_temporal", False):
                    continue

                pos = j.get("pos", "JUG")
                media = j.get("media", 0)
                edad = j.get("edad", 19)

                if pos == "POR":
                    mejora = media - media_porteros if media_porteros else media - media_general
                else:
                    mejora = media - media_general

                score = media + prioridad_base
                if edad <= 20:
                    score += 0.5

                candidatos.append({
                    "jugador": j,
                    "origen": eq_vinc,
                    "score": score,
                    "mejora": mejora,
                    "pos": pos,
                    "ya_tiene_ficha": j.get("ficha_primer_equipo", False),
                })

        # PRIORIDAD: si hay solo 1 portero, dar BONUS a los porteros
        if num_porteros == 1:
            for c in candidatos:
                if c["pos"] == "POR":
                    c["score"] += 5  # bonus fuerte para priorizar porteros

        candidatos = sorted(candidatos, key=lambda x: x["score"], reverse=True)

        # 1) Si hay solo 1 portero, intentar subir/promocionar un portero primero
        if num_porteros == 1 and puede_subir:
            candidatos_por = [c for c in candidatos if c["pos"] == "POR"]
            if candidatos_por:
                c = candidatos_por[0]
                ok, msg = promocionar_a_primer_equipo(c["jugador"]["nombre"], c["origen"], club)
                if ok:
                    movimientos.append(f"🤖 {club} promociona a {c['jugador']['nombre']} desde {c['origen']} por necesidad en portería")
                    continue

        # 2) Bucle de fichas blindado con nueva regla de efectivos
        # Jornada 1: máximo 8 efectivos
        # Después: máximo 7 permanentes (pueden tener +2 subidos temporalmente = 9 en total)
        if jornada_actual == 1:
            max_efectivos = 8
        else:
            max_efectivos = 7  # permanentes; los 2 extra vienen por promociones temporales

        while (
            puede_ficha
            and necesita_fichas_para_convocatoria(club, jornada_actual)
            and contar_total_efectivos_primer_equipo(club) < max_efectivos
        ):
            # Si hay solo 1 portero, priorizar fichar/promocionar un portero
            if num_porteros == 1:
                candidatos_ficha = [
                    c for c in candidatos
                    if not c["ya_tiene_ficha"] and c["pos"] == "POR"
                ]
                # Si no hay porteros, dejar que ficha a cualquiera
                if not candidatos_ficha:
                    candidatos_ficha = [
                        c for c in candidatos
                        if not c["ya_tiene_ficha"]
                    ]
            else:
                candidatos_ficha = [
                    c for c in candidatos
                    if not c["ya_tiene_ficha"] and c["pos"] != "POR"
                ]
                if not candidatos_ficha:
                    candidatos_ficha = [
                        c for c in candidatos
                        if not c["ya_tiene_ficha"]
                    ]

            if not candidatos_ficha:
                break

            c = candidatos_ficha[0]

            ok, msg = dar_ficha_primer_equipo(c["jugador"]["nombre"], c["origen"], club)
            if not ok:
                break

            movimientos.append(f"🤖 {club} da ficha a {c['jugador']['nombre']} ({c['origen']}) para completar convocatoria")
            c["ya_tiene_ficha"] = True

            # Actualizamos el estado tras cada ficha
            puede_ficha = puede_dar_ficha_primer_equipo(club)
            # Recalcular num_porteros tras cada movimiento
            num_porteros = sum(1 for j in db["equipos_data"][club]["jugadores"] if j.get("pos") == "POR")

    if movimientos:
        db["mercado_log"].extend(movimientos)

    return movimientos

def promocion_automatica_por_media():
    """
    Sube permanentemente:
    - Del Sub-19 al filial (B/C) si tiene más media que la media del filial
    - Del filial/Sub-19 al primer equipo si tiene más media que la media del primer equipo
    
    NO se aplica a CEREZAS ni RB Zerkas (clubes del usuario).
    """
    db = st.session_state.db
    movimientos = []

    # Clubs gestionados manualmente: sin promociones automáticas
    clubes_usuario = {"CEREZAS", "RB Zerkas","EKIPO"}

    for club in list(db["equipos_data"].keys()):
        if not es_equipo_principal(club):
            continue

        # Saltar clubes del usuario
        if obtener_club_principal(club) in clubes_usuario:
            continue

        vinculados = obtener_equipos_vinculados_del_club(club)
        if not vinculados:
            continue

        # Separar filiales (B/C) y Sub-19
        filiales = [
            eq for eq in vinculados
            if eq.endswith(" B") or eq.endswith(" C")
        ]
        sub19 = [
            eq for eq in vinculados
            if es_equipo_sub19(eq)
        ]

        if not filiales and not sub19:
            continue

        # ─────────────────────────────────────────────────────
        # 1) Subir del Sub-19 al filial (si existe filial)
        # ─────────────────────────────────────────────────────
        if filiales and sub19:
            for filial in filiales:
                plantilla_filial = db["equipos_data"][filial]["jugadores"]
                if not plantilla_filial:
                    continue

                media_filial = (
                    sum(j.get("media", 0) for j in plantilla_filial)
                    / len(plantilla_filial)
                )

                for eq_s19 in sub19:
                    for j in db["equipos_data"][eq_s19]["jugadores"]:
                        if j.get("cedido", False):
                            continue
                        if j.get("edad", 0) > 19:
                            continue  # Solo menores de 20 al filial

                        # Si tiene más media que la del filial, subirlo
                        if j.get("media", 0) > media_filial:
                            # Comprobar si hay hueco en el filial (máx 8)
                            if len(plantilla_filial) < 8:
                                # Mover del Sub-19 al filial
                                db["equipos_data"][eq_s19]["jugadores"].remove(j)
                                db["equipos_data"][filial]["jugadores"].append(j)

                                j["equipo_actual"] = filial
                                j["propietario"] = filial
                                j["equipo_base"] = filial
                                j["promocion_temporal"] = False
                                j["bloqueado_filial_sub19"] = False
                                j["ficha_primer_equipo"] = False
                                j["primer_equipo_asignado"] = None
                                j["ficha_filial"] = False
                                j["filial_asignado"] = None

                                abrir_tramo_temporada(
                                    j, filial, "promoción automática a filial"
                                )

                                registrar_traspaso(
                                    j,
                                    eq_s19,
                                    filial,
                                    tipo="promoción automática a filial",
                                    temporada=db["config"]["temporada"],
                                    valor=0,
                                )

                                movimientos.append(
                                    f"🔼 {filial} promociona automáticamente a {j['nombre']} "
                                    f"({eq_s19}, {j['media']} > {media_filial:.1f})"
                                )

        # ─────────────────────────────────────────────────────
        # 2) Subir del filial/Sub-19 al primer equipo
        # ─────────────────────────────────────────────────────
        plantilla_primer = db["equipos_data"][club]["jugadores"]
        if plantilla_primer:
            media_primer = (
                sum(j.get("media", 0) for j in plantilla_primer)
                / len(plantilla_primer)
            )

            # Mirar en filiales y Sub-19
            candidatos = []
            for eq_vinc in vinculados:
                for j in db["equipos_data"][eq_vinc]["jugadores"]:
                    if j.get("cedido", False):
                        continue
                    if j.get("promocion_temporal", False):
                        continue
                    if j.get("ficha_primer_equipo", False):
                        continue

                    # Si tiene más media que la del primer equipo, es candidato
                    if j.get("media", 0) > media_primer:
                        candidatos.append((j, eq_vinc))

            # Subir candidatos si hay hueco (máx 7 permanentes)
            for j, eq_vinc in candidatos:
                promocionados_actuales = [
                    jugador
                    for jugador in db["equipos_data"][club]["jugadores"]
                    if jugador.get("promocion_temporal", False)
                ]

                if len(promocionados_actuales) >= 7:
                    ok_libera, msg_libera = liberar_plaza_promocionado(club)

                    if not ok_libera:
                        movimientos.append(
                            f"⚠️ {club} no puede promocionar a {j['nombre']}: "
                            f"no se pudo liberar una plaza."
                        )
                        continue

                    movimientos.append(msg_libera)

                ok, msg = promocionar_a_primer_equipo(
                    j["nombre"],
                    eq_vinc,
                    club
                )
                if ok:
                    movimientos.append(
                        f"🔼 {club} promociona automáticamente a {j['nombre']} "
                        f"({eq_vinc}, {j['media']} > {media_primer:.1f})"
                    )

    if movimientos:
        db["mercado_log"].extend(movimientos)

    return movimientos

def completar_convocatoria_ia(
    club_principal,
    jornada_actual=None
):
    db = st.session_state.db

    # Solo aplica a primeros equipos
    if not es_equipo_principal(club_principal):
        return []

    # Clubs gestionados manualmente: sin IA de convocatorias
    if obtener_club_principal(club_principal) in {"CEREZAS", "RB Zerkas", "EKIPO"}:
        return []

    movimientos = []

    while True:
        # Tope de efectivos disponibles en el primer equipo
        total_disponibles = contar_total_disponibles_primer_equipo(club_principal)
        if total_disponibles >= 10:
            break

        # Jugadores disponibles para este partido
        disponibles = obtener_plantilla_disponible_partido(
            club_principal,
            jornada_actual
        )
        disponibles_sanos = [
            j for j in disponibles
            if j.get("lesion_jornadas", 0) == 0
        ]

        # Si ya hay 8 sanos, no hace falta subir más
        if len(disponibles_sanos) >= 8:
            break

        # Si el club ya no puede dar más fichas de primer equipo, parar
        if not puede_dar_ficha_primer_equipo(club_principal):
            break

        # Recoger candidatos de filiales y Sub-19
        vinculados = obtener_equipos_vinculados_del_club(club_principal)
        candidatos = []

        for eq_vinc in vinculados:
            # Prioridad según categoría
            prioridad_base = 0
            if eq_vinc.endswith(" B"):
                prioridad_base = 3
            elif eq_vinc.endswith(" C"):
                prioridad_base = 2
            elif es_equipo_sub19(eq_vinc):
                prioridad_base = 1

            for j in db["equipos_data"][eq_vinc]["jugadores"]:
                # Ignorar cedidos, lesionados o que ya tengan ficha en este primer equipo
                if j.get("cedido", False):
                    continue
                if j.get("lesion_jornadas", 0) > 0:
                    continue
                if (
                    j.get("ficha_primer_equipo", False)
                    and j.get("primer_equipo_asignado") == club_principal
                ):
                    continue

                # Puntuación: media + prioridad + bonificación joven - penalización portero
                score = j.get("media", 0) + prioridad_base
                if j.get("edad", 19) <= 20:
                    score += 0.5
                if j.get("pos") == "POR":
                    score -= 0.5

                candidatos.append((score, eq_vinc, j))

        if not candidatos:
            break

        # Elegir al mejor candidato
        candidatos.sort(key=lambda x: x[0], reverse=True)
        _, eq_origen, jugador = candidatos[0]

        # Intentar darle ficha de primer equipo
        ok, msg = dar_ficha_primer_equipo(
            jugador["nombre"],
            eq_origen,
            club_principal
        )
        if not ok:
            break

        movimientos.append(
            f"🤖 {club_principal} da ficha a {jugador['nombre']} "
            f"({eq_origen}) para completar convocatoria"
        )

    if movimientos:
        db["mercado_log"].extend(movimientos)

    return movimientos


def completar_convocatoria_filial_ia(
    equipo_filial,
    jornada_actual=None
):
    if equipo_filial == "RB Zerkas B":
        return []

    db = st.session_state.db

    if not (equipo_filial.endswith(" B") or equipo_filial.endswith(" C")):
        return []

    movimientos = []

    while True:
        total_disponibles = contar_total_disponibles_filial(equipo_filial)
        if total_disponibles >= 10:
            break

        disponibles = obtener_plantilla_disponible_partido(
            equipo_filial,
            jornada_actual
        )
        disponibles_sanos = [
            j for j in disponibles
            if j.get("lesion_jornadas", 0) == 0
        ]

        if len(disponibles_sanos) >= 8:
            break

        if not puede_dar_ficha_filial(equipo_filial):
            break

        club_base = obtener_club_principal(equipo_filial)
        sub19 = None

        for eq in db["equipos_data"].keys():
            if (
                obtener_club_principal(eq) == club_base
                and es_equipo_sub19(eq)
            ):
                sub19 = eq
                break

        if not sub19:
            break

        candidatos = []

        for j in db["equipos_data"][sub19]["jugadores"]:
            if j.get("cedido", False):
                continue
            if j.get("lesion_jornadas", 0) > 0:
                continue
            if (
                j.get("ficha_filial", False)
                and j.get("filial_asignado") == equipo_filial
            ):
                continue

            score = j.get("media", 0)
            if j.get("edad", 19) <= 18:
                score += 0.5
            if j.get("pos") == "POR":
                score -= 0.5

            candidatos.append((score, j))

        if not candidatos:
            break

        candidatos.sort(key=lambda x: x[0], reverse=True)
        _, jugador = candidatos[0]

        ok, msg = dar_ficha_filial(
            jugador["nombre"],
            sub19,
            equipo_filial
        )
        if not ok:
            break

        movimientos.append(
            f"🤖 {equipo_filial} da ficha filial a {jugador['nombre']} "
            f"desde {sub19} para completar convocatoria"
        )

    if movimientos:
        db["mercado_log"].extend(movimientos)

    return movimientos

def asegurar_convocatoria_partido(eq1, eq2, jornada_actual=None):
    movimientos = []

    # Clubs que gestionamos manualmente (no se les aplica la IA de convocatorias)
    clubes_usuario = {"CEREZAS", "RB Zerkas", "EKIPO"}

    for eq in [eq1, eq2]:
        if obtener_club_principal(eq) in clubes_usuario:
            continue

        if es_equipo_principal(eq):
            movimientos.extend(completar_convocatoria_ia(eq, jornada_actual))
        elif eq.endswith(" B") or eq.endswith(" C"):
            movimientos.extend(completar_convocatoria_filial_ia(eq, jornada_actual))

    return movimientos
# ============================================================================
# 1. DATOS INICIALES
# ============================================================================

DATOS_INICIALES = {
    "config": {"liga_activa": "1ª División", "temporada": 1},
    "historial_campeones": [],
    "historial_traspasos": [],
    "mercado_log": [],
    "movimientos_presupuesto": [],
    "historial_retiradas": [],
    "ofertas_pendientes": [],
    "historial_playoff": [],
    "playoff_2a": {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    },
    "playoff_3a_grupo_a": {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    },
    "playoff_3a_grupo_b": {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    },
    "playoff_sub19_2a": {
    "activo": False,
    "equipos": [],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "ganadores_semis": []
},
"playoff_sub19_3agrupoa": {
    "activo": False,
    "equipos": [],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "ganadores_semis": []
},
"playoff_sub19_3agrupob": {
    "activo": False,
    "equipos": [],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "ganadores_semis": []
},
    "ligas": {
        "1ª División": {
            "equipos": [
                "CEREZAS", "DECERÓN", "LONESTO", "KINGZ", "MAMBO", "QUÍTER",
                "BENSARO", "SIROL", "ANTINO", "MELOP", "RUPER", "ALLSURA",
                "ENERTO", "TREO", "DOMELÍ", "DORRO", "ASORPA", "SABADERO",
                "COCONUT", "CHIMICHANGA"
            ],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "historial_clubes": {}
        },
        "2ª División": {
            "equipos": [
                "IGLESIA", "POK", "SIBERIA", "SALMÓN", "ALTORPO", "FROSTÉ",
                "FEBRONTO", "ABDUZCAN", "ANCO", "ZOQUIO", "AGUEST", "ALFALFA",
                "DENTOR", "JOREVOS", "AMPRO", "MERSOL", "NÁCOR", "XEMAR"
            ],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "historial_clubes": {}
        },
        "3ª División Grupo A": {
            "equipos": [
                "LOCKE", "MARTERO", "SCAR", "FOL", "BLOX", "VILLAPORRINO",
                "FIF", "MINE", "JULÍN", "BOLONCHO", "VORNES", "CEREZAS B",
                "MOJI", "COF"
            ],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "historial_clubes": {}
        },
        "3ª División Grupo B": {
            "equipos": [
                "PER", "PICO", "XD", "UH", "DUTE", "MAMBO B",
                "GAMBI", "MACAGUADAN", "TORE", "BANANO", "AM", "FORT",
                "STOR", "ROMPH"
            ],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "historial_clubes": {}
        },
        "4ª División": {
            "equipos": [
                 "POLANDIA", "SIROL B", "HUNGARIA",
                 "NEDERLANDIA", "ALLSURA B", "TREO B", "EKIPO"
            ],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "historial_clubes": {}
        },
        "Sub-19 1 División": {
    "equipos": [
        "CEREZAS Sub-19",
        "DECERÓN Sub-19",
        "LONESTO Sub-19",
        "KINGZ Sub-19",
        "MAMBO Sub-19",
        "QUÍTER Sub-19",
        "BENSARO Sub-19",
        "SIROL Sub-19",
        "ANTINO Sub-19",
        "MELOP Sub-19",
        "RUPER Sub-19",
        "ALLSURA Sub-19",
        "ENERTO Sub-19",
        "TREO Sub-19",
        "DOMELÍ Sub-19",
        "DORRO Sub-19",
        "ASORPA Sub-19",
        "SABADERO Sub-19",
        "COCONUT Sub-19",
        "CHIMICHANGA Sub-19"
    ],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "historial_clubes": {}
},

"Sub-19 2 División": {
    "equipos": [
        "IGLESIA Sub-19",
        "POK Sub-19",
        "SIBERIA Sub-19",
        "SALMÓN Sub-19",
        "ALTORPO Sub-19",
        "FROSTÉ Sub-19",
        "FEBRONTO Sub-19",
        "ABDUZCAN Sub-19",
        "ANCO Sub-19",
        "ZOQUIO Sub-19",
        "AGUEST Sub-19",
        "ALFALFA Sub-19",
        "DENTOR Sub-19",
        "JOREVOS Sub-19",
        "AMPRO Sub-19",
        "MERSOL Sub-19",
        "NÁCOR Sub-19",
        "XEMAR Sub-19"
    ],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "historial_clubes": {}
},

"Sub-19 3 División Grupo A": {
    "equipos": [
        "LOCKE Sub-19",
        "MARTERO Sub-19",
        "SCAR Sub-19",
        "FOL Sub-19",
        "BLOX Sub-19",
        "VILLAPORRINO Sub-19",
        "FIF Sub-19",
        "MINE Sub-19",
        "JULÍN Sub-19",
        "BOLONCHO Sub-19",
        "VORNES Sub-19",
        "POLANDIA Sub-19",
        "MOJI Sub-19",
        "COF Sub-19",
        "HUNGARIA Sub-19"
    ],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "historial_clubes": {}
},

"Sub-19 3 División Grupo B": {
    "equipos": [
        "PER Sub-19",
        "PICO Sub-19",
        "XD Sub-19",
        "UH Sub-19",
        "DUTE Sub-19",
        "NEDERLANDIA Sub-19",
        "GAMBI Sub-19",
        "MACAGUADAN Sub-19",
        "TORE Sub-19",
        "BANANO Sub-19",
        "AM Sub-19",
        "FORT Sub-19",
        "STOR Sub-19",
        "ROMPH Sub-19",
        "EKIPO Sub-19"
    ],
    "calendario": [],
    "resultados": [],
    "jornada": 0,
    "historial_clubes": {}
},

            "Com 1ª División": {
                "equipos": [
                    "RB Zerkas", "Saulo", "Tordón", "Tervo", "Glanto",
                    "Absuka", "Zalmoa", "Folfo", "Zorla", "Toquero",
                    "Stung", "Borca", "Vilaporto", "Caurto"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Com 2ª División": {
                "equipos": [
                    "RB Zerkas B", "Quimbalú", "Cartuba", "Danesio",
                    "Tencla", "Pineto", "Sembencín", "Ceuta"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Com Sub-19 1 División": {
                "equipos": [
                    "RB Zerkas Sub-19", "Saulo Sub-19", "Tordón Sub-19", "Tervo Sub-19",
                    "Glanto Sub-19", "Absuka Sub-19", "Zalmoa Sub-19", "Folfo Sub-19",
                    "Zorla Sub-19", "Toquero Sub-19", "Stung Sub-19", "Borca Sub-19",
                    "Vilaporto Sub-19", "Caurto Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Com Sub-19 2 División": {
                "equipos": [
                    "Quimbalú Sub-19", "Cartuba Sub-19", "Danesio Sub-19",
                    "Tencla Sub-19", "Pineto Sub-19", "Sembencín Sub-19", "Ceuta Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },

            "Tengu 1ª División": {
                "equipos": [
                    "Tasón", "Albicans", "Cosmo", "Larano", "Corpazo",
                    "Selonda", "Chiva", "Cristo", "Hispetón", "Intes",
                    "Vástico", "Basufo", "Lopio", "Botabú"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Tengu 2ª División": {
                "equipos": [
                    "Villaverde", "Albicans B", "Colario", "Axómera",
                    "Paramonte", "Lutra", "Rilicu", "Lemel"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Tengu Sub-19 1 División": {
                "equipos": [
                    "Tasón Sub-19", "Albicans Sub-19", "Cosmo Sub-19", "Larano Sub-19",
                    "Corpazo Sub-19", "Selonda Sub-19", "Chiva Sub-19", "Cristo Sub-19",
                    "Hispetón Sub-19", "Intes Sub-19", "Vástico Sub-19", "Basufo Sub-19",
                    "Lopio Sub-19", "Botabú Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Tengu Sub-19 2 División": {
                "equipos": [
                    "Villaverde Sub-19", "Colario Sub-19", "Axómera Sub-19",
                    "Paramonte Sub-19", "Lutra Sub-19", "Rilicu Sub-19", "Lemel Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },

            "Folimón 1ª División": {
                "equipos": [
                    "EQUIPO_FOLIMON_1", "EQUIPO_FOLIMON_2", "EQUIPO_FOLIMON_3", "EQUIPO_FOLIMON_4",
                    "EQUIPO_FOLIMON_5", "EQUIPO_FOLIMON_6", "EQUIPO_FOLIMON_7", "EQUIPO_FOLIMON_8",
                    "EQUIPO_FOLIMON_9", "EQUIPO_FOLIMON_10", "EQUIPO_FOLIMON_11", "EQUIPO_FOLIMON_12",
                    "EQUIPO_FOLIMON_13", "EQUIPO_FOLIMON_14"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Folimón 2ª División": {
                "equipos": [
                    "EQUIPO_FOLIMON_2_1", "EQUIPO_FOLIMON_2_2", "EQUIPO_FOLIMON_2_3", "EQUIPO_FOLIMON_2_4",
                    "EQUIPO_FOLIMON_2_5", "EQUIPO_FOLIMON_2_6", "EQUIPO_FOLIMON_2_7", "EQUIPO_FOLIMON_2_8"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Folimón Sub-19 1 División": {
                "equipos": [
                    "EQUIPO_FOLIMON_1 Sub-19", "EQUIPO_FOLIMON_2 Sub-19", "EQUIPO_FOLIMON_3 Sub-19",
                    "EQUIPO_FOLIMON_4 Sub-19", "EQUIPO_FOLIMON_5 Sub-19", "EQUIPO_FOLIMON_6 Sub-19",
                    "EQUIPO_FOLIMON_7 Sub-19", "EQUIPO_FOLIMON_8 Sub-19", "EQUIPO_FOLIMON_9 Sub-19",
                    "EQUIPO_FOLIMON_10 Sub-19", "EQUIPO_FOLIMON_11 Sub-19", "EQUIPO_FOLIMON_12 Sub-19",
                    "EQUIPO_FOLIMON_13 Sub-19", "EQUIPO_FOLIMON_14 Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
            "Folimón Sub-19 2 División": {
                "equipos": [
                    "EQUIPO_FOLIMON_2_1 Sub-19", "EQUIPO_FOLIMON_2_2 Sub-19", "EQUIPO_FOLIMON_2_3 Sub-19",
                    "EQUIPO_FOLIMON_2_4 Sub-19", "EQUIPO_FOLIMON_2_5 Sub-19", "EQUIPO_FOLIMON_2_6 Sub-19",
                    "EQUIPO_FOLIMON_2_7 Sub-19", "EQUIPO_FOLIMON_2_8 Sub-19"
                ],
                "calendario": [],
                "resultados": [],
                "jornada": 0,
                "historial_clubes": {}
            },
    },
    "equipos_data": {
        "CEREZAS": {"liga": "1ª División", "escudo": "ðŸ’", "jugadores": [
            {"nombre": "Javi Cáceres", "media": 88, "valor": 50, "pos": "POR"},
            {"nombre": "Dani Tejero", "media": 75, "valor": 5, "pos": "JUG"},
            {"nombre": "Jaime López", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Joaquín", "media": 79, "valor": 12, "pos": "POR"},
            {"nombre": "Miguel Muñoz", "media": 81, "valor": 20, "pos": "JUG"},
            {"nombre": "Gonzalo Cortés", "media": 78, "valor": 15, "pos": "JUG"}
        ]},
        "DECERÓN": {"liga": "1ª División", "escudo": "ðŸŸ£", "jugadores": [
            {"nombre": "Fernando Sanchís", "media": 91, "valor": 70, "pos": "POR"},
            {"nombre": "Hugo Fernández", "media": 85, "valor": 30, "pos": "JUG"},
            {"nombre": "Arinho", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Lucas Lázaro", "media": 76, "valor": 5, "pos": "POR"},
            {"nombre": "Javi Sánchez", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Bembe", "media": 80, "valor": 15, "pos": "JUG"}
        ]},
        "LONESTO": {"liga": "1ª División", "escudo": "ðŸ¦", "jugadores": [
            {"nombre": "Petrović", "media": 80, "valor": 15, "pos": "POR"},
            {"nombre": "Tonsa", "media": 87, "valor": 40, "pos": "JUG"},
            {"nombre": "Dani Martínez", "media": 85, "valor": 30, "pos": "JUG"},
            {"nombre": "Takashi", "media": 76, "valor": 5, "pos": "POR"},
            {"nombre": "Raúl Córdoba", "media": 81, "valor": 18, "pos": "JUG"},
            {"nombre": "Nacho Jiménez", "media": 80, "valor": 15, "pos": "JUG"}
        ]},
        "KINGZ": {"liga": "1ª División", "escudo": "ðŸ‘‘", "jugadores": [
            {"nombre": "Nico Giménez", "media": 85, "valor": 30, "pos": "POR"},
            {"nombre": "Show", "media": 86, "valor": 35, "pos": "JUG"},
            {"nombre": "Léo Thien", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Laxman", "media": 70, "valor": 1, "pos": "POR"},
            {"nombre": "Arturo Benítez", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Sepi", "media": 80, "valor": 15, "pos": "JUG"}
        ]},
        "MAMBO": {"liga": "1ª División", "escudo": "ðŸ", "jugadores": [
            {"nombre": "Zhào", "media": 82, "valor": 20, "pos": "POR"},
            {"nombre": "Enzo Pérez", "media": 89, "valor": 50, "pos": "JUG"},
            {"nombre": "Lolo", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Nico Sánchez", "media": 78, "valor": 10, "pos": "POR"},
            {"nombre": "Meyer", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Fukinawa", "media": 80, "valor": 15, "pos": "JUG"}
        ]},
        "QUÍTER": {"liga": "1ª División", "escudo": "âš¡", "jugadores": [
            {"nombre": "De Jong", "media": 85, "valor": 30, "pos": "POR"},
            {"nombre": "Terglish", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Hadivick", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Héctor Martínez", "media": 72, "valor": 3, "pos": "POR"},
            {"nombre": "Caraçao", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Bedelchenko", "media": 75, "valor": 7, "pos": "JUG"}
        ]},
        "BENSARO": {"liga": "1ª División", "escudo": "ðŸ›¡ï¸", "jugadores": [
            {"nombre": "Juan Vega", "media": 80, "valor": 15, "pos": "POR"},
            {"nombre": "Torsič", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Blas", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Onyeka", "media": 73, "valor": 4, "pos": "POR"},
            {"nombre": "Felipe Cano", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "José Soriano", "media": 75, "valor": 5, "pos": "JUG"}
        ]},
        "SIROL": {"liga": "1ª División", "escudo": "ðŸŒŠ", "jugadores": [
            {"nombre": "Ramírez", "media": 82, "valor": 20, "pos": "POR"},
            {"nombre": "Enzo", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Virtanen", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Víctor Régulo", "media": 78, "valor": 10, "pos": "POR"},
            {"nombre": "Wellington", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "McCarthy", "media": 78, "valor": 10, "pos": "JUG"}
        ]},
        "ANTINO": {"liga": "1ª División", "escudo": "âš”ï¸", "jugadores": [
            {"nombre": "Iker Gallardo", "media": 78, "valor": 10, "pos": "POR"},
            {"nombre": "Esteban Moya", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Jesús Herrera", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Samuele Francesco", "media": 74, "valor": 5, "pos": "POR"},
            {"nombre": "Darío Márquez", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Felipe Santos", "media": 74, "valor": 5, "pos": "JUG"}
        ]},
        "MELOP": {"liga": "1ª División", "escudo": "ðŸˆ", "jugadores": [
            {"nombre": "Pedro Vázquez", "media": 87, "valor": 40, "pos": "POR"},
            {"nombre": "Carlos Torres", "media": 85, "valor": 30, "pos": "JUG"},
            {"nombre": "Vito JR", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Sérgio", "media": 77, "valor": 8, "pos": "POR"},
            {"nombre": "Mateo Vida", "media": 75, "valor": 5, "pos": "JUG"},
            {"nombre": "David Gutiérrez", "media": 75, "valor": 5, "pos": "JUG"}
        ]},
        "RUPER": {"liga": "1ª División", "escudo": "ðŸ¦Š", "jugadores": [
            {"nombre": "Fernando Blanco", "media": 75, "valor": 5, "pos": "POR"},
            {"nombre": "Youssef Idrissi", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Josema", "media": 75, "valor": 5, "pos": "JUG"},
            {"nombre": "Obi", "media": 71, "valor": 2, "pos": "POR"},
            {"nombre": "Andrés Navarro", "media": 75, "valor": 5, "pos": "JUG"},
            {"nombre": "Nil Santana", "media": 75, "valor": 5, "pos": "JUG"}
        ]},
        "ALLSURA": {"liga": "1ª División", "escudo": "ðŸ¦…", "jugadores": [
            {"nombre": "González", "media": 82, "valor": 20, "pos": "POR"},
            {"nombre": "Manuel Rodríguez", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Samu", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Óscar Sosa", "media": 74, "valor": 6, "pos": "POR"},
            {"nombre": "Eric Cabrera", "media": 82, "valor": 20, "pos": "JUG"},
            {"nombre": "Gabri Costa", "media": 78, "valor": 10, "pos": "JUG"}
        ]},
        "ENERTO": {"liga": "1ª División", "escudo": "âš¡", "jugadores": [
            {"nombre": "Carmona", "media": 80, "valor": 15, "pos": "POR"},
            {"nombre": "Marcos López", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Ángel Bravo", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Yilmaz", "media": 72, "valor": 3, "pos": "POR"},
            {"nombre": "Unai Pascual", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Rubén", "media": 71, "valor": 2, "pos": "JUG"}
        ]},
        "TREO": {"liga": "1ª División", "escudo": "ðŸŒ²", "jugadores": [
            {"nombre": "Guille Fuentes", "media": 84, "valor": 25, "pos": "POR"},
            {"nombre": "Ismael", "media": 84, "valor": 25, "pos": "JUG"},
            {"nombre": "Raúl Montero", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Ryan Anderson", "media": 71, "valor": 2, "pos": "POR"},
            {"nombre": "Serway", "media": 74, "valor": 5, "pos": "JUG"},
            {"nombre": "Rafa León", "media": 77, "valor": 9, "pos": "JUG"}
        ]},
        "DOMELÍ": {"liga": "1ª División", "escudo": "ðŸ ", "jugadores": [
            {"nombre": "Iván Martín", "media": 78, "valor": 10, "pos": "POR"},
            {"nombre": "Castillo", "media": 85, "valor": 30, "pos": "JUG"},
            {"nombre": "Lintombe", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Rossi", "media": 72, "valor": 3, "pos": "POR"},
            {"nombre": "Schmidt", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Aarón Garrido", "media": 74, "valor": 5, "pos": "JUG"}
        ]},
        "DORRO": {"liga": "1ª División", "escudo": "ðŸ‚", "jugadores": [
            {"nombre": "Dani Monzón", "media": 80, "valor": 15, "pos": "POR"},
            {"nombre": "Francisco Castro", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Gabri", "media": 80, "valor": 15, "pos": "JUG"},
            {"nombre": "Carlos González", "media": 75, "valor": 7, "pos": "POR"},
            {"nombre": "Carlos Jiménez", "media": 72, "valor": 3, "pos": "JUG"},
            {"nombre": "Juan Medina", "media": 75, "valor": 7, "pos": "JUG"}
        ]},
        "ASORPA": {"liga": "1ª División", "escudo": "ðŸ•·ï¸", "jugadores": [
            {"nombre": "Bruno Iglesias", "media": 77, "valor": 8, "pos": "POR"},
            {"nombre": "Alex Rubio", "media": 78, "valor": 10, "pos": "JUG"},
            {"nombre": "Rafa Ortega", "media": 74, "valor": 6, "pos": "JUG"},
            {"nombre": "Tanaka", "media": 70, "valor": 1, "pos": "POR"},
            {"nombre": "Moreno", "media": 73, "valor": 4, "pos": "JUG"},
            {"nombre": "Mario Carrasco", "media": 73, "valor": 4, "pos": "JUG"}
        ]},
        "SABADERO": {"liga": "1ª División", "escudo": "ðŸ“…", "jugadores": [
            {"nombre": "Víctor Casas", "media": 78, "valor": 10, "pos": "POR"},
            {"nombre": "Héctor Gómez", "media": 77, "valor": 9, "pos": "JUG"},
            {"nombre": "Montserrat", "media": 76, "valor": 8, "pos": "JUG"},
            {"nombre": "Dupont", "media": 73, "valor": 4, "pos": "POR"},
            {"nombre": "Méndez", "media": 71, "valor": 2, "pos": "JUG"},
            {"nombre": "Asier", "media": 73, "valor": 4, "pos": "JUG"}
        ]},
        "COCONUT": {"liga": "1ª División", "escudo": "ðŸ¥¥", "jugadores": [
            {"nombre": "Martín Peña", "media": 75, "valor": 7, "pos": "POR"},
            {"nombre": "Matías Sanz", "media": 77, "valor": 9, "pos": "JUG"},
            {"nombre": "Bleu", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Ricardo Fernández", "media": 74, "valor": 5, "pos": "POR"},
            {"nombre": "Alfonso Madrid", "media": 74, "valor": 5, "pos": "JUG"},
            {"nombre": "Tiquinho", "media": 71, "valor": 2, "pos": "JUG"}
        ]},
        "CHIMICHANGA": {"liga": "1ª División", "escudo": "ðŸŒ¯", "jugadores": [
            {"nombre": "Song", "media": 73, "valor": 4, "pos": "POR"},
            {"nombre": "Montero", "media": 76, "valor": 8, "pos": "JUG"},
            {"nombre": "Santi Hidalgo", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Diego Sánchez", "media": 70, "valor": 1, "pos": "POR"},
            {"nombre": "Antonio Soler", "media": 75, "valor": 7, "pos": "JUG"},
            {"nombre": "Sergio Pérez", "media": 72, "valor": 3, "pos": "JUG"}
        ]},
         "IGLESIA": {"liga": "2ª División", "escudo": "⛪", "jugadores": [
            {"nombre": "Martín Toribio", "media": 73, "valor": 5, "pos": "POR", "edad": 25},
            {"nombre": "Ale Sánchez", "media": 71, "valor": 4, "pos": "JUG", "edad": 26},
            {"nombre": "Pedro Domingo", "media": 71, "valor": 4, "pos": "JUG", "edad": 23},
            {"nombre": "Santiago Morales", "media": 67, "valor": 2, "pos": "POR", "edad": 28},
            {"nombre": "Bauer", "media": 67, "valor": 2, "pos": "JUG", "edad": 19},
            {"nombre": "Arnau Afonso", "media": 67, "valor": 2, "pos": "JUG", "edad": 18}
        ]},
        "POK": {"liga": "2ª División", "escudo": "🎴", "jugadores": [
            {"nombre": "Miguel Ballesteros", "media": 69, "valor": 3, "pos": "POR", "edad": 34},
            {"nombre": "Arimé", "media": 75, "valor": 6, "pos": "JUG", "edad": 27},
            {"nombre": "Manuel Berenguer", "media": 73, "valor": 5, "pos": "JUG", "edad": 25},
            {"nombre": "Antonio Martínez", "media": 69, "valor": 3, "pos": "POR", "edad": 23},
            {"nombre": "Francisco Pazos", "media": 67, "valor": 2, "pos": "JUG", "edad": 23},
            {"nombre": "Dani Pedraza", "media": 65, "valor": 1, "pos": "JUG", "edad": 18}
        ]},
        "SIBERIA": {"liga": "2ª División", "escudo": "❄️", "jugadores": [
            {"nombre": "Sosa", "media": 73, "valor": 5, "pos": "POR", "edad": 22},
            {"nombre": "Côme Le Goff", "media": 71, "valor": 4, "pos": "JUG", "edad": 21},
            {"nombre": "Vicente Barrero", "media": 73, "valor": 5, "pos": "JUG", "edad": 24},
            {"nombre": "Alex Fernández", "media": 69, "valor": 3, "pos": "POR", "edad": 28},
            {"nombre": "Alejandro Sierra", "media": 69, "valor": 3, "pos": "JUG", "edad": 33},
            {"nombre": "Valentín Frutos", "media": 67, "valor": 2, "pos": "JUG", "edad": 16}
        ]},
        "SALMÓN": {"liga": "2ª División", "escudo": "🐟", "jugadores": [
            {"nombre": "Kleber", "media": 71, "valor": 4, "pos": "POR", "edad": 29},
            {"nombre": "Javi Oller", "media": 71, "valor": 4, "pos": "JUG", "edad": 19},
            {"nombre": "Hugo Prieto", "media": 73, "valor": 5, "pos": "JUG", "edad": 28},
            {"nombre": "Mario Villegas", "media": 69, "valor": 3, "pos": "POR", "edad": 24},
            {"nombre": "Pablo Plaza", "media": 67, "valor": 2, "pos": "JUG", "edad": 19},
            {"nombre": "Darling", "media": 67, "valor": 2, "pos": "JUG", "edad": 18}
        ]},
        "ALTORPO": {"liga": "2ª División", "escudo": "🏔️", "jugadores": [
            {"nombre": "Chema Romero", "media": 73, "valor": 5, "pos": "POR", "edad": 26},
            {"nombre": "Engels", "media": 71, "valor": 4, "pos": "JUG", "edad": 30},
            {"nombre": "Luis Blanco", "media": 71, "valor": 4, "pos": "JUG", "edad": 22},
            {"nombre": "Voronin", "media": 69, "valor": 3, "pos": "POR", "edad": 30},
            {"nombre": "César Rico", "media": 69, "valor": 3, "pos": "JUG", "edad": 20},
            {"nombre": "Esteban Palomar", "media": 67, "valor": 2, "pos": "JUG", "edad": 19}
        ]},
        "FROSTÉ": {"liga": "2ª División", "escudo": "🧊", "jugadores": [
            {"nombre": "Miguel Zamorano", "media": 73, "valor": 5, "pos": "POR", "edad": 26},
            {"nombre": "Maxi Merino", "media": 71, "valor": 4, "pos": "JUG", "edad": 18},
            {"nombre": "Pereira", "media": 73, "valor": 5, "pos": "JUG", "edad": 26},
            {"nombre": "Soria", "media": 67, "valor": 2, "pos": "POR", "edad": 24},
            {"nombre": "Kombo", "media": 67, "valor": 2, "pos": "JUG", "edad": 24},
            {"nombre": "Boualem", "media": 69, "valor": 3, "pos": "JUG", "edad": 18}
        ]},
        "FEBRONTO": {"liga": "2ª División", "escudo": "🔥", "jugadores": [
            {"nombre": "Juan Meléndez", "media": 71, "valor": 4, "pos": "POR", "edad": 23},
            {"nombre": "Hatem", "media": 75, "valor": 6, "pos": "JUG", "edad": 22},
            {"nombre": "Nico Villalba", "media": 71, "valor": 4, "pos": "JUG", "edad": 24},
            {"nombre": "Lombardi", "media": 69, "valor": 3, "pos": "POR", "edad": 25},
            {"nombre": "David Rivas", "media": 67, "valor": 2, "pos": "JUG", "edad": 20},
            {"nombre": "Ángel Duarte", "media": 67, "valor": 2, "pos": "JUG", "edad": 19}
        ]},
        "ABDUZCAN": {"liga": "2ª División", "escudo": "🛸", "jugadores": [
            {"nombre": "Dani Rubio", "media": 73, "valor": 5, "pos": "POR", "edad": 26},
            {"nombre": "Juan Aguilar", "media": 71, "valor": 4, "pos": "JUG", "edad": 25},
            {"nombre": "David Ponce", "media": 71, "valor": 4, "pos": "JUG", "edad": 27},
            {"nombre": "Luque", "media": 71, "valor": 4, "pos": "POR", "edad": 26},
            {"nombre": "Laredo", "media": 69, "valor": 3, "pos": "JUG", "edad": 29},
            {"nombre": "Jaime Egea", "media": 62, "valor": 0.6, "pos": "JUG", "edad": 17}
        ]},
        "ANCO": {"liga": "2ª División", "escudo": "⚓", "jugadores": [
            {"nombre": "Olmo", "media": 71, "valor": 4, "pos": "POR", "edad": 19},
            {"nombre": "Taleb", "media": 69, "valor": 3, "pos": "JUG", "edad": 28},
            {"nombre": "Alonso", "media": 69, "valor": 3, "pos": "JUG", "edad": 25},
            {"nombre": "Afonso", "media": 67, "valor": 2, "pos": "POR", "edad": 22},
            {"nombre": "Marc", "media": 65, "valor": 1, "pos": "JUG", "edad": 22},
            {"nombre": "Uygun", "media": 65, "valor": 1, "pos": "JUG", "edad": 20}
        ]},
        "ZOQUIO": {"liga": "2ª División", "escudo": "🦎", "jugadores": [
            {"nombre": "Dumont", "media": 69, "valor": 3, "pos": "POR", "edad": 28},
            {"nombre": "Alberto", "media": 67, "valor": 2, "pos": "JUG", "edad": 22},
            {"nombre": "Suárez", "media": 69, "valor": 3, "pos": "JUG", "edad": 24},
            {"nombre": "Muntari", "media": 65, "valor": 1, "pos": "POR", "edad": 22},
            {"nombre": "Calleja", "media": 67, "valor": 2, "pos": "JUG", "edad": 25},
            {"nombre": "Hugo", "media": 67, "valor": 2, "pos": "JUG", "edad": 20}
        ]},
        "AGUEST": {"liga": "2ª División", "escudo": "🌫️", "jugadores": [
            {"nombre": "César", "media": 67, "valor": 2, "pos": "POR", "edad": 31},
            {"nombre": "Loureiro", "media": 69, "valor": 3, "pos": "JUG", "edad": 27},
            {"nombre": "Spence", "media": 71, "valor": 4, "pos": "JUG", "edad": 24},
            {"nombre": "Bin Zhao", "media": 69, "valor": 3, "pos": "POR", "edad": 24},
            {"nombre": "Borja", "media": 67, "valor": 2, "pos": "JUG", "edad": 21},
            {"nombre": "Saúl", "media": 67, "valor": 2, "pos": "JUG", "edad": 19}
        ]},
        "ALFALFA": {"liga": "2ª División", "escudo": "🌿", "jugadores": [
            {"nombre": "Prat", "media": 69, "valor": 3, "pos": "POR", "edad": 23},
            {"nombre": "Mario", "media": 67, "valor": 2, "pos": "JUG", "edad": 20},
            {"nombre": "Nil", "media": 69, "valor": 3, "pos": "JUG", "edad": 26},
            {"nombre": "Alarcón", "media": 67, "valor": 2, "pos": "POR", "edad": 27},
            {"nombre": "Appiah", "media": 67, "valor": 2, "pos": "JUG", "edad": 24},
            {"nombre": "Cordero", "media": 67, "valor": 2, "pos": "JUG", "edad": 19}
        ]},
        "DENTOR": {"liga": "2ª División", "escudo": "🦷", "jugadores": [
            {"nombre": "Mayoral", "media": 69, "valor": 3, "pos": "POR", "edad": 29},
            {"nombre": "Vranches", "media": 69, "valor": 3, "pos": "JUG", "edad": 23},
            {"nombre": "Migue", "media": 67, "valor": 2, "pos": "JUG", "edad": 32},
            {"nombre": "Hindson", "media": 67, "valor": 2, "pos": "POR", "edad": 21},
            {"nombre": "Gaspar", "media": 67, "valor": 2, "pos": "JUG", "edad": 23},
            {"nombre": "Fernán", "media": 65, "valor": 1, "pos": "JUG", "edad": 18}
        ]},
        "JOREVOS": {"liga": "2ª División", "escudo": "🪐", "jugadores": [
            {"nombre": "Unai", "media": 71, "valor": 4, "pos": "POR", "edad": 26},
            {"nombre": "Buendía", "media": 69, "valor": 3, "pos": "JUG", "edad": 24},
            {"nombre": "Bellido", "media": 67, "valor": 2, "pos": "JUG", "edad": 21},
            {"nombre": "Alex Fallon", "media": 65, "valor": 1, "pos": "POR", "edad": 22},
            {"nombre": "Luis", "media": 67, "valor": 2, "pos": "JUG", "edad": 26},
            {"nombre": "Nelson", "media": 63, "valor": 0.7, "pos": "JUG", "edad": 17}
        ]},
        "AMPRO": {"liga": "2ª División", "escudo": "🔧", "jugadores": [
            {"nombre": "Perea", "media": 69, "valor": 3, "pos": "POR", "edad": 27},
            {"nombre": "Emilio", "media": 69, "valor": 3, "pos": "JUG", "edad": 25},
            {"nombre": "Noah Miller", "media": 67, "valor": 2, "pos": "JUG", "edad": 22},
            {"nombre": "Machín", "media": 67, "valor": 2, "pos": "POR", "edad": 26},
            {"nombre": "Granados", "media": 65, "valor": 1, "pos": "JUG", "edad": 30},
            {"nombre": "Schopp", "media": 67, "valor": 2, "pos": "JUG", "edad": 21}
        ]},
        "MERSOL": {"liga": "2ª División", "escudo": "🌞", "jugadores": [
            {"nombre": "Juan Jesús", "media": 75, "valor": 6, "pos": "POR", "edad": 25},
            {"nombre": "Seoane", "media": 73, "valor": 5, "pos": "JUG", "edad": 24},
            {"nombre": "Galindo", "media": 71, "valor": 4, "pos": "JUG", "edad": 28},
            {"nombre": "Nkgosi Davids", "media": 69, "valor": 3, "pos": "POR", "edad": 27},
            {"nombre": "Eloy", "media": 60, "valor": 0.1, "pos": "JUG", "edad": 23},
            {"nombre": "Llorer", "media": 65, "valor": 1, "pos": "JUG", "edad": 18}
        ]},
        "NÁCOR": {"liga": "2ª División", "escudo": "🗿", "jugadores": [
            {"nombre": "Mariño", "media": 71, "valor": 4, "pos": "POR", "edad": 22},
            {"nombre": "Moyano", "media": 73, "valor": 5, "pos": "JUG", "edad": 27},
            {"nombre": "Heckingbottom", "media": 71, "valor": 4, "pos": "JUG", "edad": 29},
            {"nombre": "Mráz", "media": 69, "valor": 3, "pos": "POR", "edad": 26},
            {"nombre": "Oriol Rivera", "media": 67, "valor": 2, "pos": "JUG", "edad": 18},
            {"nombre": "Le Bris", "media": 67, "valor": 2, "pos": "JUG", "edad": 20}
        ]},
        "XEMAR": {"liga": "2ª División", "escudo": "💠", "jugadores": [
            {"nombre": "Moya", "media": 73, "valor": 5, "pos": "POR", "edad": 26},
            {"nombre": "Moha", "media": 71, "valor": 4, "pos": "JUG", "edad": 23},
            {"nombre": "Solana", "media": 71, "valor": 4, "pos": "JUG", "edad": 21},
            {"nombre": "Iván", "media": 69, "valor": 3, "pos": "POR", "edad": 28},
            {"nombre": "Carlitos", "media": 65, "valor": 1, "pos": "JUG", "edad": 19},
            {"nombre": "Josemi", "media": 67, "valor": 2, "pos": "JUG", "edad": 20}
        ]},
"LOCKE": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Arana",             "media": 67, "valor": 2.0,  "pos": "POR", "edad": 22},
        {"nombre": "Cerezo",            "media": 65, "valor": 1.0,  "pos": "JUG", "edad": 30},
        {"nombre": "Guille Vera",       "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Julian",            "media": 60, "valor": 0.5,  "pos": "POR", "edad": 24},
        {"nombre": "Fritz",             "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 23},
        {"nombre": "Fraga",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 27},
    ]},
"MARTERO": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Trigo",             "media": 60, "valor": 0.5,  "pos": "POR", "edad": 23},
        {"nombre": "Peiro",             "media": 62, "valor": 0.75, "pos": "JUG", "edad": 25},
        {"nombre": "Escobar",           "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 29},
        {"nombre": "Thami Sampson",     "media": 57, "valor": 0.2,  "pos": "POR", "edad": 22},
        {"nombre": "Ernesto",           "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
        {"nombre": "Martos",            "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 23},
    ]},
"SCAR": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Ruano",             "media": 65, "valor": 1.0,  "pos": "POR", "edad": 29},
        {"nombre": "Hulshoff",          "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 27},
        {"nombre": "Zamora",            "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 24},
        {"nombre": "Hugo Yuste",        "media": 58, "valor": 0.3,  "pos": "POR", "edad": 25},
        {"nombre": "Wallius",           "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 23},
        {"nombre": "Raposo",            "media": 56, "valor": 0.1,  "pos": "JUG", "edad": 19},
    ]},
"FOL": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Andrés",            "media": 56, "valor": 0.1,  "pos": "POR", "edad": 37},
        {"nombre": "Esmorís",           "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 28},
        {"nombre": "Minatel",           "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 20},
        {"nombre": "Hadi",              "media": 58, "valor": 0.3,  "pos": "POR", "edad": 24},
        {"nombre": "Nabil L'Ghoul",     "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Milla",             "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
    ]},
"BLOX": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Rojo",              "media": 60, "valor": 0.5,  "pos": "POR", "edad": 23},
        {"nombre": "Fabri Zurdel",      "media": 58, "valor": 0.39, "pos": "JUG", "edad": 24},
        {"nombre": "Yacouba",           "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 22},
        {"nombre": "Buenaventura",      "media": 58, "valor": 0.3,  "pos": "POR", "edad": 22},
        {"nombre": "Diatta",            "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Krasniqi",          "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 19},
    ]},
"VILLAPORRINO": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Rivera",            "media": 65, "valor": 1.0,  "pos": "POR", "edad": 25},
        {"nombre": "Ayoze",             "media": 64, "valor": 0.9,  "pos": "JUG", "edad": 24},
        {"nombre": "Sandoval",          "media": 62, "valor": 0.7,  "pos": "JUG", "edad": 31},
        {"nombre": "Soppy",             "media": 62, "valor": 0.7,  "pos": "POR", "edad": 23},
        {"nombre": "Méndez",            "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 22},
        {"nombre": "Crespo",            "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 19},
    ]},
"FIF": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Günter",            "media": 58, "valor": 0.3,  "pos": "POR", "edad": 21},
        {"nombre": "Pizzi",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 25},
        {"nombre": "Bamba",             "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 24},
        {"nombre": "Agustín",           "media": 57, "valor": 0.2,  "pos": "POR", "edad": 32},
        {"nombre": "Cabral",            "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 21},
        {"nombre": "Borja Marí",        "media": 56, "valor": 0.15, "pos": "JUG", "edad": 18},
    ]},
"MINE": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Morris",            "media": 59, "valor": 0.4,  "pos": "POR", "edad": 31},
        {"nombre": "Pedraza",           "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 24},
        {"nombre": "Manquillo",         "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 22},
        {"nombre": "Amarillo",          "media": 58, "valor": 0.3,  "pos": "POR", "edad": 26},
        {"nombre": "Carrión",           "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Navarra",           "media": 56, "valor": 0.1,  "pos": "JUG", "edad": 19},
    ]},
"JULÍN": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Soler",             "media": 65, "valor": 1.0,  "pos": "POR", "edad": 24},
        {"nombre": "Vasco",             "media": 64, "valor": 0.9,  "pos": "JUG", "edad": 26},
        {"nombre": "Palencia",          "media": 65, "valor": 1.0,  "pos": "JUG", "edad": 23},
        {"nombre": "Renato",            "media": 61, "valor": 0.6,  "pos": "POR", "edad": 25},
        {"nombre": "Marcano",           "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 22},
        {"nombre": "Rafa",              "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 19},
    ]},
"BOLONCHO": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Girard",            "media": 58, "valor": 0.3,  "pos": "POR", "edad": 26},
        {"nombre": "Díaz",              "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 21},
        {"nombre": "Muñoz",             "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 27},
        {"nombre": "Bissainthe",        "media": 59, "valor": 0.4,  "pos": "POR", "edad": 22},
        {"nombre": "Navas",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 29},
        {"nombre": "Barroso",           "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 23},
    ]},
"VORNES": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Jaén",              "media": 59, "valor": 0.4,  "pos": "POR", "edad": 28},
        {"nombre": "Gray",              "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 24},
        {"nombre": "Soares",            "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 23},
        {"nombre": "Bilbao",            "media": 62, "valor": 0.7,  "pos": "POR", "edad": 29},
        {"nombre": "César",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 20},
        {"nombre": "Carbonell",         "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 19},
    ]},
"CEREZAS B": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Sergio Sánchez",    "media": 56, "valor": 0.1,  "pos": "POR", "edad": 17},
        {"nombre": "Simón",             "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 20},
        {"nombre": "Montillana",        "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 19},
        {"nombre": "Juanjo",            "media": 56, "valor": 0.1,  "pos": "POR", "edad": 20},
        {"nombre": "Juanmi Muñoz",      "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 17},
        {"nombre": "Trivi",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 17},
    ]},
"MOJI": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Bernabé",           "media": 59, "valor": 0.4,  "pos": "POR", "edad": 27},
        {"nombre": "Adjeil Pereira",    "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 19},
        {"nombre": "Toral",             "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 30},
        {"nombre": "Bueno",             "media": 58, "valor": 0.3,  "pos": "POR", "edad": 29},
        {"nombre": "De Barr",           "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Diaby",             "media": 56, "valor": 0.1,  "pos": "JUG", "edad": 19},
    ]},
"COF": {
    "liga": "3ª División Grupo A",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Robinson",          "media": 60, "valor": 0.5,  "pos": "POR", "edad": 24},
        {"nombre": "Denis",             "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 22},
        {"nombre": "Turrell",           "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 23},
        {"nombre": "Ramos",             "media": 57, "valor": 0.2,  "pos": "POR", "edad": 24},
        {"nombre": "Kike",              "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 19},
        {"nombre": "Iglesias",          "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
    ]},
"PER": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Skela",             "media": 58, "valor": 0.3,  "pos": "POR", "edad": 30},
        {"nombre": "Curtin",            "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 20},
        {"nombre": "Mateo López",       "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 28},
        {"nombre": "Peñaranda",         "media": 57, "valor": 0.2,  "pos": "POR", "edad": 25},
        {"nombre": "Mario Iglesias",    "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 18},
        {"nombre": "Antonio Iglesias",  "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 18},
    ]},
"PICO": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Lima",              "media": 58, "valor": 0.3,  "pos": "POR", "edad": 26},
        {"nombre": "Turunen",           "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 27},
        {"nombre": "Alejandro Torres",  "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 29},
        {"nombre": "Kowalski",          "media": 65, "valor": 1.0,  "pos": "POR", "edad": 31},
        {"nombre": "Javier Morales",    "media": 62, "valor": 0.7,  "pos": "JUG", "edad": 22},
        {"nombre": "Marín",             "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 19},
    ]},
"XD": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Mario Jiménez",     "media": 59, "valor": 0.4,  "pos": "POR", "edad": 29},
        {"nombre": "Juan Poyato",       "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 23},
        {"nombre": "Idrizi",            "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 28},
        {"nombre": "Itten",             "media": 56, "valor": 0.1,  "pos": "POR", "edad": 24},
        {"nombre": "Tomás Romero",      "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
        {"nombre": "Gonzalo Hervás",    "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 19},
    ]},
"UH": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Alfonso Millán",    "media": 59, "valor": 0.4,  "pos": "POR", "edad": 20},
        {"nombre": "Benito Calderón",   "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 23},
        {"nombre": "Pedro Ochoa",       "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 25},
        {"nombre": "Kovačević",         "media": 58, "valor": 0.3,  "pos": "POR", "edad": 28},
        {"nombre": "O’Reilly",          "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 22},
        {"nombre": "Vušković",          "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 21},
    ]},
"DUTE": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Blas Nadal",        "media": 59, "valor": 0.4,  "pos": "POR", "edad": 29},
        {"nombre": "Manu Pozo",         "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 26},
        {"nombre": "Íñigo Botín",       "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 24},
        {"nombre": "Daniel Blasco",     "media": 57, "valor": 0.2,  "pos": "POR", "edad": 22},
        {"nombre": "Nunes",             "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 20},
        {"nombre": "Kooistra",          "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 19},
    ]},
"MAMBO B": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Ángel Montilla",    "media": 59, "valor": 0.4,  "pos": "POR", "edad": 18},
        {"nombre": "Proixão",           "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 20},
        {"nombre": "Simbinho",          "media": 65, "valor": 1.0,  "pos": "JUG", "edad": 22},
        {"nombre": "Al-Mansoori",       "media": 58, "valor": 0.3,  "pos": "POR", "edad": 21},
        {"nombre": "Aitor Cañete",      "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 18},
        {"nombre": "David Retamosa",    "media": 61, "valor": 0.6,  "pos": "JUG", "edad": 18},
    ]},
"GAMBI": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Pelayo Cela",       "media": 61, "valor": 0.6,  "pos": "POR", "edad": 25},
        {"nombre": "Bajrami",           "media": 62, "valor": 0.7,  "pos": "JUG", "edad": 22},
        {"nombre": "Hipólito Navas",    "media": 63, "valor": 0.8,  "pos": "JUG", "edad": 32},
        {"nombre": "Javi García",       "media": 59, "valor": 0.4,  "pos": "POR", "edad": 24},
        {"nombre": "Fran Martín",       "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 30},
        {"nombre": "Nacho Luna",        "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 17},
    ]},
"MACAGUADAN": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Pablo Barrera",     "media": 63, "valor": 0.8,  "pos": "POR", "edad": 31},
        {"nombre": "Antonio Guzmán",    "media": 64, "valor": 0.9,  "pos": "JUG", "edad": 27},
        {"nombre": "Pau Santana",       "media": 65, "valor": 1.0,  "pos": "JUG", "edad": 22},
        {"nombre": "Akindale Olatunji", "media": 60, "valor": 0.5,  "pos": "POR", "edad": 22},
        {"nombre": "Ernesto Elías",     "media": 62, "valor": 0.7,  "pos": "JUG", "edad": 22},
        {"nombre": "Veto Sevilla",      "media": 64, "valor": 0.9,  "pos": "JUG", "edad": 20},
    ]},
"TORE": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Tobías Cifuentes",  "media": 60, "valor": 0.5,  "pos": "POR", "edad": 20},
        {"nombre": "Mazzu",             "media": 62, "valor": 0.7,  "pos": "JUG", "edad": 26},
        {"nombre": "Djibril Pelletier", "media": 63, "valor": 0.8,  "pos": "JUG", "edad": 22},
        {"nombre": "Juan Pérez",        "media": 60, "valor": 0.5,  "pos": "POR", "edad": 30},
        {"nombre": "Martín Moncayo",    "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
        {"nombre": "Víctor Narváez",    "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 21},
    ]},
"BANANO": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Kavanagh",          "media": 59, "valor": 0.4,  "pos": "POR", "edad": 24},
        {"nombre": "Diouf",             "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 28},
        {"nombre": "Pablo Vázquez",     "media": 63, "valor": 0.8,  "pos": "JUG", "edad": 23},
        {"nombre": "Guillermo Varela",  "media": 58, "valor": 0.3,  "pos": "POR", "edad": 26},
        {"nombre": "Aarón Carranza",    "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 20},
        {"nombre": "Miguel Zerolo",     "media": 64, "valor": 0.9,  "pos": "JUG", "edad": 18},
    ]},
"AM": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Antonio Castellanos","media": 61, "valor": 0.6, "pos": "POR", "edad": 22},
        {"nombre": "Jesús Yague",       "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 27},
        {"nombre": "Alex Gómez",        "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 25},
        {"nombre": "Liam Ballester",    "media": 59, "valor": 0.4,  "pos": "POR", "edad": 23},
        {"nombre": "Jorge Jesús Ledesma","media": 57, "valor": 0.2, "pos": "JUG", "edad": 22},
        {"nombre": "Luciano Zaragoza",  "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 18},
    ]},
"FORT": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Ba",                "media": 59, "valor": 0.4,  "pos": "POR", "edad": 28},
        {"nombre": "Pol Fuentes",       "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 29},
        {"nombre": "Alejandro Serna",   "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 24},
        {"nombre": "Juris Kalniņš",     "media": 57, "valor": 0.2,  "pos": "POR", "edad": 23},
        {"nombre": "Juan Manuel Rubio", "media": 56, "valor": 0.1,  "pos": "JUG", "edad": 18},
        {"nombre": "Juan García",       "media": 57, "valor": 0.2,  "pos": "JUG", "edad": 19},
    ]},
"STOR": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Miguel Ángel del Monte","media": 59, "valor": 0.4, "pos": "POR", "edad": 22},
        {"nombre": "Martín Castillo",   "media": 59, "valor": 0.4,  "pos": "JUG", "edad": 21},
        {"nombre": "Juan Prado",        "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 26},
        {"nombre": "Leo Enríquez",      "media": 56, "valor": 0.1,  "pos": "POR", "edad": 24},
        {"nombre": "Tomás Rubio",       "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 18},
        {"nombre": "Enrique Puertas",   "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 22},
    ]},
"ROMPH": {
    "liga": "3ª División Grupo B",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Vicente Mata",      "media": 61, "valor": 0.6,  "pos": "POR", "edad": 27},
        {"nombre": "Julio Serrano",     "media": 60, "valor": 0.5,  "pos": "JUG", "edad": 28},
        {"nombre": "Hugo Muñoz",        "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 26},
        {"nombre": "Tayler Emrini",     "media": 56, "valor": 0.1,  "pos": "POR", "edad": 19},
        {"nombre": "Rodri Jiménez",     "media": 58, "valor": 0.3,  "pos": "JUG", "edad": 20},
        {"nombre": "Sergio Badía",      "media": 57, "valor": 0.25, "pos": "JUG", "edad": 21},
    ]},
"POLANDIA": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Paco Jubero", "media": 58, "valor": 0.2, "pos": "POR", "edad": 24},
    {"nombre": "Pepe Ferrer", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Noah De Jong", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 26},
    {"nombre": "Manuel Pino", "media": 56, "valor": 0.05, "pos": "POR", "edad": 22},
    {"nombre": "Fleminho", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 23},
    {"nombre": "Javi Dorado", "media": 56, "valor": 0.05, "pos": "JUG", "edad": 19}
]},

"SIROL B": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Marc Ferrando", "media": 58, "valor": 0.2, "pos": "POR", "edad": 23},
    {"nombre": "Casado", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 20},
    {"nombre": "Puerta", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Fabian Carbon", "media": 57, "valor": 0.1, "pos": "POR", "edad": 20},
    {"nombre": "Luis Ramis", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Rings", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 21}
]},

"HUNGARIA": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Sousa", "media": 58, "valor": 0.2, "pos": "POR", "edad": 23},
    {"nombre": "Heliberto Orozco", "media": 59, "valor": 0.3, "pos": "JUG", "edad": 28},
    {"nombre": "Alberto Riera", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 20},
    {"nombre": "Pedro Navas", "media": 58, "valor": 0.2, "pos": "POR", "edad": 26},
    {"nombre": "Álex Crespo", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Manuel Marí", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 17}
]},

"NEDERLANDIA": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Dorvič", "media": 58, "valor": 0.2, "pos": "POR", "edad": 26},
    {"nombre": "Mensah", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 25},
    {"nombre": "Mikel Torres", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Leopoldo de Andrade", "media": 57, "valor": 0.1, "pos": "POR", "edad": 21},
    {"nombre": "Diarra", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 22},
    {"nombre": "Traoré", "media": 56, "valor": 0.05, "pos": "JUG", "edad": 16}
]},

"EKIPO": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "aha", "media": 58, "valor": 0.2, "pos": "POR", "edad": 26},
    {"nombre": "meme", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 25},
    {"nombre": "mism Torres", "media": 58, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "lsod de Andrade", "media": 57, "valor": 0.1, "pos": "POR", "edad": 21},
    {"nombre": "vms", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 22},
    {"nombre": "3im", "media": 56, "valor": 0.05, "pos": "JUG", "edad": 16}
]},

"ALLSURA B": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Jan Portero", "media": 58, "valor": 0.2, "pos": "POR", "edad": 20},
    {"nombre": "Óliver Reguillos", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 21},
    {"nombre": "Sheldon Ngubo", "media": 58, "valor": 0.25, "pos": "JUG", "edad": 20},
    {"nombre": "Jacobo Toledano", "media": 57, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Bruno Montesinos", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 20},
    {"nombre": "Manolo Rivas", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 17}
]},

"TREO B": {"liga": "4ª División", "escudo": "⚪", "jugadores": [
    {"nombre": "Julio Estévez", "media": 58, "valor": 0.2, "pos": "POR", "edad": 21},
    {"nombre": "Jorge Villar", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Gerard Fuster", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Claudio Pacheco", "media": 57, "valor": 0.1, "pos": "POR", "edad": 20},
    {"nombre": "Francisco Mayoral", "media": 56, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Diambou", "media": 57, "valor": 0.1, "pos": "JUG", "edad": 16}
]},
    "CEREZAS Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Lázaro Di Domenico", "media": 60, "valor": 1.0, "pos": "POR", "edad": 19},
        {"nombre": "Aarón Altozano", "media": 57, "valor": 0.7, "pos": "POR", "edad": 18},
        {"nombre": "De Cea", "media": 54, "valor": 0.4, "pos": "POR", "edad": 17},
        {"nombre": "Onguene", "media": 59, "valor": 0.9, "pos": "JUG", "edad": 19},
        {"nombre": "Rubén Fortea", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 18},
        {"nombre": "Luciano Quintana", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Waldo Coronas", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 17},
        {"nombre": "Sebas Arrebola", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Gueye", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 16},
        {"nombre": "Jaime Tejero", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 15}
    ]},
    "DECERÓN Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 DECERN Sub-19", "media": 60, "valor": 1.0, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 DECERN Sub-19", "media": 57, "valor": 0.7, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 DECERN Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 DECERN Sub-19", "media": 59, "valor": 0.9, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 DECERN Sub-19", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 DECERN Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 DECERN Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 DECERN Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 DECERN Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 DECERN Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 16}
    ]},
    "LONESTO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 LONESTO Sub-19", "media": 60, "valor": 1.0, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 LONESTO Sub-19", "media": 57, "valor": 0.7, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 LONESTO Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 LONESTO Sub-19", "media": 59, "valor": 0.9, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 LONESTO Sub-19", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 LONESTO Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 LONESTO Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 LONESTO Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 LONESTO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 LONESTO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 16}
    ]},
    "KINGZ Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 KINGZ Sub-19", "media": 60, "valor": 1.0, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 KINGZ Sub-19", "media": 57, "valor": 0.7, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 KINGZ Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 KINGZ Sub-19", "media": 59, "valor": 0.9, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 KINGZ Sub-19", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 KINGZ Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 KINGZ Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 KINGZ Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 KINGZ Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 KINGZ Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 16}
    ]},
    "MAMBO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 MAMBO Sub-19", "media": 59, "valor": 0.9, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 MAMBO Sub-19", "media": 56, "valor": 0.6, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 MAMBO Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 MAMBO Sub-19", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 MAMBO Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 MAMBO Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 MAMBO Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 MAMBO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 MAMBO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 MAMBO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 16}
    ]},
    "QUÍTER Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 QUÍTER Sub-19", "media": 59, "valor": 0.9, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 QUÍTER Sub-19", "media": 56, "valor": 0.6, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 QUÍTER Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 QUÍTER Sub-19", "media": 58, "valor": 0.8, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 QUÍTER Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 QUÍTER Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 QUÍTER Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 QUÍTER Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 QUÍTER Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 QUÍTER Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 16}
    ]},
    "BENSARO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 BENSARO Sub-19", "media": 58, "valor": 0.8, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 BENSARO Sub-19", "media": 55, "valor": 0.5, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 BENSARO Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 BENSARO Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 BENSARO Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 BENSARO Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 BENSARO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 BENSARO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 BENSARO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 BENSARO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 16}
    ]},
    "SIROL Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 SIROL Sub-19", "media": 58, "valor": 0.8, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 SIROL Sub-19", "media": 55, "valor": 0.5, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 SIROL Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 SIROL Sub-19", "media": 57, "valor": 0.7, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 SIROL Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 SIROL Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 SIROL Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 SIROL Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 SIROL Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 SIROL Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 16}
    ]},
    "ANTINO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 ANTINO Sub-19", "media": 57, "valor": 0.7, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 ANTINO Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 ANTINO Sub-19", "media": 51, "valor": 0.1, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 ANTINO Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 ANTINO Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 ANTINO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 ANTINO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 ANTINO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 ANTINO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 ANTINO Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "MELOP Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 MELOP Sub-19", "media": 57, "valor": 0.7, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 MELOP Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 MELOP Sub-19", "media": 51, "valor": 0.1, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 MELOP Sub-19", "media": 56, "valor": 0.6, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 MELOP Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 MELOP Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 MELOP Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 MELOP Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 MELOP Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 MELOP Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "RUPER Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 RUPER Sub-19", "media": 56, "valor": 0.6, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 RUPER Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 RUPER Sub-19", "media": 50, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 RUPER Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 RUPER Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 RUPER Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 RUPER Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 RUPER Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 RUPER Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 RUPER Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "ALLSURA Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 ALLSURA Sub-19", "media": 56, "valor": 0.6, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 ALLSURA Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 ALLSURA Sub-19", "media": 50, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 ALLSURA Sub-19", "media": 55, "valor": 0.5, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 ALLSURA Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 ALLSURA Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 ALLSURA Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 ALLSURA Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 ALLSURA Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 ALLSURA Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "ENERTO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 ENERTO Sub-19", "media": 55, "valor": 0.5, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 ENERTO Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 ENERTO Sub-19", "media": 49, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 ENERTO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 ENERTO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 ENERTO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 ENERTO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 ENERTO Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 ENERTO Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 ENERTO Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "TREO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 TREO Sub-19", "media": 55, "valor": 0.5, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 TREO Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 TREO Sub-19", "media": 49, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 TREO Sub-19", "media": 54, "valor": 0.4, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 TREO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 TREO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 TREO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 TREO Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 TREO Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 TREO Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "DOMELÍ Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 DOMEL Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 DOMEL Sub-19", "media": 51, "valor": 0.1, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 DOMEL Sub-19", "media": 48, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 DOMEL Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 DOMEL Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 DOMEL Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 DOMEL Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 DOMEL Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 DOMEL Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 DOMEL Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "DORRO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 DORRO Sub-19", "media": 54, "valor": 0.4, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 DORRO Sub-19", "media": 51, "valor": 0.1, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 DORRO Sub-19", "media": 48, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 DORRO Sub-19", "media": 53, "valor": 0.3, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 DORRO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 DORRO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 DORRO Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 DORRO Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 DORRO Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 DORRO Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "ASORPA Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 ASORPA Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 ASORPA Sub-19", "media": 50, "valor": 0.05, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 ASORPA Sub-19", "media": 47, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 ASORPA Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 ASORPA Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 ASORPA Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 ASORPA Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 ASORPA Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 ASORPA Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 ASORPA Sub-19", "media": 46, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "SABADERO Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 SABADERO Sub-19", "media": 53, "valor": 0.3, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 SABADERO Sub-19", "media": 50, "valor": 0.05, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 SABADERO Sub-19", "media": 47, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 SABADERO Sub-19", "media": 52, "valor": 0.2, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 SABADERO Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 SABADERO Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 SABADERO Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 SABADERO Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 SABADERO Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 SABADERO Sub-19", "media": 46, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "COCONUT Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 COCONUT Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 COCONUT Sub-19", "media": 49, "valor": 0.05, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 COCONUT Sub-19", "media": 46, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 COCONUT Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 COCONUT Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 COCONUT Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 COCONUT Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 COCONUT Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 COCONUT Sub-19", "media": 46, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 COCONUT Sub-19", "media": 45, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},
    "CHIMICHANGA Sub-19": {"liga": "Sub-19 1 División", "escudo": "⚪", "jugadores": [
        {"nombre": "Portero 1 CHIMICHANGA Sub-19", "media": 52, "valor": 0.2, "pos": "POR", "edad": 19},
        {"nombre": "Portero 2 CHIMICHANGA Sub-19", "media": 49, "valor": 0.05, "pos": "POR", "edad": 18},
        {"nombre": "Portero 3 CHIMICHANGA Sub-19", "media": 46, "valor": 0.05, "pos": "POR", "edad": 17},
        {"nombre": "Jugador 1 CHIMICHANGA Sub-19", "media": 51, "valor": 0.1, "pos": "JUG", "edad": 19},
        {"nombre": "Jugador 2 CHIMICHANGA Sub-19", "media": 50, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 3 CHIMICHANGA Sub-19", "media": 49, "valor": 0.05, "pos": "JUG", "edad": 18},
        {"nombre": "Jugador 4 CHIMICHANGA Sub-19", "media": 48, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 5 CHIMICHANGA Sub-19", "media": 47, "valor": 0.05, "pos": "JUG", "edad": 17},
        {"nombre": "Jugador 6 CHIMICHANGA Sub-19", "media": 46, "valor": 0.05, "pos": "JUG", "edad": 16},
        {"nombre": "Jugador 7 CHIMICHANGA Sub-19", "media": 45, "valor": 0.05, "pos": "JUG", "edad": 16}
    ]},

"IGLESIA Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 IGLESIA Sub-19", "media": 50, "valor": 0.9, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 IGLESIA Sub-19", "media": 47, "valor": 0.6, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 IGLESIA Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 IGLESIA Sub-19", "media": 49, "valor": 0.8, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 IGLESIA Sub-19", "media": 49, "valor": 0.7, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 IGLESIA Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 IGLESIA Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 IGLESIA Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 IGLESIA Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 IGLESIA Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 16}
]},
"POK Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 POK Sub-19", "media": 50, "valor": 0.9, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 POK Sub-19", "media": 47, "valor": 0.6, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 POK Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 POK Sub-19", "media": 49, "valor": 0.8, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 POK Sub-19", "media": 49, "valor": 0.7, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 POK Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 POK Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 POK Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 POK Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 POK Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 16}
]},
"SIBERIA Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 SIBERIA Sub-19", "media": 49, "valor": 0.8, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 SIBERIA Sub-19", "media": 47, "valor": 0.5, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 SIBERIA Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 SIBERIA Sub-19", "media": 49, "valor": 0.7, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 SIBERIA Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 SIBERIA Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 SIBERIA Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 SIBERIA Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 SIBERIA Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 SIBERIA Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 16}
]},
"SALMÓN Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 SALMÓN Sub-19", "media": 49, "valor": 0.8, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 SALMÓN Sub-19", "media": 47, "valor": 0.5, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 SALMÓN Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 SALMÓN Sub-19", "media": 49, "valor": 0.7, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 SALMÓN Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 SALMÓN Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 SALMÓN Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 SALMÓN Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 SALMÓN Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 SALMÓN Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 16}
]},
"ALTORPO Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ALTORPO Sub-19", "media": 49, "valor": 0.7, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ALTORPO Sub-19", "media": 46, "valor": 0.4, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ALTORPO Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ALTORPO Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ALTORPO Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ALTORPO Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ALTORPO Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ALTORPO Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ALTORPO Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ALTORPO Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"FROSTÉ Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 FROST Sub-19", "media": 49, "valor": 0.7, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 FROST Sub-19", "media": 46, "valor": 0.4, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 FROST Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 FROST Sub-19", "media": 47, "valor": 0.6, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 FROST Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 FROST Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 FROST Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 FROST Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 FROST Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 FROST Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"FEBRONTO Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 FEBRONTO Sub-19", "media": 47, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 FEBRONTO Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 FEBRONTO Sub-19", "media": 42, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 FEBRONTO Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 FEBRONTO Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 FEBRONTO Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 FEBRONTO Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 FEBRONTO Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 FEBRONTO Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 FEBRONTO Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"ABDUZCAN Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ABDUZCAN Sub-19", "media": 47, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ABDUZCAN Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ABDUZCAN Sub-19", "media": 42, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ABDUZCAN Sub-19", "media": 47, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ABDUZCAN Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ABDUZCAN Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ABDUZCAN Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ABDUZCAN Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ABDUZCAN Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ABDUZCAN Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"ANCO Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ANCO Sub-19", "media": 47, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ANCO Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ANCO Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ANCO Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ANCO Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ANCO Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ANCO Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ANCO Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ANCO Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ANCO Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"ZOQUIO Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ZOQUIO Sub-19", "media": 47, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ZOQUIO Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ZOQUIO Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ZOQUIO Sub-19", "media": 46, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ZOQUIO Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ZOQUIO Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ZOQUIO Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ZOQUIO Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ZOQUIO Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ZOQUIO Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"AGUEST Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 AGUEST Sub-19", "media": 46, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 AGUEST Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 AGUEST Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 AGUEST Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 AGUEST Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 AGUEST Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 AGUEST Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 AGUEST Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 AGUEST Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 AGUEST Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"ALFALFA Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ALFALFA Sub-19", "media": 46, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ALFALFA Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ALFALFA Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ALFALFA Sub-19", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ALFALFA Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ALFALFA Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ALFALFA Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ALFALFA Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ALFALFA Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ALFALFA Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"DENTOR Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 DENTOR Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 DENTOR Sub-19", "media": 42, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 DENTOR Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 DENTOR Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 DENTOR Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 DENTOR Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 DENTOR Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 DENTOR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 DENTOR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 DENTOR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"JOREVOS Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 JOREVOS Sub-19", "media": 45, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 JOREVOS Sub-19", "media": 42, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 JOREVOS Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 JOREVOS Sub-19", "media": 44, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 JOREVOS Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 JOREVOS Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 JOREVOS Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 JOREVOS Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 JOREVOS Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 JOREVOS Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"AMPRO Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 AMPRO Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 AMPRO Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 AMPRO Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 AMPRO Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 AMPRO Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 AMPRO Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 AMPRO Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 AMPRO Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 AMPRO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 AMPRO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"MERSOL Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 MERSOL Sub-19", "media": 44, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 MERSOL Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 MERSOL Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 MERSOL Sub-19", "media": 43, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 MERSOL Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 MERSOL Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 MERSOL Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 MERSOL Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 MERSOL Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 MERSOL Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"NÁCOR Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 NCOR Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 NCOR Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 NCOR Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 NCOR Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 NCOR Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 NCOR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 NCOR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 NCOR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 NCOR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 NCOR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"XEMAR Sub-19": {"liga": "Sub-19 2 División", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 XEMAR Sub-19", "media": 43, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 XEMAR Sub-19", "media": 41, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 XEMAR Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 XEMAR Sub-19", "media": 43, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 XEMAR Sub-19", "media": 42, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 XEMAR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 XEMAR Sub-19", "media": 41, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 XEMAR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 XEMAR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 XEMAR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16}
]},

"LOCKE Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 LOCKE Sub-19", "media": 45, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 LOCKE Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 LOCKE Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 LOCKE Sub-19", "media": 44, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 LOCKE Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 LOCKE Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 LOCKE Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 LOCKE Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 LOCKE Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 LOCKE Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"MARTERO Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 MARTERO Sub-19", "media": 45, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 MARTERO Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 MARTERO Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 MARTERO Sub-19", "media": 44, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 MARTERO Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 MARTERO Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 MARTERO Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 MARTERO Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 MARTERO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 MARTERO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"SCAR Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 SCAR Sub-19", "media": 44, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 SCAR Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 SCAR Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 SCAR Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 SCAR Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 SCAR Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 SCAR Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 SCAR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 SCAR Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 SCAR Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"FOL Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 FOL Sub-19", "media": 44, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 FOL Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 FOL Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 FOL Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 FOL Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 FOL Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 FOL Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 FOL Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 FOL Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 FOL Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"BLOX Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 BLOX Sub-19", "media": 43, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 BLOX Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 BLOX Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 BLOX Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 BLOX Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 BLOX Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 BLOX Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 BLOX Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 BLOX Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 BLOX Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"VILLAPORRINO Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 VILLAPORRINO Sub-19", "media": 43, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 VILLAPORRINO Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 VILLAPORRINO Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 VILLAPORRINO Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 VILLAPORRINO Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 VILLAPORRINO Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 VILLAPORRINO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 VILLAPORRINO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 VILLAPORRINO Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 VILLAPORRINO Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"FIF Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 FIF Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 FIF Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 FIF Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 FIF Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 FIF Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 FIF Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 FIF Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 FIF Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 FIF Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 FIF Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"MINE Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 MINE Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 MINE Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 MINE Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 MINE Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 MINE Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 MINE Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 MINE Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 MINE Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 MINE Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 MINE Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"JULÍN Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 JULN Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 JULN Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 JULN Sub-19", "media": 36, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 JULN Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 JULN Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 JULN Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 JULN Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 JULN Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 JULN Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 JULN Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"BOLONCHO Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 BOLONCHO Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 BOLONCHO Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 BOLONCHO Sub-19", "media": 36, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 BOLONCHO Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 BOLONCHO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 BOLONCHO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 BOLONCHO Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 BOLONCHO Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 BOLONCHO Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 BOLONCHO Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"VORNES Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 VORNES Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 VORNES Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 VORNES Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 VORNES Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 VORNES Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 VORNES Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 VORNES Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 VORNES Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 VORNES Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 VORNES Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"MOJI Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 MOJI Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 MOJI Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 MOJI Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 MOJI Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 MOJI Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 MOJI Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 MOJI Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 MOJI Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 MOJI Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 MOJI Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"COF Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 COF Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 COF Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 COF Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 COF Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 COF Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 COF Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 COF Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 COF Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 COF Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 COF Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"HUNGARIA Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 HUNGARIA Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 HUNGARIA Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 HUNGARIA Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 HUNGARIA Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 HUNGARIA Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 HUNGARIA Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 HUNGARIA Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 HUNGARIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 HUNGARIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 HUNGARIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"POLANDIA Sub-19": {"liga": "Sub-19 3 División Grupo A", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 POLANDIA Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 POLANDIA Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 POLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 POLANDIA Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 POLANDIA Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 POLANDIA Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 POLANDIA Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 POLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 POLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 POLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},

"PER Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 PER Sub-19", "media": 45, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 PER Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 PER Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 PER Sub-19", "media": 44, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 PER Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 PER Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 PER Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 PER Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 PER Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 PER Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"PICO Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 PICO Sub-19", "media": 45, "valor": 0.6, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 PICO Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 PICO Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 PICO Sub-19", "media": 44, "valor": 0.5, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 PICO Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 PICO Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 PICO Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 PICO Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 PICO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 PICO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"XD Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 XD Sub-19", "media": 44, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 XD Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 XD Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 XD Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 XD Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 XD Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 XD Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 XD Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 XD Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 XD Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"UH Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 UH Sub-19", "media": 44, "valor": 0.5, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 UH Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 UH Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 UH Sub-19", "media": 43, "valor": 0.4, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 UH Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 UH Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 UH Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 UH Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 UH Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 UH Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"DUTE Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 DUTE Sub-19", "media": 43, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 DUTE Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 DUTE Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 DUTE Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 DUTE Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 DUTE Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 DUTE Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 DUTE Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 DUTE Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 DUTE Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"GAMBI Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 GAMBI Sub-19", "media": 43, "valor": 0.4, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 GAMBI Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 GAMBI Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 GAMBI Sub-19", "media": 42, "valor": 0.3, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 GAMBI Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 GAMBI Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 GAMBI Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 GAMBI Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 GAMBI Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 GAMBI Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"MACAGUADAN Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 MACAGUADAN Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 MACAGUADAN Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 MACAGUADAN Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 MACAGUADAN Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 MACAGUADAN Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 MACAGUADAN Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 MACAGUADAN Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 MACAGUADAN Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 MACAGUADAN Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 MACAGUADAN Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"TORE Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 TORE Sub-19", "media": 42, "valor": 0.3, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 TORE Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 TORE Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 TORE Sub-19", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 TORE Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 TORE Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 TORE Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 TORE Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 TORE Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 TORE Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"BANANO Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 BANANO Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 BANANO Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 BANANO Sub-19", "media": 36, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 BANANO Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 BANANO Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 BANANO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 BANANO Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 BANANO Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 BANANO Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 BANANO Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"AM Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 AM Sub-19", "media": 42, "valor": 0.2, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 AM Sub-19", "media": 39, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 AM Sub-19", "media": 36, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 AM Sub-19", "media": 41, "valor": 0.1, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 AM Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 AM Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 AM Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 AM Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 AM Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 AM Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"FORT Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 FORT Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 FORT Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 FORT Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 FORT Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 FORT Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 FORT Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 FORT Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 FORT Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 FORT Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 FORT Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"STOR Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 STOR Sub-19", "media": 41, "valor": 0.1, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 STOR Sub-19", "media": 38, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 STOR Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 STOR Sub-19", "media": 40, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 STOR Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 STOR Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 STOR Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 STOR Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 STOR Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 STOR Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"ROMPH Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 ROMPH Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 ROMPH Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 ROMPH Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 ROMPH Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 ROMPH Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 ROMPH Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 ROMPH Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 ROMPH Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 ROMPH Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 ROMPH Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
"NEDERLANDIA Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 NEDERLANDIA Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 NEDERLANDIA Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 NEDERLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 NEDERLANDIA Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 NEDERLANDIA Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 NEDERLANDIA Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 NEDERLANDIA Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 NEDERLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 NEDERLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 NEDERLANDIA Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},

"EKIPO Sub-19": {"liga": "Sub-19 3 División Grupo B", "escudo": "⚪", "jugadores": [
    {"nombre": "Portero 1 EKIPO Sub-19", "media": 40, "valor": 0.05, "pos": "POR", "edad": 19},
    {"nombre": "Portero 2 EKIPO Sub-19", "media": 37, "valor": 0.05, "pos": "POR", "edad": 18},
    {"nombre": "Portero 3 EKIPO Sub-19", "media": 35, "valor": 0.05, "pos": "POR", "edad": 17},
    {"nombre": "Jugador 1 EKIPO Sub-19", "media": 39, "valor": 0.05, "pos": "JUG", "edad": 19},
    {"nombre": "Jugador 2 EKIPO Sub-19", "media": 38, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 3 EKIPO Sub-19", "media": 37, "valor": 0.05, "pos": "JUG", "edad": 18},
    {"nombre": "Jugador 4 EKIPO Sub-19", "media": 36, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 5 EKIPO Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 17},
    {"nombre": "Jugador 6 EKIPO Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16},
    {"nombre": "Jugador 7 EKIPO Sub-19", "media": 35, "valor": 0.05, "pos": "JUG", "edad": 16}
]},
        "RB Zerkas": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Isma Carbonell", "media": 72, "valor": 1, "pos": "POR", "edad": 27, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Juan", "media": 78, "valor": 8, "pos": "JUG", "edad": 28, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "David", "media": 80, "valor": 15, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Carlos Ruiz", "media": 74, "valor": 4, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Adri", "media": 76, "valor": 6, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Lorenzo", "media": 74, "valor": 4, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Saulo": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Dani", "media": 79, "valor": 10, "pos": "POR", "edad": 26, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Antonio", "media": 78, "valor": 9, "pos": "JUG", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Congrão", "media": 79, "valor": 11, "pos": "JUG", "edad": 20, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
                {"nombre": "Íñigo Ariza", "media": 75, "valor": 5, "pos": "POR", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Montoya", "media": 73, "valor": 3, "pos": "JUG", "edad": 20, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Stephen", "media": 73, "valor": 3, "pos": "JUG", "edad": 18, "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"], "nacionalidades": ["inglesa"]},
            ]
        },
        "Tordón": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Mena", "media": 76, "valor": 6, "pos": "POR", "edad": 31, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Rubén Vázquez", "media": 74, "valor": 4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Fernando De la Cruz", "media": 78, "valor": 9, "pos": "JUG", "edad": 28, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "César Quintana", "media": 73, "valor": 3, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Ángel", "media": 73, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Manu Duque", "media": 74, "valor": 4, "pos": "JUG", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
            ]
        },
        "Tervo": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Luis Amado", "media": 78, "valor": 8, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Salas", "media": 79, "valor": 10, "pos": "JUG", "edad": 22, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "Ávila", "media": 78, "valor": 8, "pos": "JUG", "edad": 25, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Edison Solís", "media": 73, "valor": 3, "pos": "POR", "edad": 21, "banderas": ["🇪🇨"], "nacionalidades": ["ecuatoriana"]},
                {"nombre": "Miguel Heras", "media": 73, "valor": 3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Keint", "media": 72, "valor": 2, "pos": "JUG", "edad": 17, "banderas": ["🇫🇷"], "nacionalidades": ["francesa"]},
            ]
        },
        "Glanto": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Piñeiro", "media": 77, "valor": 7, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Rivas", "media": 78, "valor": 8, "pos": "JUG", "edad": 24, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "François", "media": 77, "valor": 7, "pos": "JUG", "edad": 29, "banderas": ["🇺🇸"], "nacionalidades": ["estadounidense"]},
                {"nombre": "Ricardo Diaby", "media": 74, "valor": 4, "pos": "POR", "edad": 22, "banderas": ["🇱🇨", "🇲🇱"], "nacionalidades": ["folimonense", "malí"]},
                {"nombre": "Edu", "media": 73, "valor": 3, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Rodri", "media": 73, "valor": 3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
        "Absuka": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Jorge", "media": 78, "valor": 8, "pos": "POR", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Felipe", "media": 77, "valor": 7, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Veixão", "media": 77, "valor": 7, "pos": "JUG", "edad": 19, "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
                {"nombre": "Rav Lomwijk", "media": 74, "valor": 4, "pos": "POR", "edad": 23, "banderas": ["🇳🇱"], "nacionalidades": ["neerlandesa"]},
                {"nombre": "Tomi", "media": 73, "valor": 3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Andrés", "media": 72, "valor": 2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Zalmoa": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Orlic", "media": 76, "valor": 6, "pos": "POR", "edad": 28, "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"], "nacionalidades": ["inglesa"]},
                {"nombre": "Luis", "media": 78, "valor": 8, "pos": "JUG", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Alberto", "media": 77, "valor": 7, "pos": "JUG", "edad": 26, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Niklas Behrens", "media": 73, "valor": 3, "pos": "POR", "edad": 24, "banderas": ["🇩🇪"], "nacionalidades": ["alemana"]},
                {"nombre": "Leo", "media": 72, "valor": 2, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Miguel", "media": 73, "valor": 3, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Folfo": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Bruno", "media": 77, "valor": 7, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Mario", "media": 76, "valor": 6, "pos": "JUG", "edad": 28, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ángel", "media": 75, "valor": 5, "pos": "JUG", "edad": 27, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Anderson Gallese", "media": 72, "valor": 2, "pos": "POR", "edad": 25, "banderas": ["🇵🇪"], "nacionalidades": ["peruana"]},
                {"nombre": "Lopes", "media": 74, "valor": 4, "pos": "JUG", "edad": 22, "banderas": ["🇨🇻"], "nacionalidades": ["caboverdiana"]},
                {"nombre": "Lozano", "media": 74, "valor": 4, "pos": "JUG", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Zorla": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Enric", "media": 75, "valor": 5, "pos": "POR", "edad": 28, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Olmedo", "media": 76, "valor": 6, "pos": "JUG", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Roger", "media": 75, "valor": 5, "pos": "JUG", "edad": 22, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "Ángel Carmona", "media": 73, "valor": 3, "pos": "POR", "edad": 26, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ali Sollie", "media": 72, "valor": 2, "pos": "JUG", "edad": 17, "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"], "nacionalidades": ["inglesa"]},
                {"nombre": "Julio", "media": 71, "valor": 1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Toquero": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Kevin", "media": 77, "valor": 7, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Eric", "media": 75, "valor": 5, "pos": "JUG", "edad": 28, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Miquel", "media": 76, "valor": 6, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Florent Sahiti", "media": 71, "valor": 1, "pos": "POR", "edad": 22, "banderas": ["🇽🇰"], "nacionalidades": ["kosovar"]},
                {"nombre": "Clemente", "media": 73, "valor": 3, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Narváez", "media": 72, "valor": 2, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Stung": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Peralta", "media": 74, "valor": 4, "pos": "POR", "edad": 32, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Hicham", "media": 76, "valor": 6, "pos": "JUG", "edad": 22, "banderas": ["🇩🇿"], "nacionalidades": ["argelina"]},
                {"nombre": "Bonilla", "media": 74, "valor": 4, "pos": "JUG", "edad": 23, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Pablo Sandoval", "media": 72, "valor": 2, "pos": "POR", "edad": 29, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Segarra", "media": 73, "valor": 3, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Joel", "media": 72, "valor": 2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Borca": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Ojeda", "media": 75, "valor": 5, "pos": "POR", "edad": 25, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Mourad", "media": 74, "valor": 4, "pos": "JUG", "edad": 19, "banderas": ["🇲🇦"], "nacionalidades": ["marroquí"]},
                {"nombre": "Mateo", "media": 74, "valor": 4, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Martin Mathisen", "media": 73, "valor": 3, "pos": "POR", "edad": 25, "banderas": ["🇩🇰"], "nacionalidades": ["danesa"]},
                {"nombre": "Chavez", "media": 71, "valor": 1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Portillo", "media": 72, "valor": 2, "pos": "JUG", "edad": 19, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
            ]
        },
        "Vilaporto": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Lucas", "media": 78, "valor": 8, "pos": "POR", "edad": 24, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Pedro", "media": 76, "valor": 6, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Padrón", "media": 74, "valor": 4, "pos": "JUG", "edad": 27, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Marcos Ramírez", "media": 74, "valor": 4, "pos": "POR", "edad": 26, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Carlos", "media": 73, "valor": 3, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Bennet", "media": 73, "valor": 3, "pos": "JUG", "edad": 21, "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"], "nacionalidades": ["inglesa"]},
            ]
        },
        "Caurto": {
            "liga": "Com 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Pardo", "media": 75, "valor": 5, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Alex", "media": 76, "valor": 6, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Montiel", "media": 75, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Aarón Carrión", "media": 73, "valor": 3, "pos": "POR", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Jesús", "media": 74, "valor": 4, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Rubio", "media": 72, "valor": 2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "RB Zerkas B": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "RBZ B Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "RBZ B Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "RBZ B Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "RBZ B Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "RBZ B Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "RBZ B Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Quimbalú": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Quimbalú Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Quimbalú Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Quimbalú Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Quimbalú Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Quimbalú Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Quimbalú Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Cartuba": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Cartuba Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Cartuba Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Cartuba Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Cartuba Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Cartuba Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Cartuba Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Danesio": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Danesio Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Danesio Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Danesio Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Danesio Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Danesio Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Danesio Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Tencla": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Tencla Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Tencla Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Tencla Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Tencla Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Tencla Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Tencla Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Pineto": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Pineto Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Pineto Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Pineto Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Pineto Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Pineto Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Pineto Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Sembencín": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Sembencín Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Sembencín Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Sembencín Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Sembencín Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Sembencín Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Sembencín Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Ceuta": {
            "liga": "Com 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Ceuta Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ceuta Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ceuta Jugador 1", "media": 69, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ceuta Jugador 2", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ceuta Jugador 3", "media": 67, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Ceuta Jugador 4", "media": 66, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
"RB Zerkas Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "RBZ S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "RBZ S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Saulo Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Saulo S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Saulo S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Tordón Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Tordón S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tordón S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Tervo Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Tervo S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tervo S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Glanto Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Glanto S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Glanto S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Absuka Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Absuka S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Absuka S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Zalmoa Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Zalmoa S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zalmoa S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Folfo Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folfo S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Folfo S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Zorla Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Zorla S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Zorla S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Toquero Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Toquero S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Toquero S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Stung Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Stung S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Stung S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Borca Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Borca S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Borca S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Vilaporto Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Vilaporto S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Vilaporto S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Caurto Sub-19": {
    "liga": "Com Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Caurto S19 Portero 1", "media": 54, "valor": 0.5, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Portero 2", "media": 52, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Portero 3", "media": 50, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 1", "media": 55, "valor": 0.6, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 2", "media": 54, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 3", "media": 53, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 4", "media": 52, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 5", "media": 51, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 6", "media": 50, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Caurto S19 Jugador 7", "media": 49, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Quimbalú Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Quimbalú S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Quimbalú S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Cartuba Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Cartuba S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Cartuba S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Danesio Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Danesio S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Danesio S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Tencla Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Tencla S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tencla S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Pineto Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Pineto S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Pineto S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Sembencín Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Sembencín S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Sembencín S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Ceuta Sub-19": {
    "liga": "Com Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Ceuta S19 Portero 1", "media": 47, "valor": 0.3, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Portero 2", "media": 42, "valor": 0.2, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Portero 3", "media": 38, "valor": 0.1, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 1", "media": 50, "valor": 0.4, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 2", "media": 47, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 3", "media": 45, "valor": 0.2, "pos": "JUG", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 4", "media": 42, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 5", "media": 40, "valor": 0.1, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 6", "media": 38, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Ceuta S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
        "Tasón": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Ahmed Al-Saleh", "media": 74, "valor": 6, "pos": "POR", "edad": 25, "banderas": ["🇸🇦"], "nacionalidades": ["saudí"]},
                {"nombre": "Sergio Martínez", "media": 76, "valor": 8, "pos": "JUG", "edad": 28, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Alejandro Sánchez", "media": 74, "valor": 6, "pos": "JUG", "edad": 27, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Mbenga", "media": 68, "valor": 1, "pos": "POR", "edad": 19, "banderas": ["🇨🇩"], "nacionalidades": ["congoleña"]},
                {"nombre": "Javier Torres", "media": 72, "valor": 4, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Alejandro López", "media": 71, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Albicans": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Pablo Fernández", "media": 79, "valor": 10, "pos": "POR", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Lucas Fernández", "media": 75, "valor": 6, "pos": "JUG", "edad": 30, "banderas": ["🇦🇷"], "nacionalidades": ["argentina"]},
                {"nombre": "Popov", "media": 77, "valor": 8, "pos": "JUG", "edad": 21, "banderas": ["🇷🇺"], "nacionalidades": ["rusa"]},
                {"nombre": "Pablo Hernández", "media": 74, "valor": 5, "pos": "POR", "edad": 31, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Juan Torres", "media": 71, "valor": 3, "pos": "JUG", "edad": 26, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Francisco Romero", "media": 70, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
        "Cosmo": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Adamu Suleiman", "media": 81, "valor": 12, "pos": "POR", "edad": 23, "banderas": ["🇳🇬"], "nacionalidades": ["nigeriana"]},
                {"nombre": "Alex Fernández", "media": 76, "valor": 6, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Luca Bianchi", "media": 73, "valor": 4, "pos": "JUG", "edad": 29, "banderas": ["🇮🇹"], "nacionalidades": ["italiana"]},
                {"nombre": "Juanca Martínez", "media": 72, "valor": 3, "pos": "POR", "edad": 25, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "El Khoury", "media": 74, "valor": 5, "pos": "JUG", "edad": 27, "banderas": ["🇲🇦"], "nacionalidades": ["marroquí"]},
                {"nombre": "Gonzalo Fernández", "media": 74, "valor": 5, "pos": "JUG", "edad": 26, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
            ]
        },
        "Larano": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Santi Gómez", "media": 74, "valor": 6, "pos": "POR", "edad": 27, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Mamadou Diallo", "media": 73, "valor": 5, "pos": "JUG", "edad": 20, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
                {"nombre": "Silva", "media": 76, "valor": 7, "pos": "JUG", "edad": 31, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Alcaraz", "media": 71, "valor": 3, "pos": "POR", "edad": 30, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Llabrés", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Zurraque", "media": 73, "valor": 5, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
            ]
        },
        "Corpazo": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Costa", "media": 72, "valor": 3, "pos": "POR", "edad": 29, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
                {"nombre": "Raúl Sánchez", "media": 70, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Nowak", "media": 74, "valor": 5, "pos": "JUG", "edad": 27, "banderas": ["🇵🇱"], "nacionalidades": ["polaca"]},
                {"nombre": "Adamu Bello", "media": 70, "valor": 2, "pos": "POR", "edad": 21, "banderas": ["🇦🇬", "🇳🇬"], "nacionalidades": ["tenguana", "nigeriana"]},
                {"nombre": "Alberto Ruiz", "media": 68, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Rosado", "media": 72, "valor": 3, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
        "Selonda": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Manu García", "media": 72, "valor": 4, "pos": "POR", "edad": 30, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Hugo Gomes", "media": 73, "valor": 5, "pos": "JUG", "edad": 26, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
                {"nombre": "Issa Diallo", "media": 72, "valor": 4, "pos": "JUG", "edad": 21, "banderas": ["🇧🇫", "🇦🇬"], "nacionalidades": ["burkinesa", "tenguana"]},
                {"nombre": "Pedro Ramos", "media": 70, "valor": 2, "pos": "POR", "edad": 29, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Luis González", "media": 71, "valor": 3, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Pablo Pastor", "media": 72, "valor": 4, "pos": "JUG", "edad": 24, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
            ]
        },
        "Chiva": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Pedro Morales", "media": 73, "valor": 5, "pos": "POR", "edad": 29, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Miguel López", "media": 76, "valor": 7, "pos": "JUG", "edad": 26, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Miki Sánchez", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Antonio Silva", "media": 71, "valor": 3, "pos": "POR", "edad": 27, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Ahmed Hassam", "media": 71, "valor": 3, "pos": "JUG", "edad": 21, "banderas": ["🇪🇬"], "nacionalidades": ["egipcia"]},
                {"nombre": "Aliou Diallo", "media": 72, "valor": 4, "pos": "JUG", "edad": 22, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
            ]
        },
        "Cristo": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Alberto Francés", "media": 72, "valor": 4, "pos": "POR", "edad": 28, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Enrico Nove", "media": 71, "valor": 3, "pos": "JUG", "edad": 25, "banderas": ["🇮🇹"], "nacionalidades": ["italiana"]},
                {"nombre": "Héctor Corberán", "media": 74, "valor": 5, "pos": "JUG", "edad": 31, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Pau Soria", "media": 70, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Rafa Ñíguez", "media": 69, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Chinedu Okoro", "media": 69, "valor": 1, "pos": "JUG", "edad": 23, "banderas": ["🇳🇬"], "nacionalidades": ["nigeriana"]},
            ]
        },
        "Hispetón": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Manuel Chico", "media": 70, "valor": 2, "pos": "POR", "edad": 25, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
                {"nombre": "Eneko Estrada", "media": 73, "valor": 5, "pos": "JUG", "edad": 27, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Marc Mas", "media": 70, "valor": 2, "pos": "JUG", "edad": 28, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Maicon Anderson", "media": 69, "valor": 1, "pos": "POR", "edad": 28, "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
                {"nombre": "Ryotaro Hoshi", "media": 69, "valor": 1, "pos": "JUG", "edad": 24, "banderas": ["🇯🇵"], "nacionalidades": ["japonesa"]},
                {"nombre": "Emilio Engonga", "media": 70, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇬🇶"], "nacionalidades": ["ecuatoguineana"]},
            ]
        },
        "Intes": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Antoine Manomey", "media": 72, "valor": 4, "pos": "POR", "edad": 23, "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
                {"nombre": "Dani Galán", "media": 71, "valor": 3, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Pedro Cuadrado", "media": 70, "valor": 2, "pos": "JUG", "edad": 28, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Alberto Guirao", "media": 70, "valor": 2, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Jaime Tresaco", "media": 70, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Rubén Ruiz", "media": 69, "valor": 1, "pos": "JUG", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
            ]
        },
        "Vástico": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Rodrigo Sayol", "media": 71, "valor": 3, "pos": "POR", "edad": 20, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Jane Mbeki", "media": 72, "valor": 4, "pos": "JUG", "edad": 24, "banderas": ["🇿🇦"], "nacionalidades": ["sudafricana"]},
                {"nombre": "Amadou Diop", "media": 71, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
                {"nombre": "Alejandro Fernández", "media": 69, "valor": 1, "pos": "POR", "edad": 29, "banderas": ["🇦🇷"], "nacionalidades": ["argentina"]},
                {"nombre": "Ángel Riera", "media": 70, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Raúl Olmo", "media": 69, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
        "Basufo": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Dedé Guilherme", "media": 74, "valor": 5, "pos": "POR", "edad": 25, "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
                {"nombre": "Devin Pierluisi", "media": 69, "valor": 1, "pos": "JUG", "edad": 23, "banderas": ["🇵🇷"], "nacionalidades": ["puertorriqueña"]},
                {"nombre": "Martín Aquino", "media": 70, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "César Mozo", "media": 72, "valor": 3, "pos": "POR", "edad": 26, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Marco Méndez", "media": 70, "valor": 2, "pos": "JUG", "edad": 28, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Roberto Hermoso", "media": 69, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
        "Lopio": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Aritz Franquesa", "media": 72, "valor": 4, "pos": "POR", "edad": 28, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "Michael Mascarenhas", "media": 69, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇬🇮"], "nacionalidades": ["gibraltareña"]},
                {"nombre": "Manu Pino", "media": 72, "valor": 4, "pos": "JUG", "edad": 29, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Mateo Sánchez", "media": 70, "valor": 2, "pos": "POR", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Tariq Al-Farsi", "media": 69, "valor": 1, "pos": "JUG", "edad": 23, "banderas": ["🇶🇦"], "nacionalidades": ["qatarí"]},
                {"nombre": "Marvin Kospo", "media": 69, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇨🇭"], "nacionalidades": ["suiza"]},
            ]
        },
        "Botabú": {
            "liga": "Tengu 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Paolo Bueno", "media": 70, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Brais Soler", "media": 72, "valor": 3, "pos": "JUG", "edad": 29, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Álex Porro", "media": 72, "valor": 3, "pos": "JUG", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Sergio Valle", "media": 70, "valor": 2, "pos": "POR", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Antonis Bouchalakis", "media": 70, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇬🇷"], "nacionalidades": ["griega"]},
                {"nombre": "Kobi Solomon", "media": 68, "valor": 1, "pos": "JUG", "edad": 19, "banderas": ["🇮🇱"], "nacionalidades": ["israelí"]},
            ]
        },
        "Villaverde": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Villaverde Portero 1", "media": 68, "valor": 3, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Villaverde Portero 2", "media": 66, "valor": 2, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Villaverde Jugador 1", "media": 68, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Villaverde Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Villaverde Jugador 3", "media": 66, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Villaverde Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Albicans B": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Albicans B Portero 1", "media": 68, "valor": 3, "pos": "POR", "edad": 23, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Albicans B Portero 2", "media": 66, "valor": 2, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Albicans B Jugador 1", "media": 68, "valor": 3, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Albicans B Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇦🇷"], "nacionalidades": ["argentina"]},
                {"nombre": "Albicans B Jugador 3", "media": 66, "valor": 2, "pos": "JUG", "edad": 20, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Albicans B Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Colario": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Colario Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Colario Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Colario Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Colario Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Colario Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Colario Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Axómera": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Axómera Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Axómera Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Axómera Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇬🇷"], "nacionalidades": ["griega"]},
                {"nombre": "Axómera Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Axómera Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Axómera Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Paramonte": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Paramonte Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 25, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Paramonte Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Paramonte Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
                {"nombre": "Paramonte Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Paramonte Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Paramonte Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Lutra": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Lutra Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Lutra Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Lutra Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇿🇦"], "nacionalidades": ["sudafricana"]},
                {"nombre": "Lutra Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Lutra Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Lutra Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Rilicu": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Rilicu Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Rilicu Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Rilicu Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Rilicu Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
                {"nombre": "Rilicu Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Rilicu Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },

        "Lemel": {
            "liga": "Tengu 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Lemel Portero 1", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Lemel Portero 2", "media": 66, "valor": 1, "pos": "POR", "edad": 21, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},

                {"nombre": "Lemel Jugador 1", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
                {"nombre": "Lemel Jugador 2", "media": 67, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
                {"nombre": "Lemel Jugador 3", "media": 66, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Lemel Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 20, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
            ]
        },
"Tasón Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Tasón S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Tasón S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Tasón S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Tasón S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Albicans Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Albicans S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Albicans S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Albicans S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Albicans S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Albicans S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇷"], "nacionalidades": ["argentina"]},
        {"nombre": "Albicans S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇷🇺"], "nacionalidades": ["rusa"]},
        {"nombre": "Albicans S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Albicans S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Albicans S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Albicans S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Cosmo Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Cosmo S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cosmo S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cosmo S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cosmo S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇳🇬"], "nacionalidades": ["nigeriana"]},
        {"nombre": "Cosmo S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cosmo S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇮🇹"], "nacionalidades": ["italiana"]},
        {"nombre": "Cosmo S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Cosmo S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇲🇦"], "nacionalidades": ["marroquí"]},
        {"nombre": "Cosmo S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cosmo S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Larano Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Larano S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Larano S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Larano S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Larano S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Larano S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
        {"nombre": "Larano S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Larano S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Larano S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Larano S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Larano S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Corpazo Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Corpazo S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
        {"nombre": "Corpazo S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
        {"nombre": "Corpazo S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Corpazo S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Corpazo S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇵🇱"], "nacionalidades": ["polaca"]},
        {"nombre": "Corpazo S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Corpazo S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇳🇬"], "nacionalidades": ["nigeriana"]},
        {"nombre": "Corpazo S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Corpazo S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Corpazo S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Selonda Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Selonda S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Selonda S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
        {"nombre": "Selonda S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇧🇫"], "nacionalidades": ["burkinesa"]},
        {"nombre": "Selonda S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Selonda S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
        {"nombre": "Selonda S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇫"], "nacionalidades": ["burkinesa"]},
        {"nombre": "Selonda S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Selonda S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Selonda S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Selonda S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Chiva Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Chiva S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Chiva S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Chiva S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Chiva S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Chiva S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Chiva S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Chiva S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇪🇬"], "nacionalidades": ["egipcia"]},
        {"nombre": "Chiva S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
        {"nombre": "Chiva S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Chiva S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Cristo Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Cristo S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇮🇹"], "nacionalidades": ["italiana"]},
        {"nombre": "Cristo S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Cristo S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Cristo S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇳🇬"], "nacionalidades": ["nigeriana"]},
        {"nombre": "Cristo S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Hispetón Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Hispetón S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Hispetón S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Hispetón S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Hispetón S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Hispetón S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Hispetón S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
        {"nombre": "Hispetón S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇯🇵"], "nacionalidades": ["japonesa"]},
        {"nombre": "Hispetón S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇬🇶"], "nacionalidades": ["ecuatoguineana"]},
        {"nombre": "Hispetón S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Hispetón S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Intes Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Intes S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
        {"nombre": "Intes S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
        {"nombre": "Intes S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Intes S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Intes S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Intes S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Intes S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Intes S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Intes S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Intes S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Vástico Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Vástico S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Vástico S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇿🇦"], "nacionalidades": ["sudafricana"]},
        {"nombre": "Vástico S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
        {"nombre": "Vástico S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇷"], "nacionalidades": ["argentina"]},
        {"nombre": "Vástico S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Vástico S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Vástico S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Vástico S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Vástico S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Vástico S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Basufo Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Basufo S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
        {"nombre": "Basufo S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇵🇷"], "nacionalidades": ["puertorriqueña"]},
        {"nombre": "Basufo S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Basufo S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Basufo S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
        {"nombre": "Basufo S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Basufo S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Basufo S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Basufo S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Basufo S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    ]
},
"Lopio Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Lopio S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
        {"nombre": "Lopio S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇬🇮"], "nacionalidades": ["gibraltareña"]},
        {"nombre": "Lopio S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lopio S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lopio S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lopio S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lopio S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lopio S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇶🇦"], "nacionalidades": ["qatarí"]},
        {"nombre": "Lopio S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇨🇭"], "nacionalidades": ["suiza"]},
        {"nombre": "Lopio S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Botabú Sub-19": {
    "liga": "Tengu Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Botabú S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Botabú S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Botabú S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Botabú S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Botabú S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Botabú S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Botabú S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Botabú S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇬🇷"], "nacionalidades": ["griega"]},
        {"nombre": "Botabú S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇮🇱"], "nacionalidades": ["israelí"]},
        {"nombre": "Botabú S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Villaverde Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Villaverde S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Villaverde S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Villaverde S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Villaverde S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Colario Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Colario S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Colario S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Colario S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Colario S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Colario S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Axómera Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Axómera S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇬🇷"], "nacionalidades": ["griega"]},
        {"nombre": "Axómera S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Axómera S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Axómera S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Axómera S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Paramonte Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Paramonte S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
        {"nombre": "Paramonte S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Paramonte S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Paramonte S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Paramonte S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Lutra Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Lutra S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇿🇦"], "nacionalidades": ["sudafricana"]},
        {"nombre": "Lutra S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Lutra S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Lutra S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lutra S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Rilicu Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Rilicu S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Rilicu S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
        {"nombre": "Rilicu S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Rilicu S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Rilicu S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
"Lemel Sub-19": {
    "liga": "Tengu Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Lemel S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
        {"nombre": "Lemel S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Lemel S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
        {"nombre": "Lemel S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
        {"nombre": "Lemel S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
    ]
},
        "EQUIPO_FOLIMON_1": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 1 Portero 1", "media": 78, "valor": 5, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 1 Jugador 1", "media": 79, "valor": 7, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 1 Jugador 2", "media": 76, "valor": 5, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 1 Portero 2", "media": 72, "valor": 3, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 1 Jugador 3", "media": 74, "valor": 4, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 1 Jugador 4", "media": 70, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2 Portero 1", "media": 77, "valor": 5, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2 Jugador 1", "media": 78, "valor": 6, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2 Jugador 2", "media": 74, "valor": 4, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2 Portero 2", "media": 70, "valor": 2, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2 Jugador 3", "media": 72, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2 Jugador 4", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_3": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 3 Portero 1", "media": 79, "valor": 6, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 3 Jugador 1", "media": 79, "valor": 7, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 3 Jugador 2", "media": 77, "valor": 5, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 3 Portero 2", "media": 73, "valor": 3, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 3 Jugador 3", "media": 75, "valor": 4, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 3 Jugador 4", "media": 71, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_4": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 4 Portero 1", "media": 75, "valor": 5, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 4 Jugador 1", "media": 76, "valor": 6, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 4 Jugador 2", "media": 73, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 4 Portero 2", "media": 68, "valor": 2, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 4 Jugador 3", "media": 71, "valor": 3, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 4 Jugador 4", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_5": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 5 Portero 1", "media": 78, "valor": 6, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 5 Jugador 1", "media": 78, "valor": 7, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 5 Jugador 2", "media": 75, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 5 Portero 2", "media": 71, "valor": 3, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 5 Jugador 3", "media": 73, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 5 Jugador 4", "media": 69, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_6": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 6 Portero 1", "media": 74, "valor": 5, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 6 Jugador 1", "media": 75, "valor": 6, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 6 Jugador 2", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 6 Portero 2", "media": 67, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 6 Jugador 3", "media": 70, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 6 Jugador 4", "media": 66, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_7": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 7 Portero 1", "media": 77, "valor": 6, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 7 Jugador 1", "media": 77, "valor": 7, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 7 Jugador 2", "media": 74, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 7 Portero 2", "media": 70, "valor": 3, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 7 Jugador 3", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 7 Jugador 4", "media": 68, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_8": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 8 Portero 1", "media": 76, "valor": 5, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 8 Jugador 1", "media": 76, "valor": 6, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 8 Jugador 2", "media": 73, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 8 Portero 2", "media": 69, "valor": 2, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 8 Jugador 3", "media": 71, "valor": 3, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 8 Jugador 4", "media": 67, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_9": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 9 Portero 1", "media": 78, "valor": 6, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 9 Jugador 1", "media": 78, "valor": 7, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 9 Jugador 2", "media": 75, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 9 Portero 2", "media": 71, "valor": 3, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 9 Jugador 3", "media": 73, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 9 Jugador 4", "media": 69, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_10": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 10 Portero 1", "media": 75, "valor": 5, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 10 Jugador 1", "media": 75, "valor": 6, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 10 Jugador 2", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 10 Portero 2", "media": 68, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 10 Jugador 3", "media": 70, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 10 Jugador 4", "media": 66, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_11": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 11 Portero 1", "media": 77, "valor": 6, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 11 Jugador 1", "media": 78, "valor": 7, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 11 Jugador 2", "media": 74, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 11 Portero 2", "media": 70, "valor": 3, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 11 Jugador 3", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 11 Jugador 4", "media": 68, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_12": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 12 Portero 1", "media": 74, "valor": 5, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 12 Jugador 1", "media": 75, "valor": 6, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 12 Jugador 2", "media": 72, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 12 Portero 2", "media": 67, "valor": 2, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 12 Jugador 3", "media": 70, "valor": 3, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 12 Jugador 4", "media": 66, "valor": 2, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_13": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 13 Portero 1", "media": 76, "valor": 6, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 13 Jugador 1", "media": 77, "valor": 7, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 13 Jugador 2", "media": 73, "valor": 5, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 13 Portero 2", "media": 69, "valor": 3, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 13 Jugador 3", "media": 71, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 13 Jugador 4", "media": 67, "valor": 2, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_14": {
            "liga": "Folimón 1ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 14 Portero 1", "media": 73, "valor": 5, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 14 Jugador 1", "media": 74, "valor": 6, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 14 Jugador 2", "media": 71, "valor": 4, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 14 Portero 2", "media": 66, "valor": 2, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 14 Jugador 3", "media": 69, "valor": 3, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 14 Jugador 4", "media": 66, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
        "EQUIPO_FOLIMON_2_1": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-1 Portero 1", "media": 66, "valor": 3, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-1 Jugador 1", "media": 67, "valor": 4, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-1 Jugador 2", "media": 65, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-1 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-1 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-1 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_2": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-2 Portero 1", "media": 65, "valor": 3, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-2 Jugador 1", "media": 66, "valor": 4, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-2 Jugador 2", "media": 64, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-2 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-2 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-2 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_3": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-3 Portero 1", "media": 67, "valor": 3, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-3 Jugador 1", "media": 67, "valor": 4, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-3 Jugador 2", "media": 66, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-3 Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-3 Jugador 3", "media": 66, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-3 Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_4": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-4 Portero 1", "media": 64, "valor": 3, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-4 Jugador 1", "media": 65, "valor": 4, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-4 Jugador 2", "media": 64, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-4 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-4 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-4 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_5": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-5 Portero 1", "media": 66, "valor": 3, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-5 Jugador 1", "media": 67, "valor": 4, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-5 Jugador 2", "media": 65, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-5 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-5 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-5 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_6": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-6 Portero 1", "media": 65, "valor": 3, "pos": "POR", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-6 Jugador 1", "media": 66, "valor": 4, "pos": "JUG", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-6 Jugador 2", "media": 64, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-6 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-6 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-6 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_7": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-7 Portero 1", "media": 67, "valor": 3, "pos": "POR", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-7 Jugador 1", "media": 67, "valor": 4, "pos": "JUG", "edad": 28, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-7 Jugador 2", "media": 66, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-7 Portero 2", "media": 65, "valor": 1, "pos": "POR", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-7 Jugador 3", "media": 66, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-7 Jugador 4", "media": 65, "valor": 1, "pos": "JUG", "edad": 21, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },

        "EQUIPO_FOLIMON_2_8": {
            "liga": "Folimón 2ª División",
            "escudo": "⚪",
            "jugadores": [
                {"nombre": "Folimón 2-8 Portero 1", "media": 64, "valor": 3, "pos": "POR", "edad": 27, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-8 Jugador 1", "media": 65, "valor": 4, "pos": "JUG", "edad": 26, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-8 Jugador 2", "media": 64, "valor": 2, "pos": "JUG", "edad": 25, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-8 Portero 2", "media": 64, "valor": 1, "pos": "POR", "edad": 22, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-8 Jugador 3", "media": 65, "valor": 2, "pos": "JUG", "edad": 24, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
                {"nombre": "Folimón 2-8 Jugador 4", "media": 64, "valor": 1, "pos": "JUG", "edad": 23, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
            ]
        },
"EQUIPO_FOLIMON_1 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 1 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 1 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_3 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 3 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 3 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_4 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 4 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 4 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_5 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 5 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 5 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_6 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 6 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 6 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_7 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 7 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 7 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_8 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 8 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 8 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_9 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 9 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 9 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_10 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 10 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 10 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_11 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 11 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 11 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_12 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 12 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 12 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_13 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 13 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 13 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_14 Sub-19": {
    "liga": "Folimón Sub-19 1 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 14 S19 Portero 1", "media": 54, "valor": 0.6, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Portero 2", "media": 51, "valor": 0.4, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Portero 3", "media": 48, "valor": 0.3, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 1", "media": 55, "valor": 0.7, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 2", "media": 54, "valor": 0.6, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 3", "media": 52, "valor": 0.5, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 4", "media": 51, "valor": 0.4, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 5", "media": 49, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 6", "media": 48, "valor": 0.3, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 14 S19 Jugador 7", "media": 46, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_1 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-1 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-1 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_2 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-2 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-2 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_3 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-3 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-3 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_4 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-4 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-4 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_5 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-5 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-5 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_6 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-6 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-6 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_7 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-7 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-7 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
},
"EQUIPO_FOLIMON_2_8 Sub-19": {
    "liga": "Folimón Sub-19 2 División",
    "escudo": "⚪",
    "jugadores": [
        {"nombre": "Folimón 2-8 S19 Portero 1", "media": 48, "valor": 0.4, "pos": "POR", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Portero 2", "media": 43, "valor": 0.3, "pos": "POR", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Portero 3", "media": 38, "valor": 0.2, "pos": "POR", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 1", "media": 50, "valor": 0.5, "pos": "JUG", "edad": 19, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 2", "media": 48, "valor": 0.4, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 3", "media": 45, "valor": 0.3, "pos": "JUG", "edad": 18, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 4", "media": 43, "valor": 0.3, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 5", "media": 40, "valor": 0.2, "pos": "JUG", "edad": 17, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 6", "media": 38, "valor": 0.2, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
        {"nombre": "Folimón 2-8 S19 Jugador 7", "media": 35, "valor": 0.1, "pos": "JUG", "edad": 16, "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
    ]
}
}
}

PANELES_PAISES = {
    "PAÍS PRINCIPAL": [
        "1ª División",
        "2ª División",
        "3ª División Grupo A",
        "3ª División Grupo B",
        "4ª División",
        "Sub-19 1 División",
        "Sub-19 2 División",
        "Sub-19 3 División Grupo A",
        "Sub-19 3 División Grupo B",
    ],
    "Com": [
        "Com 1ª División",
        "Com 2ª División",
        "Com Sub-19 1 División",
        "Com Sub-19 2 División",
    ],
    "Tengu": [
        "Tengu 1ª División",
        "Tengu 2ª División",
        "Tengu Sub-19 1 División",
        "Tengu Sub-19 2 División",
    ],
    "Folimón": [
        "Folimón 1ª División",
        "Folimón 2ª División",
        "Folimón Sub-19 1 División",
        "Folimón Sub-19 2 División",
    ],
}

EDADES_INICIALES = {
    "Javi Cáceres": 24, "Dani Tejero": 18, "Jaime López": 20, "Joaquín": 23, "Miguel Muñoz": 23, "Gonzalo Cortés": 22,
    "Fernando Sanchís": 27, "Hugo Fernández": 18, "Arinho": 19, "Lucas Lázaro": 21, "Javi Sánchez": 20, "Bembe": 21,
    "Petrović": 23, "Tonsa": 22, "Dani Martínez": 20, "Takashi": 24, "Raúl Córdoba": 18, "Nacho Jiménez": 17,
    "Nico Giménez": 29, "Show": 25, "Léo Thien": 18, "Laxman": 18, "Arturo Benítez": 22, "Sepi": 17,
    "Zhào": 25, "Enzo Pérez": 26, "Lolo": 19, "Nico Sánchez": 22, "Meyer": 21, "Fukinawa": 20,
    "De Jong": 23, "Terglish": 21, "Hadivick": 21, "Héctor Martínez": 20, "Caraçao": 20, "Bedelchenko": 19,
    "Juan Vega": 28, "Torsič": 24, "Blas": 21, "Onyeka": 19, "Felipe Cano": 22, "José Soriano": 17,
    "Ramírez": 21, "Enzo": 19, "Virtanen": 20, "Víctor Régulo": 23, "Wellington": 20, "McCarthy": 18,
    "Iker Gallardo": 21, "Esteban Moya": 20, "Jesús Herrera": 20, "Samuele Francesco": 26, "Darío Márquez": 18, "Felipe Santos": 19,
    "Pedro Vázquez": 24, "Carlos Torres": 19, "Vito JR": 20, "Sérgio": 23, "Mateo Vida": 20, "David Gutiérrez": 19,
    "Fernando Blanco": 26, "Youssef Idrissi": 21, "Josema": 17, "Obi": 21, "Andrés Navarro": 19, "Nil Santana": 23,
    "González": 23, "Manuel Rodríguez": 24, "Samu": 21, "Óscar Sosa": 18, "Eric Cabrera": 20, "Gabri Costa": 19,
    "Carmona": 25, "Marcos López": 23, "Ángel Bravo": 19, "Yilmaz": 28, "Unai Pascual": 20, "Rubén": 17,
    "Guille Fuentes": 25, "Ismael": 21, "Raúl Montero": 19, "Ryan Anderson": 25, "Serway": 20, "Rafa León": 19,
    "Iván Martín": 27, "Castillo": 22, "Lintombe": 21, "Rossi": 28, "Schmidt": 19, "Aarón Garrido": 18,
    "Dani Monzón": 25, "Francisco Castro": 20, "Gabri": 19, "Carlos González": 23, "Carlos Jiménez": 17, "Juan Medina": 18,
    "Bruno Iglesias": 26, "Alex Rubio": 24, "Rafa Ortega": 19, "Tanaka": 22, "Moreno": 20, "Mario Carrasco": 19,
    "Víctor Casas": 25, "Héctor Gómez": 23, "Montserrat": 20, "Dupont": 27, "Méndez": 22, "Asier": 23,
    "Martín Peña": 29, "Matías Sanz": 21, "Bleu": 20, "Ricardo Fernández": 29, "Alfonso Madrid": 28, "Tiquinho": 18,
    "Song": 18, "Montero": 21, "Santi Hidalgo": 32, "Diego Sánchez": 26, "Antonio Soler": 26, "Sergio Pérez": 16,
}

JUGADORES_NACIONALIDAD = {
    "CEREZAS": [
        {"nombre": "Javi Cáceres",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Dani Tejero",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Jaime López",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Joaquín",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Miguel Muñoz",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Gonzalo Cortés",    "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "DECERÓN": [
        {"nombre": "Fernando Sanchís",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hugo Fernández",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Arinho",            "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Lucas Lázaro",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Javi Sánchez",      "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Bembe",             "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
    ],
    "LONESTO": [
        {"nombre": "Petrović",          "banderas": ["🇧🇦"],           "nacionalidades": ["bosnia"]},
        {"nombre": "Tonsa",             "banderas": ["🇧🇪"],           "nacionalidades": ["belga"]},
        {"nombre": "Dani Martínez",     "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Takashi",           "banderas": ["🇯🇵"],           "nacionalidades": ["japonesa"]},
        {"nombre": "Raúl Córdoba",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Nacho Jiménez",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "KINGZ": [
        {"nombre": "Nico Giménez",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Show",              "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
        {"nombre": "Léo Thien",         "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Laxman",            "banderas": ["🇮🇳"],           "nacionalidades": ["india"]},
        {"nombre": "Arturo Benítez",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Sepi",              "banderas": ["🇸🇳"],           "nacionalidades": ["senegalesa"]},
    ],
    "MAMBO": [
        {"nombre": "Zhào",              "banderas": ["🇨🇳"],           "nacionalidades": ["china"]},
        {"nombre": "Enzo Pérez",        "banderas": ["🇦🇷", "🇦🇶"],     "nacionalidades": ["argentina", "nacional"]},
        {"nombre": "Lolo",              "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Nico Sánchez",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Meyer",             "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Fukinawa",          "banderas": ["🇯🇵"],           "nacionalidades": ["japonesa"]},
    ],
    "QUÍTER": [
        {"nombre": "De Jong",           "banderas": ["🇳🇱"],           "nacionalidades": ["neerlandesa"]},
        {"nombre": "Terglish",          "banderas": ["🏴󠁧󠁢󠁳󠁣󠁴󠁿"],           "nacionalidades": ["escocesa"]},
        {"nombre": "Hadivick",          "banderas": ["🇨🇿"],           "nacionalidades": ["checa"]},
        {"nombre": "Héctor Martínez",   "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Caraçao",           "banderas": ["🇵🇹"],           "nacionalidades": ["portuguesa"]},
        {"nombre": "Bedelchenko",       "banderas": ["🇺🇦"],           "nacionalidades": ["ucraniana"]},
    ],
    "BENSARO": [
        {"nombre": "Juan Vega",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Torsič",            "banderas": ["🇭🇷"],           "nacionalidades": ["croata"]},
        {"nombre": "Blas",              "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Onyeka",            "banderas": ["🇳🇬"],           "nacionalidades": ["nigeriana"]},
        {"nombre": "Felipe Cano",       "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "José Soriano",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "SIROL": [
        {"nombre": "Ramírez",           "banderas": ["🇨🇴"],           "nacionalidades": ["colombiana"]},
        {"nombre": "Enzo",              "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Virtanen",          "banderas": ["🇫🇮"],           "nacionalidades": ["finlandesa"]},
        {"nombre": "Víctor Régulo",     "banderas": ["🇵🇹"],           "nacionalidades": ["portuguesa"]},
        {"nombre": "Wellington",        "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "McCarthy",          "banderas": ["🇮🇪"],           "nacionalidades": ["irlandesa"]},
    ],
    "ANTINO": [
        {"nombre": "Iker Gallardo",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Esteban Moya",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Jesús Herrera",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Samuele Francesco", "banderas": ["🇮🇹"],           "nacionalidades": ["italiana"]},
        {"nombre": "Darío Márquez",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Felipe Santos",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "MELOP": [
        {"nombre": "Pedro Vázquez",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Carlos Torres",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Vito JR",           "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Sérgio",            "banderas": ["🇵🇹"],           "nacionalidades": ["portuguesa"]},
        {"nombre": "Mateo Vida",        "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "David Gutiérrez",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "RUPER": [
        {"nombre": "Fernando Blanco",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Youssef Idrissi",   "banderas": ["🇲🇦"],           "nacionalidades": ["marroquí"]},
        {"nombre": "Josema",            "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Obi",               "banderas": ["🇬🇭"],           "nacionalidades": ["ghanesa"]},
        {"nombre": "Andrés Navarro",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Nil Santana",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ALLSURA": [
        {"nombre": "González",          "banderas": ["🇦🇷"],           "nacionalidades": ["argentina"]},
        {"nombre": "Manuel Rodríguez",  "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Samu",              "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Óscar Sosa",        "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Eric Cabrera",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Gabri Costa",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ENERTO": [
        {"nombre": "Carmona",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Marcos López",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Ángel Bravo",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Yilmaz",            "banderas": ["🇹🇷"],           "nacionalidades": ["turca"]},
        {"nombre": "Unai Pascual",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Rubén",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "TREO": [
        {"nombre": "Guille Fuentes",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Ismael",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Raúl Montero",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Ryan Anderson",     "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Serway",            "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Rafa León",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "DOMELÍ": [
        {"nombre": "Iván Martín",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Castillo",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Lintombe",          "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Rossi",             "banderas": ["🇮🇹"],           "nacionalidades": ["italiana"]},
        {"nombre": "Schmidt",           "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Aarón Garrido",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "DORRO": [
        {"nombre": "Dani Monzón",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Francisco Castro",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Gabri",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Carlos González",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Carlos Jiménez",    "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Juan Medina",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ASORPA": [
        {"nombre": "Bruno Iglesias",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Alex Rubio",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Rafa Ortega",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Tanaka",            "banderas": ["🇯🇵"],           "nacionalidades": ["japonesa"]},
        {"nombre": "Moreno",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Mario Carrasco",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "SABADERO": [
        {"nombre": "Víctor Casas",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Héctor Gómez",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Montserrat",        "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Dupont",            "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Méndez",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Asier",             "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
    ],
    "COCONUT": [
        {"nombre": "Martín Peña",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Matías Sanz",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Bleu",              "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Ricardo Fernández", "banderas": ["🇦🇷"],           "nacionalidades": ["argentina"]},
        {"nombre": "Alfonso Madrid",    "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Tiquinho",          "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
    ],
    "CHIMICHANGA": [
        {"nombre": "Song",              "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Montero",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Santi Hidalgo",     "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
        {"nombre": "Diego Sánchez",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Antonio Soler",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Sergio Pérez",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "IGLESIA": [
        {"nombre": "Martín Toribio",    "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Ale Sánchez",       "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Pedro Domingo",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Santiago Morales",  "banderas": ["🇪🇨"],           "nacionalidades": ["ecuatoriana"]},
        {"nombre": "Bauer",             "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Arnau Afonso",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "POK": [
        {"nombre": "Miguel Ballesteros","banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
        {"nombre": "Arimé",             "banderas": ["🇸🇳"],           "nacionalidades": ["senegalesa"]},
        {"nombre": "Manuel Berenguer",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Antonio Martínez",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Francisco Pazos",   "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Dani Pedraza",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "SIBERIA": [
        {"nombre": "Sosa",              "banderas": ["🇦🇷"],           "nacionalidades": ["argentina"]},
        {"nombre": "Côme Le Goff",      "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Vicente Barrero",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Alex Fernández",    "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Alejandro Sierra",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Valentín Frutos",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "SALMÓN": [
        {"nombre": "Kleber",            "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Javi Oller",        "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hugo Prieto",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Mario Villegas",    "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
        {"nombre": "Pablo Plaza",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Darling",           "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
    ],
    "ALTORPO": [
        {"nombre": "Chema Romero",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Engels",            "banderas": ["🇧🇪"],           "nacionalidades": ["belga"]},
        {"nombre": "Luis Blanco",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Voronin",           "banderas": ["🇺🇦"],           "nacionalidades": ["ucraniana"]},
        {"nombre": "César Rico",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Esteban Palomar",   "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
    ],
    "FROSTÉ": [
        {"nombre": "Miguel Zamorano",   "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Maxi Merino",       "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Pereira",           "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Soria",             "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Kombo",             "banderas": ["🇨🇲"],           "nacionalidades": ["camerunesa"]},
        {"nombre": "Boualem",           "banderas": ["🇩🇿"],           "nacionalidades": ["argelina"]},
    ],
    "FEBRONTO": [
        {"nombre": "Juan Meléndez",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hatem",             "banderas": ["🇲🇦"],           "nacionalidades": ["marroquí"]},
        {"nombre": "Nico Villalba",     "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Lombardi",          "banderas": ["🇮🇹"],           "nacionalidades": ["italiana"]},
        {"nombre": "David Rivas",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Ángel Duarte",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ABDUZCAN": [
        {"nombre": "Dani Rubio",        "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Juan Aguilar",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "David Ponce",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Luque",             "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Laredo",            "banderas": ["🇦🇩"],           "nacionalidades": ["andorrana"]},
        {"nombre": "Jaime Egea",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ANCO": [
        {"nombre": "Olmo",              "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Taleb",             "banderas": ["🇲🇦"],           "nacionalidades": ["marroquí"]},
        {"nombre": "Alonso",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Afonso",            "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Marc",              "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Uygun",             "banderas": ["🇹🇷"],           "nacionalidades": ["turca"]},
    ],
    "ZOQUIO": [
        {"nombre": "Dumont",            "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Alberto",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Suárez",            "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Muntari",           "banderas": ["🇶🇦"],           "nacionalidades": ["catarí"]},
        {"nombre": "Calleja",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Hugo",              "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "AGUEST": [
        {"nombre": "César",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Loureiro",          "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Spence",            "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
        {"nombre": "Bin Zhao",          "banderas": ["🇨🇳"],           "nacionalidades": ["china"]},
        {"nombre": "Borja",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Saúl",              "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ALFALFA": [
        {"nombre": "Prat",              "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Mario",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Nil",               "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
        {"nombre": "Alarcón",           "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
        {"nombre": "Appiah",            "banderas": ["🇬🇭"],           "nacionalidades": ["ghanesa"]},
        {"nombre": "Cordero",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "DENTOR": [
        {"nombre": "Mayoral",           "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Vranches",          "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Migue",             "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hindson",           "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
        {"nombre": "Gaspar",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Fernán",            "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
    ],
    "JOREVOS": [
        {"nombre": "Unai",              "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Buendía",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Bellido",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Alex Fallon",       "banderas": ["🇳🇿"],           "nacionalidades": ["neozelandesa"]},
        {"nombre": "Luis",              "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Nelson",            "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
    ],
    "AMPRO": [
        {"nombre": "Perea",             "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Emilio",            "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Noah Miller",       "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Machín",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Granados",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Schopp",            "banderas": ["🇦🇹"],           "nacionalidades": ["austriaca"]},
    ],
    "MERSOL": [
        {"nombre": "Juan Jesús",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Seoane",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Galindo",           "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Nkgosi Davids",     "banderas": ["🇿🇦"],           "nacionalidades": ["sudafricana"]},
        {"nombre": "Eloy",              "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Llorer",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "NÁCOR": [
        {"nombre": "Mariño",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Moyano",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Heckingbottom",     "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],           "nacionalidades": ["inglesa"]},
        {"nombre": "Mráz",              "banderas": ["🇸🇰"],           "nacionalidades": ["eslovaca"]},
        {"nombre": "Oriol Rivera",            "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Le Bris",           "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
    ],
    "XEMAR": [
        {"nombre": "Moya",              "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Moha",              "banderas": ["🇲🇦"],           "nacionalidades": ["marroquí"]},
        {"nombre": "Solana",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Iván",              "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Carlitos",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Josemi",            "banderas": ["🇱🇨"],           "nacionalidades": ["folimonense"]},
    ],
    "LOCKE": [
        {"nombre": "Arana",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Cerezo",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Guille Vera",     "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Julian",          "banderas": ["🇬🇮"],           "nacionalidades": ["gibraltareña"]},
        {"nombre": "Fritz",           "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Fraga",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "MARTERO": [
        {"nombre": "Trigo",           "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Peiro",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Escobar",         "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Thami Sampson",   "banderas": ["🇿🇦"],           "nacionalidades": ["sudafricana"]},
        {"nombre": "Ernesto",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Martos",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "SCAR": [
        {"nombre": "Ruano",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Hulshoff",        "banderas": ["🇳🇱"],           "nacionalidades": ["neerlandesa"]},
        {"nombre": "Zamora",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hugo Yuste",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Wallius",         "banderas": ["🇫🇮"],           "nacionalidades": ["finlandesa"]},
        {"nombre": "Raposo",          "banderas": ["🇵🇹"],           "nacionalidades": ["portuguesa"]},
    ],
    "FOL": [
        {"nombre": "Andrés",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Esmorís",         "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Minatel",         "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Hadi",            "banderas": ["🇲🇦"],           "nacionalidades": ["marroquí"]},
        {"nombre": "Nabil L'Ghoul",   "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Milla",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "BLOX": [
        {"nombre": "Rojo",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Fabri Zurdel",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Yacouba",         "banderas": ["🇳🇪"],           "nacionalidades": ["nigerina"]},
        {"nombre": "Buenaventura",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Diatta",          "banderas": ["🇸🇳"],           "nacionalidades": ["senegalesa"]},
        {"nombre": "Krasniqi",        "banderas": ["🇽🇰"],           "nacionalidades": ["kosovar"]},
    ],
    "VILLAPORRINO": [
        {"nombre": "Rivera",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Ayoze",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Sandoval",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Soppy",           "banderas": ["🇨🇮"],           "nacionalidades": ["marfileña"]},
        {"nombre": "Méndez",          "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Crespo",          "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
    ],
    "FIF": [
        {"nombre": "Günter",          "banderas": ["🇩🇪"],           "nacionalidades": ["alemana"]},
        {"nombre": "Pizzi",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Bamba",           "banderas": ["🇨🇮"],           "nacionalidades": ["marfileña"]},
        {"nombre": "Agustín",         "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Cabral",          "banderas": ["🇦🇷"],           "nacionalidades": ["argentina"]},
        {"nombre": "Borja Marí",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "MINE": [
        {"nombre": "Morris",          "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Pedraza",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Manquillo",       "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Amarillo",        "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Carrión",         "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Navarra",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "JULÍN": [
        {"nombre": "Soler",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Vasco",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Palencia",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Renato",          "banderas": ["🇵🇪"],           "nacionalidades": ["peruana"]},
        {"nombre": "Marcano",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Rafa",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "BOLONCHO": [
        {"nombre": "Girard",          "banderas": ["🇫🇷"],           "nacionalidades": ["francesa"]},
        {"nombre": "Díaz",            "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Muñoz",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Bissainthe",      "banderas": ["🇭🇹"],           "nacionalidades": ["haitiana"]},
        {"nombre": "Navas",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Barroso",         "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
    ],
    "VORNES": [
        {"nombre": "Jaén",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Gray",            "banderas": ["🏴󠁧󠁢󠁳󠁣󠁴󠁿"],            "nacionalidades": ["escocesa"]},
        {"nombre": "Soares",          "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Bilbao",          "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "César",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Carbonell",       "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "CEREZAS B": [
        {"nombre": "Sergio Sánchez",  "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Simón",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Montillana",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Juanjo",          "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Juanmi Muñoz",    "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Trivi",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "MOJI": [
        {"nombre": "Bernabé",         "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Adjeil Pereira",  "banderas": ["🇸🇹"],           "nacionalidades": ["santo-tomense"]},
        {"nombre": "Toral",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Bueno",           "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "De Barr",         "banderas": ["🇬🇮"],           "nacionalidades": ["gibraltareña"]},
        {"nombre": "Diaby",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "COF": [
        {"nombre": "Robinson",        "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"],            "nacionalidades": ["inglesa"]},
        {"nombre": "Denis",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Turrell",         "banderas": ["🇬🇮"],           "nacionalidades": ["gibraltareña"]},
        {"nombre": "Ramos",           "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Kike",            "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Iglesias",        "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "PER": [
        {"nombre": "Skela",           "banderas": ["🇦🇱"],           "nacionalidades": ["albanesa"]},
        {"nombre": "Curtin",          "banderas": ["🇺🇸"],           "nacionalidades": ["estadounidense"]},
        {"nombre": "Mateo López",     "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Peñaranda",       "banderas": ["🇦🇷"],           "nacionalidades": ["argentina"]},
        {"nombre": "Mario Iglesias",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Antonio Iglesias","banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "PICO": [
        {"nombre": "Lima",            "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Turunen",         "banderas": ["🇫🇮"],           "nacionalidades": ["finlandesa"]},
        {"nombre": "Alejandro Torres","banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Kowalski",        "banderas": ["🇵🇱"],           "nacionalidades": ["polaca"]},
        {"nombre": "Javier Morales",  "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Marín",           "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "XD": [
        {"nombre": "Mario Jiménez",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Juan Poyato",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Idrizi",          "banderas": ["🇽🇰"],           "nacionalidades": ["kosovar"]},
        {"nombre": "Itten",           "banderas": ["🇨🇭"],           "nacionalidades": ["suiza"]},
        {"nombre": "Tomás Romero",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Gonzalo Hervás",  "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
    ],
    "UH": [
        {"nombre": "Alfonso Millán",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Benito Calderón", "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Pedro Ochoa",     "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Kovačević",       "banderas": ["🇭🇷"],           "nacionalidades": ["croata"]},
        {"nombre": "O’Reilly",        "banderas": ["🇮🇪"],           "nacionalidades": ["irlandesa"]},
        {"nombre": "Vušković",        "banderas": ["🇭🇷"],           "nacionalidades": ["croata"]},
    ],
    "DUTE": [
        {"nombre": "Blas Nadal",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Manu Pozo",       "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Íñigo Botín",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Daniel Blasco",   "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Nunes",           "banderas": ["🇵🇹"],           "nacionalidades": ["portuguesa"]},
        {"nombre": "Kooistra",        "banderas": ["🇳🇱"],           "nacionalidades": ["neerlandesa"]},
    ],
    "MAMBO B": [
        {"nombre": "Ángel Montilla",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Proixão",         "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Simbinho",        "banderas": ["🇧🇷"],           "nacionalidades": ["brasileña"]},
        {"nombre": "Al-Mansoori",     "banderas": ["🇶🇦"],           "nacionalidades": ["qatarí"]},
        {"nombre": "Aitor Cañete",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "David Retamosa",  "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
    ],
    "GAMBI": [
        {"nombre": "Pelayo Cela",     "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Bajrami",         "banderas": ["🇦🇱"],           "nacionalidades": ["albanesa"]},
        {"nombre": "Hipólito Navas",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Javi García",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Fran Martín",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Nacho Luna",      "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "MACAGUADAN": [
        {"nombre": "Pablo Barrera",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Antonio Guzmán",  "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Pau Santana",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Akindale Olatunji","banderas": ["🇳🇬"],          "nacionalidades": ["nigeriana"]},
        {"nombre": "Ernesto Elías",   "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Veto Sevilla",    "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
    ],
    "TORE": [
        {"nombre": "Tobías Cifuentes","banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Mazzu",           "banderas": ["🇧🇪"],           "nacionalidades": ["belga"]},
        {"nombre": "Djibril Pelletier","banderas": ["🇫🇷"],          "nacionalidades": ["francesa"]},
        {"nombre": "Juan Pérez",      "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Martín Moncayo",  "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Víctor Narváez",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "BANANO": [
        {"nombre": "Kavanagh",        "banderas": ["🏴󠁧󠁢󠁳󠁣󠁴󠁿"],            "nacionalidades": ["escocesa"]},
        {"nombre": "Diouf",           "banderas": ["🇸🇳"],           "nacionalidades": ["senegalesa"]},
        {"nombre": "Pablo Vázquez",   "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Guillermo Varela","banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Aarón Carranza",  "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Miguel Zerolo",   "banderas": ["🇧🇧", "🇮🇹"],    "nacionalidades": ["comera", "italiana"]},
    ],
    "AM": [
        {"nombre": "Antonio Castellanos","banderas": ["🇧🇧"],        "nacionalidades": ["comera"]},
        {"nombre": "Jesús Yague",     "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Alex Gómez",      "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
        {"nombre": "Liam Ballester",  "banderas": ["🇬🇮"],           "nacionalidades": ["gibraltareña"]},
        {"nombre": "Jorge Jesús Ledesma","banderas": ["🇦🇶"],        "nacionalidades": ["nacional"]},
        {"nombre": "Luciano Zaragoza","banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "FORT": [
        {"nombre": "Ba",              "banderas": ["🇸🇳"],           "nacionalidades": ["senegalesa"]},
        {"nombre": "Pol Fuentes",     "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Alejandro Serna", "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Juris Kalniņš",   "banderas": ["🇱🇻"],           "nacionalidades": ["letona"]},
        {"nombre": "Juan Manuel Rubio","banderas": ["🇦🇶"],          "nacionalidades": ["nacional"]},
        {"nombre": "Juan García",     "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
    ],
    "STOR": [
        {"nombre": "Miguel Ángel del Monte","banderas": ["🇱🇨"],     "nacionalidades": ["tenguana"]},
        {"nombre": "Martín Castillo", "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Juan Prado",      "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Leo Enríquez",    "banderas": ["🇱🇨"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Tomás Rubio",     "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Enrique Puertas", "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
    ],
    "ROMPH": [
        {"nombre": "Vicente Mata",    "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Julio Serrano",   "banderas": ["🇦🇶"],           "nacionalidades": ["nacional"]},
        {"nombre": "Hugo Muñoz",      "banderas": ["🇦🇬"],           "nacionalidades": ["tenguana"]},
        {"nombre": "Tayler Emrini",   "banderas": ["🇬🇮"],           "nacionalidades": ["gibraltareña"]},
        {"nombre": "Rodri Jiménez",   "banderas": ["🇧🇧"],           "nacionalidades": ["comera"]},
        {"nombre": "Sergio Badía",    "banderas": ["🇪🇸"],           "nacionalidades": ["española"]},
    ],
    "POLANDIA": [
{"nombre": "Paco Jubero", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Pepe Ferrer", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Noah De Jong", "banderas": ["🇳🇱"], "nacionalidades": ["neerlandesa"]},
{"nombre": "Manuel Pino", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Fleminho", "banderas": ["🇧🇷"], "nacionalidades": ["brasileña"]},
{"nombre": "Javi Dorado", "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
],

"SIROL B": [
{"nombre": "Marc Ferrando", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Casado", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Puerta", "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
{"nombre": "Fabian Carbon", "banderas": ["🇨🇭"], "nacionalidades": ["suiza"]},
{"nombre": "Luis Ramis", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
{"nombre": "Rings", "banderas": ["🏴󠁧󠁢󠁥󠁮󠁧󠁿"], "nacionalidades": ["inglesa"]},
],

"HUNGARIA": [
{"nombre": "Sousa", "banderas": ["🇵🇹"], "nacionalidades": ["portuguesa"]},
{"nombre": "Heliberto Orozco", "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
{"nombre": "Alberto Riera", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
{"nombre": "Pedro Navas", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Álex Crespo", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Manuel Marí", "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
],

"NEDERLANDIA": [
{"nombre": "Dorvič", "banderas": ["🇭🇷"], "nacionalidades": ["croata"]},
{"nombre": "Mensah", "banderas": ["🇬🇭"], "nacionalidades": ["ghanesa"]},
{"nombre": "Mikel Torres", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Leopoldo de Andrade", "banderas": ["🇦🇶", "🇧🇷"], "nacionalidades": ["nacional", "brasileña"]},
{"nombre": "Diarra", "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
{"nombre": "Traoré", "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
],

"ALLSURA B": [
{"nombre": "Jan Portero", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Óliver Reguillos", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Sheldon Ngubo", "banderas": ["🇿🇦"], "nacionalidades": ["sudafricana"]},
{"nombre": "Jacobo Toledano", "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
{"nombre": "Bruno Montesinos", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
{"nombre": "Manolo Rivas", "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
],

"TREO B": [
{"nombre": "Julio Estévez", "banderas": ["🇪🇸"], "nacionalidades": ["española"]},
{"nombre": "Jorge Villar", "banderas": ["🇦🇬"], "nacionalidades": ["tenguana"]},
{"nombre": "Gerard Fuster", "banderas": ["🇱🇨"], "nacionalidades": ["folimonense"]},
{"nombre": "Claudio Pacheco", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Francisco Mayoral", "banderas": ["🇦🇶"], "nacionalidades": ["nacional"]},
{"nombre": "Diambou", "banderas": ["🇸🇳"], "nacionalidades": ["senegalesa"]},
],

"CEREZAS Sub-19": [
    {"nombre": "Lázaro Di Domenico", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Aarón Altozano", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "De Cea", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Onguene", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Rubén Fortea", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Luciano Quintana", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Waldo Coronas", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Sebas Arrebola", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Gueye", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]},
    {"nombre": "Jaime Tejero", "banderas": ["🇧🇧"], "nacionalidades": ["comera"]}
],
}
PREMIOS_CLASIFICACION_PAIS = {
    # 1ª División (20 equipos) - Campeón: 40 M, Último: 11 M
    "1ª División": {
        1: 40,
        2: 38,
        3: 36,
        4: 34,
        5: 32,
        6: 30,
        7: 28,
        8: 26,
        9: 24,
        10: 22,
        11: 20,
        12: 18,
        13: 16,
        14: 14.5,
        15: 13.5,
        16: 12.5,
        17: 12,
        18: 11.7,
        19: 11.3,
        20: 11,
    },

    # 2ª División (20 equipos) - Campeón: 15 M, Último: 3.5 M
    "2ª División": {
        1: 15,
        2: 14,
        3: 13,
        4: 12,
        5: 11,
        6: 10,
        7: 9,
        8: 8,
        9: 7.5,
        10: 7,
        11: 6.5,
        12: 6,
        13: 5.5,
        14: 5,
        15: 4.5,
        16: 4,
        17: 3.8,
        18: 3.65,
        19: 3.55,
        20: 3.5,
    },

    # 3ª División Grupo A (14 equipos) - Campeón: 7.5 M, Último: 0.5 M
    "3ª División Grupo A": {
        1: 7.5,
        2: 6.5,
        3: 5.5,
        4: 4.5,
        5: 3.8,
        6: 3.2,
        7: 2.7,
        8: 2.3,
        9: 1.9,
        10: 1.5,
        11: 1.2,
        12: 0.9,
        13: 0.7,
        14: 0.5,
    },

    # 3ª División Grupo B (14 equipos) - Campeón: 7.5 M
    "3ª División Grupo B": {
        1: 7.5,
        2: 6.5,
        3: 5.5,
        4: 4.5,
        5: 3.8,
        6: 3.2,
        7: 2.7,
        8: 2.3,
        9: 1.9,
        10: 1.5,
        11: 1.2,
        12: 0.9,
        13: 0.7,
        14: 0.5,
    },

    # 4ª División (6 equipos) - Campeón: 2.5 M, Último: 0.5 M
    "4ª División": {
        1: 2.5,
        2: 2,
        3: 1.5,
        4: 1.2,
        5: 0.8,
        6: 0.5,
    },

    # === LIGAS NACIONALES (Com, Tengu, Folimón) ===
    # 1ª División (14 equipos) - Campeón: 30 M, Último: 7 M
    "Com 1ª División": {
        1: 30,
        2: 27,
        3: 24,
        4: 21,
        5: 18,
        6: 15,
        7: 13,
        8: 11,
        9: 10,
        10: 9,
        11: 8,
        12: 7.5,
        13: 7.2,
        14: 7,
    },
    "Tengu 1ª División": {
        1: 30,
        2: 27,
        3: 24,
        4: 21,
        5: 18,
        6: 15,
        7: 13,
        8: 11,
        9: 10,
        10: 9,
        11: 8,
        12: 7.5,
        13: 7.2,
        14: 7,
    },
    "Folimón 1ª División": {
        1: 30,
        2: 27,
        3: 24,
        4: 21,
        5: 18,
        6: 15,
        7: 13,
        8: 11,
        9: 10,
        10: 9,
        11: 8,
        12: 7.5,
        13: 7.2,
        14: 7,
    },

    # 2ª División (8 equipos) - Campeón: 10 M, Último: 2.5 M
    "Com 2ª División": {
        1: 10,
        2: 8.5,
        3: 7,
        4: 5.5,
        5: 4,
        6: 3.2,
        7: 2.8,
        8: 2.5,
    },
    "Tengu 2ª División": {
        1: 10,
        2: 8.5,
        3: 7,
        4: 5.5,
        5: 4,
        6: 3.2,
        7: 2.8,
        8: 2.5,
    },
    "Folimón 2ª División": {
        1: 10,
        2: 8.5,
        3: 7,
        4: 5.5,
        5: 4,
        6: 3.2,
        7: 2.8,
        8: 2.5,
    },
}

st.set_page_config(page_title="Manager Pro", page_icon="⚽", layout="wide")

def recargar():
    try:
        st.rerun()
    except Exception:
        pass

def generar_calendario(equipos, vueltas=2):
    if len(equipos) < 2:
        return []
    equipos = list(equipos)
    random.shuffle(equipos)
    if len(equipos) % 2 != 0:
        equipos.append(None)
    n = len(equipos)
    half = n // 2
    rounds = n - 1
    rotation = equipos[:]
    ida = []
    for r in range(rounds):
        jornada = []
        for i in range(half):
            a = rotation[i]
            b = rotation[n - 1 - i]
            if a is not None and b is not None:
                jornada.append((a, b) if r % 2 == 0 else (b, a))
        ida.append(jornada)
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
    
    # Construir calendario según número de vueltas
    calendario = []
    for v in range(vueltas):
        if v % 2 == 0:
            # Vueltas pares: mismo orden que ida
            calendario.extend(ida)
        else:
            # Vueltas impares: orden inverso (vuelta)
            calendario.extend([[(b, a) for a, b in jornada] for jornada in ida])
    
    return calendario

def asegurar_estado_ligas(db):
    for _, liga in db["ligas"].items():
        liga.setdefault("equipos", [])
        liga.setdefault("calendario", [])
        liga.setdefault("resultados", [])
        liga.setdefault("jornada", 0)
        liga.setdefault("historial_clubes", {})

def normalizar_calendario(db):
    for _, liga in db["ligas"].items():
        calendario = liga.get("calendario", [])
        nuevo = []
        for jornada in calendario:
            nueva_jornada = []
            if isinstance(jornada, list):
                for partido in jornada:
                    if isinstance(partido, (list, tuple)) and len(partido) == 2:
                        nueva_jornada.append((partido[0], partido[1]))
            nuevo.append(nueva_jornada)
        liga["calendario"] = nuevo

def regenerar_calendario_si_falta(db):
    # Ligas con 4 vueltas por tener pocos equipos
    ligas_4_vueltas = {
        "4ª División",
        "Com 2ª División",
        "Tengu 2ª División",
        "Folimón 2ª División",
        "Com Sub-19 2 División",
        "Tengu Sub-19 2 División",
        "Folimón Sub-19 2 División",
    }

    for nombre_liga, liga in db["ligas"].items():
        equipos = liga.get("equipos", [])
        calendario = liga.get("calendario", [])
        
        if len(equipos) >= 2 and (not calendario or all(len(j) == 0 for j in calendario)):
            # Determinar número de vueltas
            vueltas = 4 if nombre_liga in ligas_4_vueltas else 2
            liga["calendario"] = generar_calendario(equipos, vueltas=vueltas)

def reconstruir_jornada_desde_resultados(db):
    for _, liga in db["ligas"].items():
        resultados = liga.get("resultados", [])
        equipos = liga.get("equipos", [])
        calendario = liga.get("calendario", [])

        if not calendario:
            liga["jornada"] = 0
            continue

        ppj = max(1, len(equipos) // 2)

        conteo_por_jornada = {}
        for r in resultados:
            if not isinstance(r, dict):
                continue

            jn = int(r.get("jornada_num", 0) or 0)
            if jn <= 0:
                continue

            conteo_por_jornada[jn] = conteo_por_jornada.get(jn, 0) + 1

        jornada_ok = 0
        total_jornadas = len(calendario)

        for j in range(1, total_jornadas + 1):
            if conteo_por_jornada.get(j, 0) >= ppj:
                jornada_ok = j
            else:
                break

        liga["jornada"] = jornada_ok
    
def sanear_jugadores(db):
    # orígenes: senior y sub-19
    for origen in ["equipos_data", "equipos_data_sub19"]:
        for eq, ed in db.get(origen, {}).items():
            # Mapeo rápido nombre -> info de JUGADORES_NACIONALIDAD para este equipo (solo existirá para algunos)
            info_eq = JUGADORES_NACIONALIDAD.get(eq, [])
            mapa_nac = {j["nombre"]: j for j in info_eq}

            for j in ed["jugadores"]:
                # Stats básicas
                for k in ["goles", "asistencias", "amarillas", "rojas",
                          "partidos", "nota_total", "goles_encajados",
                          "lesion_jornadas", "cansancio"]:
                    j.setdefault(k, 0)
                j.setdefault("partidos_titular", 0)
                j.setdefault("minutos_totales", 0)

                # Edad
                if "edad" not in j:
                    edad_base = EDADES_INICIALES.get(j["nombre"])
                    j["edad"] = edad_base if edad_base is not None else random.randint(18, 34)

                # Nacionalidad y banderas
                data_nac = mapa_nac.get(j["nombre"])
                if data_nac:
                    j.setdefault("banderas", data_nac.get("banderas", []))
                    j.setdefault("nacionalidades", data_nac.get("nacionalidades", []))
                else:
                    j.setdefault("banderas", [])
                    j.setdefault("nacionalidades", [])

                j.setdefault("retirarse_al_final", False)
                j.setdefault("cedido", False)
                j.setdefault("cedido_hasta", 0)
                j.setdefault("propietario", eq)
                j.setdefault("historial_valor", [j["valor"]])
                j.setdefault("historial_media", [j["media"]])
                j.setdefault("historial_temporadas", [])
                j.setdefault("historial_traspasos", [])
                j.setdefault("equipo_actual", eq)

                # Campos para ofertas automáticas
                j.setdefault("transferible", False)
                j.setdefault("cedible", False)

                limitar_valor_por_liga(j, eq)


def asignar_salarios_y_contratos(db, solo_si_no_existe=True):
    """
    Añade salario y contrato a los jugadores.

    - salario: millones de euros por temporada.
    - fin_contrato: temporada absoluta en la que vence el contrato.

    Ejemplo:
    Si la temporada actual es 1 y firma por 3 temporadas,
    fin_contrato será 4. Quedará libre al empezar la temporada 4.

    Si solo_si_no_existe es True, no modifica los contratos
    ni salarios que ya existan en una partida guardada.
    """
    temporada_actual = db["config"]["temporada"]

    for equipo, datos_equipo in db["equipos_data"].items():
        sub19 = es_equipo_sub19(equipo)

        for jugador in datos_equipo.get("jugadores", []):
            edad = jugador.get("edad", 20)

            if not solo_si_no_existe or "salario" not in jugador:
                jugador["salario"] = calcular_salario_por_temporada(
                    jugador.get("media", 40),
                    edad,
                    sub19
                )

            if not solo_si_no_existe or "fin_contrato" not in jugador:
                if sub19:
                    duracion = random.choice([1, 2, 2, 3])
                elif edad >= 32:
                    duracion = random.choice([1, 1, 2])
                elif edad >= 28:
                    duracion = random.choice([1, 2, 2, 3])
                else:
                    duracion = random.choice([2, 3, 3, 4])

                # Guarda la temporada de vencimiento, no años restantes.
                jugador["fin_contrato"] = temporada_actual + duracion - 1

            # Asegurar campos de transferibilidad/cesión
            jugador.setdefault("transferible", False)
            jugador.setdefault("cedible", False)

def preparar_db_cargada(db):
    sanear_jugadores(db)
    asegurar_estado_ligas(db)
    normalizar_calendario(db)
    regenerar_calendario_si_falta(db)
    asignar_salarios_y_contratos(db)

def asegurar_2a_division_operativa():
    db = st.session_state.db
    liga1 = db["ligas"]["1ª División"]
    liga2 = db["ligas"]["2ª División"]

    if not liga2["equipos"]:
        base_2a = [
            "ATLÉTICO NORTE", "REAL COSTA", "UNIÓN SUR", "SPORTING OESTE",
            "RACING VERDE", "OLÍMPICO AZUL", "VILLA ROJA", "DEPORTIVO LAGO",
            "MONTAÑA FC", "PUERTO CLUB"
        ]
        for nombre in base_2a:
            if nombre not in db["equipos_data"]:
                db["equipos_data"][nombre] = {
                    "liga": "2ª División",
                    "escudo": "ðŸ”¹",
                    "jugadores": [
                        {"nombre": f"{nombre} POR A", "media": random.randint(68, 76), "valor": random.randint(2, 8), "pos": "POR"},
                        {"nombre": f"{nombre} POR B", "media": random.randint(62, 72), "valor": random.randint(1, 5), "pos": "POR"},
                        {"nombre": f"{nombre} JUG 1", "media": random.randint(68, 78), "valor": random.randint(2, 8), "pos": "JUG"},
                        {"nombre": f"{nombre} JUG 2", "media": random.randint(66, 76), "valor": random.randint(2, 7), "pos": "JUG"},
                        {"nombre": f"{nombre} JUG 3", "media": random.randint(64, 74), "valor": random.randint(1, 6), "pos": "JUG"},
                        {"nombre": f"{nombre} JUG 4", "media": random.randint(63, 73), "valor": random.randint(1, 5), "pos": "JUG"},
                    ]
                }
            liga2["equipos"].append(nombre)
        sanear_jugadores(db)

    for eq in liga1["equipos"]:
        liga1["historial_clubes"].setdefault(eq, [])
    for eq in liga2["equipos"]:
        liga2["historial_clubes"].setdefault(eq, [])

    if not liga2["calendario"] and len(liga2["equipos"]) >= 2:
        liga2["calendario"] = generar_calendario(liga2["equipos"])

def init_db():
    if "db" not in st.session_state:
        st.session_state.db = copy.deepcopy(DATOS_INICIALES)

    preparar_db_cargada(st.session_state.db)
    reconstruir_jornada_desde_resultados(st.session_state.db)
    asegurar_2a_division_operativa()
    inicializar_presupuestos()
    st.session_state.db.setdefault("jugadores_retirados", [])

def update_valor_temporada(j):
    if j["partidos"] <= 0:
        return

    media = j["nota_total"] / j["partidos"]
    edad = j.get("edad", 25)
    valor_actual = float(j.get("valor", 1.0))
    equipo_actual = j.get("equipo_actual", "")

    cambio_pct = 0.0

    if media >= 8.5:
        cambio_pct += 0.12
    elif media >= 7.8:
        cambio_pct += 0.07
    elif media <= 5.5:
        cambio_pct -= 0.15
    elif media <= 6.0:
        cambio_pct -= 0.08

    if edad <= 21 and media >= 7.0:
        cambio_pct += 0.05
    if edad >= 30 and media <= 7.0:
        cambio_pct -= 0.05

    # BONUS: Jugadores de filial/Sub-19 que juegan en primer equipo
    if es_equipo_sub19(equipo_actual) or equipo_actual.endswith(" B") or equipo_actual.endswith(" C"):
        # Si tiene ficha o promoción con primer equipo, bonus de crecimiento
        if j.get("ficha_primer_equipo", False) or j.get("promocion_temporal", False):
            club_principal = obtener_club_principal(equipo_actual)
            # Bonus extra de crecimiento (50-100% más que lo normal)
            if edad <= 19:
                cambio_pct *= 1.8  # 80% más de crecimiento
            elif edad <= 21:
                cambio_pct *= 1.5  # 50% más de crecimiento

    if valor_actual >= 35:
        cambio_pct *= 0.35
    elif valor_actual >= 25:
        cambio_pct *= 0.50
    elif valor_actual >= 15:
        cambio_pct *= 0.70
    elif valor_actual >= 8:
        cambio_pct *= 0.85

    cambio_valor = round(valor_actual * cambio_pct, 1)

    if cambio_pct > 0:
        cambio_valor = max(0.1, cambio_valor)
    elif cambio_pct < 0:
        cambio_valor = min(-0.1, cambio_valor)

    nuevo_valor = max(0.1, round(valor_actual + cambio_valor, 1))
    j["valor"] = nuevo_valor

    limitar_valor_por_liga(j, j.get("equipo_actual", ""))
    j["historial_valor"].append(j["valor"])

def cargar_partida_callback():
    up = st.session_state.get("uploader_partida")
    if up is None:
        return
    up.seek(0)
    db = json.load(up)
    preparar_db_cargada(db)
    reconstruir_jornada_desde_resultados(st.session_state.db)
    st.session_state.db = db
    st.session_state.partida_cargada_ok = True

def registrar_historial_clubes_temporada(nombre_liga, df_clasif):
    db = st.session_state.db
    liga = db["ligas"][nombre_liga]
    for pos, equipo in enumerate(df_clasif.index.tolist(), start=1):
        puntos = int(df_clasif.loc[equipo, "Pts"])
        liga["historial_clubes"].setdefault(equipo, [])
        liga["historial_clubes"][equipo].append({
            "temporada": db["config"]["temporada"],
            "liga": nombre_liga,
            "posicion": pos,
            "puntos": puntos
        })

def repartir_premios_clasificacion(nombre_liga, df_clasificacion):
    db = st.session_state.db
    temporada = db["config"]["temporada"]

    premios_liga = PREMIOS_CLASIFICACION_PAIS.get(nombre_liga)

    if not premios_liga or df_clasificacion.empty:
        return

    db.setdefault("mercado_log", [])

    for posicion, equipo in enumerate(
        df_clasificacion.index.tolist(),
        start=1
    ):
        premio = premios_liga.get(posicion)

        if premio is None:
            continue

        equipo_data = db["equipos_data"].get(equipo)

        if equipo_data is None:
            continue

        presupuesto_actual = float(
            equipo_data.get("presupuesto", 0)
        )

        equipo_data["presupuesto"] = round(
            presupuesto_actual + premio,
            2
        )

        db.setdefault("movimientos_presupuesto", []).append({
        "equipo": equipo,
        "temporada": db["config"]["temporada"],
        "tipo": "ingreso",
        "concepto": f"Premio por finalizar {posicion}º en {nombre_liga}",
        "importe": premio
        })

        db["mercado_log"].append(
            f"💰 {equipo} recibe "
            f"{formatear_valor(premio)} por finalizar "
            f"{posicion}º en {nombre_liga} "
            f"(Temporada {temporada})"
        )

def render_presupuesto_club(equipo):
    db = st.session_state.db
    equipo_data = db["equipos_data"].get(equipo)

    if not equipo_data:
        st.warning(f"No se encontró información de {equipo}")
        return

    presupuesto_actual = equipo_data.get("presupuesto", 0)

    st.subheader(f"💰 Presupuesto de {equipo}")
    st.metric("Saldo actual", f"{presupuesto_actual:.2f} M€")

    movimientos = db.get("movimientos_presupuesto", [])
    movimientos_club = [m for m in movimientos if m.get("equipo") == equipo]

    if movimientos_club:
        df_mov = pd.DataFrame(movimientos_club)

        # Formatear importe
        df_mov["importe_fmt"] = df_mov["importe"].apply(
            lambda x: f"{x:.2f} M€" if isinstance(x, (int, float)) else str(x)
        )

        df_mostrar = df_mov[["temporada", "tipo", "concepto", "importe_fmt"]].rename(
            columns={
                "temporada": "Temporada",
                "tipo": "Tipo",
                "concepto": "Concepto",
                "importe_fmt": "Importe"
            }
        )

        st.subheader("Movimientos de presupuesto")
        st.dataframe(
            df_mostrar.sort_values("Temporada", ascending=False),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No hay movimientos de presupuesto registrados aún.")
        
def clasificacion_liga(liga):
    tabla = {e: {"PJ": 0, "PG": 0, "PE": 0, "PP": 0, "GF": 0, "GC": 0, "Pts": 0} for e in liga["equipos"]}
    for r in liga["resultados"]:
        l, v = r["local"], r["visitante"]
        g1, g2 = r["goles1"], r["goles2"]
        tabla[l]["PJ"] += 1; tabla[v]["PJ"] += 1
        tabla[l]["GF"] += g1; tabla[l]["GC"] += g2
        tabla[v]["GF"] += g2; tabla[v]["GC"] += g1
        if g1 > g2:
            tabla[l]["PG"] += 1; tabla[v]["PP"] += 1; tabla[l]["Pts"] += 3
        elif g2 > g1:
            tabla[v]["PG"] += 1; tabla[l]["PP"] += 1; tabla[v]["Pts"] += 3
        else:
            tabla[l]["PE"] += 1; tabla[v]["PE"] += 1
            tabla[l]["Pts"] += 1; tabla[v]["Pts"] += 1
    df = pd.DataFrame.from_dict(tabla, orient="index")
    if not df.empty:
        df["DG"] = df["GF"] - df["GC"]
        df = df.sort_values(["Pts", "DG", "GF"], ascending=False)
        df.index.name = "Equipo"
    return df

def resolver_eliminatoria_ida_vuelta(eq1, eq2):
    ida_1 = random.randint(0, 4)
    ida_2 = random.randint(0, 4)
    vuelta_2 = random.randint(0, 4)
    vuelta_1 = random.randint(0, 4)

    total_eq1 = ida_1 + vuelta_1
    total_eq2 = ida_2 + vuelta_2

    if total_eq1 > total_eq2:
        ganador = eq1
    elif total_eq2 > total_eq1:
        ganador = eq2
    else:
        ganador = eq1 if random.random() < 0.5 else eq2

    detalle = (
        f"{eq1} {ida_1}-{ida_2} {eq2} | "
        f"{eq2} {vuelta_2}-{vuelta_1} {eq1} -> "
        f"Asciende en la eliminatoria: {ganador}"
    )
    return ganador, detalle

def crear_playoff_ascenso_3a(df_grupo):
    equipos = df_grupo.iloc[1:5].index.tolist()
    if len(equipos) < 4:
        return None

    segundo, tercero, cuarto, quinto = equipos

    return {
        "activo": True,
        "equipos": equipos,
        "calendario": [
            {
                "nombre": "Semifinal 1 · Ida",
                "fase": "semis",
                "partidos": [(segundo, quinto)]
            },
            {
                "nombre": "Semifinal 2 · Ida",
                "fase": "semis",
                "partidos": [(tercero, cuarto)]
            },
            {
                "nombre": "Semifinal 1 · Vuelta",
                "fase": "semis",
                "partidos": [(quinto, segundo)]
            },
            {
                "nombre": "Semifinal 2 · Vuelta",
                "fase": "semis",
                "partidos": [(cuarto, tercero)]
            }
        ],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }

def jugar_playoff_ascenso_2a(df2):
    equipos = df2.iloc[2:6].index.tolist()

    if len(equipos) < 4:
        return None, [], []

    tercero, cuarto, quinto, sexto = equipos

    def simular_partido_playoff(local, visitante, etiqueta):
        g1 = random.randint(0, 4)
        g2 = random.randint(0, 4)

        eventos = []
        total_goles = g1 + g2

        posibles_local = [
            j["nombre"] for j in st.session_state.db["equipos_data"][local]["jugadores"]
            if j["pos"] != "POR"
        ]
        posibles_visitante = [
            j["nombre"] for j in st.session_state.db["equipos_data"][visitante]["jugadores"]
            if j["pos"] != "POR"
        ]

        minutos_usados = sorted(random.sample(range(2, 40), total_goles)) if total_goles > 0 else []

        for i in range(g1):
            goleador = random.choice(posibles_local) if posibles_local else "Jugador"
            eventos.append({
                "min": minutos_usados[i],
                "texto": f"⚽ GOL {goleador} ({local})"
            })

        for i in range(g2):
            goleador = random.choice(posibles_visitante) if posibles_visitante else "Jugador"
            eventos.append({
                "min": minutos_usados[g1 + i],
                "texto": f"⚽ GOL {goleador} ({visitante})"
            })

        eventos = sorted(eventos, key=lambda x: x["min"])

        return {
            "local": local,
            "visitante": visitante,
            "goles1": g1,
            "goles2": g2,
            "eventos": eventos,
            "notas_partido": [],
            "alineacion1": "Playoff ascenso",
            "alineacion2": "Playoff ascenso",
            "jornada_num": etiqueta
        }

    sf1 = simular_partido_playoff(tercero, sexto, "Playoff · Semifinal 1")
    sf2 = simular_partido_playoff(cuarto, quinto, "Playoff · Semifinal 2")

    if sf1["goles1"] > sf1["goles2"]:
        ganador_sf1 = sf1["local"]
    elif sf1["goles2"] > sf1["goles1"]:
        ganador_sf1 = sf1["visitante"]
    else:
        ganador_sf1 = random.choice([sf1["local"], sf1["visitante"]])
        sf1["eventos"].append({
            "min": 41,
            "texto": f"🎯 Pasa por penaltis: {ganador_sf1}"
        })

    if sf2["goles1"] > sf2["goles2"]:
        ganador_sf2 = sf2["local"]
    elif sf2["goles2"] > sf2["goles1"]:
        ganador_sf2 = sf2["visitante"]
    else:
        ganador_sf2 = random.choice([sf2["local"], sf2["visitante"]])
        sf2["eventos"].append({
            "min": 41,
            "texto": f"🎯 Pasa por penaltis: {ganador_sf2}"
        })

    final = simular_partido_playoff(ganador_sf1, ganador_sf2, "Playoff · Final")

    if final["goles1"] > final["goles2"]:
        ganador_final = final["local"]
    elif final["goles2"] > final["goles1"]:
        ganador_final = final["visitante"]
    else:
        ganador_final = random.choice([final["local"], final["visitante"]])
        final["eventos"].append({
            "min": 41,
            "texto": f"🎯 Asciende por penaltis: {ganador_final}"
        })

    final["eventos"].append({
        "min": 42,
        "texto": f"⬆️ Asciende a 1ª División: {ganador_final}"
    })

    logs = [
        f"🎟️ Playoff ascenso 2ª - Semifinal 1: {sf1['local']} {sf1['goles1']}-{sf1['goles2']} {sf1['visitante']}",
        f"🎟️ Playoff ascenso 2ª - Semifinal 2: {sf2['local']} {sf2['goles1']}-{sf2['goles2']} {sf2['visitante']}",
        f"🏆 Playoff ascenso 2ª - Final: {final['local']} {final['goles1']}-{final['goles2']} {final['visitante']}",
        f"⬆️ Asciende por playoff: {ganador_final}"
    ]

    partidos_playoff = [sf1, sf2, final]

    return ganador_final, logs, partidos_playoff

def crear_playoff_ascenso_2a(df2):
    equipos = df2.iloc[2:6].index.tolist()
    if len(equipos) < 4:
        return None

    tercero, cuarto, quinto, sexto = equipos

    return {
        "activo": True,
        "equipos": equipos,
        "calendario": [
            {
                "nombre": "Semifinal 1 · Ida",
                "fase": "semis",
                "partidos": [(tercero, sexto)]
            },
            {
                "nombre": "Semifinal 2 · Ida",
                "fase": "semis",
                "partidos": [(cuarto, quinto)]
            },
            {
                "nombre": "Semifinal 1 · Vuelta",
                "fase": "semis",
                "partidos": [(sexto, tercero)]
            },
            {
                "nombre": "Semifinal 2 · Vuelta",
                "fase": "semis",
                "partidos": [(quinto, cuarto)]
            }
        ],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }


def clasificar_final_playoff(playoff):
    res = playoff["resultados"]

    semi1 = [r for r in res if r["jornada_num"] in [1, 3]]
    semi2 = [r for r in res if r["jornada_num"] in [2, 4]]

    if len(semi1) < 2 or len(semi2) < 2:
        return None

    def ganador_eliminatoria(partidos):
        eq1 = partidos[0]["local"]
        eq2 = partidos[0]["visitante"]

        total_eq1 = 0
        total_eq2 = 0

        for p in partidos:
            if p["local"] == eq1:
                total_eq1 += p["goles1"]
                total_eq2 += p["goles2"]
            else:
                total_eq1 += p["goles2"]
                total_eq2 += p["goles1"]

        if total_eq1 > total_eq2:
            return eq1
        elif total_eq2 > total_eq1:
            return eq2
        else:
            # Empate global → penaltis
            penaltis_eq1 = random.randint(0, 5)
            penaltis_eq2 = random.randint(0, 5)
            ganador_penaltis = eq1 if penaltis_eq1 > penaltis_eq2 else eq2

            # Guardar penaltis por eliminatoria (semi1 / semi2)
            elim_key = "semi1" if partidos[0]["jornada_num"] in [1, 3] else "semi2"
            playoff.setdefault("penaltis_semis", {})
            playoff["penaltis_semis"][elim_key] = {
                "eq1": eq1,
                "eq2": eq2,
                "penaltis_eq1": penaltis_eq1,
                "penaltis_eq2": penaltis_eq2,
                "ganador": ganador_penaltis
            }

            # Añadir evento de penaltis al último partido de la eliminatoria
            ultimo_partido = partidos[-1]
            ultimo_partido["eventos"].append({
                "min": 91,
                "texto": f"🎯 Penaltis: {eq1} {penaltis_eq1} - {penaltis_eq2} {eq2} → Gana {ganador_penaltis}"
            })

            return ganador_penaltis

    ganador_semifinal_1 = ganador_eliminatoria(semi1)
    ganador_semifinal_2 = ganador_eliminatoria(semi2)

    if not ganador_semifinal_1 or not ganador_semifinal_2:
        return None

    return ganador_semifinal_1, ganador_semifinal_2


def ganador_final_playoff(playoff):
    res = playoff["resultados"]
    finales = [r for r in res if r["jornada_num"] in [5, 6]]

    if len(finales) < 2:
        return None

    eq1 = finales[0]["local"]
    eq2 = finales[0]["visitante"]

    total_eq1 = 0
    total_eq2 = 0

    for p in finales:
        if p["local"] == eq1:
            total_eq1 += p["goles1"]
            total_eq2 += p["goles2"]
        else:
            total_eq1 += p["goles2"]
            total_eq2 += p["goles1"]

    if total_eq1 > total_eq2:
        return eq1
    elif total_eq2 > total_eq1:
        return eq2
    else:
        # Empate global → penaltis
        penaltis_eq1 = random.randint(0, 5)
        penaltis_eq2 = random.randint(0, 5)
        ganador_penaltis = eq1 if penaltis_eq1 > penaltis_eq2 else eq2

        # Guardar info de penaltis en el playoff
        playoff.setdefault("penaltis_final", {})
        playoff["penaltis_final"] = {
            "eq1": eq1,
            "eq2": eq2,
            "penaltis_eq1": penaltis_eq1,
            "penaltis_eq2": penaltis_eq2,
            "ganador": ganador_penaltis
        }

        # Añadir evento de penaltis al último partido de la final
        ultimo_partido = finales[-1]
        ultimo_partido["eventos"].append({
            "min": 91,
            "texto": f"🎯 Penaltis final: {eq1} {penaltis_eq1} - {penaltis_eq2} {eq2} → Gana {ganador_penaltis}"
        })

        return ganador_penaltis

def resetear_playoff():
    return {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }

def obtener_club_principal(equipo_nombre):
    """
    Devuelve el nombre del club principal.
    Ejemplo: 'RB Zerkas B' -> 'RB Zerkas', 'Saulo Sub-19' -> 'Saulo'.
    Ajusta esta lógica según cómo nombres a los filiales.
    """
    if equipo_nombre.endswith(" B"):
        return equipo_nombre[:-2]
    if equipo_nombre.endswith(" Sub-19"):
        return equipo_nombre.replace(" Sub-19", "")
    return equipo_nombre


def filtrar_ascensos_por_filialidad(equipo_asciende, liga_destino):
    """
    equipo_asciende: lista de nombres de equipos que quieren ascender.
    liga_destino: nombre de la liga de destino (ej. 'Com 1ª División').
    
    Devuelve una lista depurada de equipos que SÍ pueden ascender,
    y una lista con los que no pueden (por ser filiales de un equipo ya en esa liga).
    """
    db = st.session_state.db
    equipos_destino = db["ligas"][liga_destino]["equipos"]

    # Obtener clubes principales de los equipos que ya están en la liga destino
    clubes_en_destino = {obtener_club_principal(eq) for eq in equipos_destino}

    permitidos = []
    bloqueados = []

    for eq in equipo_asciende:
        club = obtener_club_principal(eq)
        if club in clubes_en_destino:
            bloqueados.append(eq)
        else:
            permitidos.append(eq)

    return permitidos, bloqueados


def aplicar_ascensos_con_filialidad(liga_origen, liga_destino, df_origen, n_ascensos_directos):
    """
    Aplica ascensos desde liga_origen a liga_destino, respetando la regla de filiales.
    df_origen: DataFrame de clasificación de la liga de origen.
    n_ascensos_directos: número de plazas directas de ascenso (ej. 2).
    """
    db = st.session_state.db
    movimientos = []

    # Posiciones teóricas de ascenso directo
    candidatos_ascenso = df_origen.head(n_ascensos_directos).index.tolist()

    # Filtrar por filialidad
    permitidos, bloqueados = filtrar_ascensos_por_filialidad(candidatos_ascenso, liga_destino)

    # Si hay bloqueados, rellenar con los siguientes no bloqueados
    while len(permitidos) < n_ascensos_directos:
        siguiente_pos = len(permitidos) + len(bloqueados)
        if siguiente_pos >= len(df_origen):
            break
        siguiente_eq = df_origen.iloc[siguiente_pos].name
        if siguiente_eq not in permitidos + bloqueados:
            nuevos_permitidos, nuevos_bloqueados = filtrar_ascensos_por_filialidad([siguiente_eq], liga_destino)
            permitidos.extend(nuevos_permitidos)
            bloqueados.extend(nuevos_bloqueados)
        else:
            break

    # Aplicar ascensos solo a los permitidos
    for eq in permitidos:
        if eq in db["ligas"][liga_origen]["equipos"]:
            db["ligas"][liga_origen]["equipos"].remove(eq)
            db["ligas"][liga_destino]["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = liga_destino
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬆️ {eq} asciende a {liga_destino}")

    return movimientos, bloqueados
def regularizar_filiales_en_liga(liga_nombre):
    """
    Si en una liga hay un filial y su club principal también está en esa liga,
    el filial desciende automáticamente a la división inferior (si existe),
    y asciende un equipo más desde abajo.
    """
    db = st.session_state.db
    liga = db["ligas"][liga_nombre]
    movimientos = []

    # Obtener clubes principales de los equipos en esta liga
    equipos = liga["equipos"][:]
    for eq in equipos:
        club = obtener_club_principal(eq)
        # Buscar si el club principal también está en esta liga
        principal_en_liga = any(
            obtener_club_principal(e) == club and e != eq
            for e in equipos
        )
        if principal_en_liga:
            # El filial debe bajar
            # Determinar liga inferior (mapeo simple)
            liga_inferior = None
            if liga_nombre == "2ª División":
                liga_inferior = "3ª División Grupo A"  # o B, se puede repartir
            elif liga_nombre == "3ª División Grupo A":
                liga_inferior = "4ª División"
            elif liga_nombre == "3ª División Grupo B":
                liga_inferior = "4ª División"
            # ... añadir más si hace falta

            if liga_inferior and eq in liga["equipos"]:
                # Bajar filial
                liga["equipos"].remove(eq)
                db["ligas"][liga_inferior]["equipos"].append(eq)
                db["equipos_data"][eq]["liga"] = liga_inferior
                for j in db["equipos_data"][eq]["jugadores"]:
                    j["equipo_actual"] = eq
                    limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                movimientos.append(f"⬇️ {eq} desciende automáticamente (filial de {club})")

                # Subir uno más desde la liga inferior
                df_inf = clasificacion_liga(db["ligas"][liga_inferior])
                if not df_inf.empty:
                    # El primero que no sea filial de alguien en esta liga
                    for candidato in df_inf.index:
                        club_candidato = obtener_club_principal(candidato)
                        if club_candidato not in {obtener_club_principal(e) for e in liga["equipos"]}:
                            # Ascender
                            db["ligas"][liga_inferior]["equipos"].remove(candidato)
                            liga["equipos"].append(candidato)
                            db["equipos_data"][candidato]["liga"] = liga_nombre
                            for j in db["equipos_data"][candidato]["jugadores"]:
                                j["equipo_actual"] = candidato
                                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                            movimientos.append(f"⬆️ {candidato} asciende (plaza por filial)")
                            break

    return movimientos

def aplicar_ascensos_descensos():
    db = st.session_state.db
    liga1 = db["ligas"]["1ª División"]
    liga2 = db["ligas"]["2ª División"]
    liga3a = db["ligas"]["3ª División Grupo A"]
    liga3b = db["ligas"]["3ª División Grupo B"]
    liga4 = db["ligas"]["4ª División"]

    if (
        not liga1["resultados"]
        or not liga2["resultados"]
        or not liga3a["resultados"]
        or not liga3b["resultados"]
        or not liga4["resultados"]
    ):
        return []

    df1 = clasificacion_liga(liga1)
    df2 = clasificacion_liga(liga2)
    df3a = clasificacion_liga(liga3a)
    df3b = clasificacion_liga(liga3b)
    df4 = clasificacion_liga(liga4)

    if (
        df1.empty or df2.empty or df3a.empty or df3b.empty or df4.empty
        or len(df1) < 3 or len(df2) < 6 or len(df3a) < 5 or len(df3b) < 5 or len(df4) < 4
    ):
        return []

    descienden_1a = df1.tail(3).index.tolist()
    descenso_2a = df2.tail(4).index.tolist()

    ascienden_directos_3a = [
        df3a.index[0],
        df3b.index[0]
    ]

    movimientos = []

    # === DESCENSOS 1ª -> 2ª ===
    for eq in descienden_1a:
        if eq in liga1["equipos"] and eq not in liga2["equipos"]:
            liga1["equipos"].remove(eq)
            liga2["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "2ª División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬇️ Desciende {eq} a 2ª División")

    # === ASCENSOS 2ª -> 1ª (CON FILIALES) ===
    clubes_en_1a = {obtener_club_principal(eq) for eq in liga1["equipos"]}
    candidatos_directos = df2.head(2).index.tolist()
    ascienden_2a = []
    for eq in candidatos_directos:
        club = obtener_club_principal(eq)
        if club in clubes_en_1a:
            movimientos.append(f"🚫 {eq} no asciende a 1ª División por ser filial de un equipo en 1ª División")
        else:
            ascienden_2a.append(eq)
            if eq in liga2["equipos"]:
                liga2["equipos"].remove(eq)
                liga1["equipos"].append(eq)
                db["equipos_data"][eq]["liga"] = "1ª División"
                for j in db["equipos_data"][eq]["jugadores"]:
                    j["equipo_actual"] = eq
                    limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                movimientos.append(f"⬆️ Asciende {eq} a 1ª División")

    # === PLAYOFF 2ª -> 1ª (CON FILIALES) ===
    playoff = db.get("playoff_2a", {})
    if playoff.get("activo"):
        ascenso_playoff = ganador_final_playoff(playoff)
        if ascenso_playoff:
            club = obtener_club_principal(ascenso_playoff)
            if club in clubes_en_1a:
                movimientos.append(f"🚫 {ascenso_playoff} no asciende (playoff) por ser filial de un equipo en 1ª División")
            else:
                if ascenso_playoff in liga2["equipos"]:
                    liga2["equipos"].remove(ascenso_playoff)
                    liga1["equipos"].append(ascenso_playoff)
                    db["equipos_data"][ascenso_playoff]["liga"] = "1ª División"
                    for j in db["equipos_data"][ascenso_playoff]["jugadores"]:
                        j["equipo_actual"] = ascenso_playoff
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬆️ Asciende {ascenso_playoff} a 1ª División (playoff)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "2ª División",
            "equipos": playoff.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff.get("resultados", [])),
            "ascendido": ascenso_playoff
        })

    # === DESCENSOS 2ª -> 3ª ===
    destinos_3a = ["3ª División Grupo A", "3ª División Grupo B"]
    i_destino = 0
    for eq in descenso_2a:
        if eq in liga2["equipos"]:
            liga2["equipos"].remove(eq)
            destino = destinos_3a[i_destino % 2]
            i_destino += 1
            db["ligas"][destino]["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = destino
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬇️ Desciende {eq} a {destino}")

    # === ASCENSOS 3ª -> 2ª (CON FILIALES: NO PUEDEN JUGAR PLAYOFF SI EL PRINCIPAL ESTÁ EN 2ª) ===
    clubes_en_2a = {obtener_club_principal(eq) for eq in liga2["equipos"]}

    # Ascensos directos desde 3ª
    for eq in ascienden_directos_3a:
        liga_origen = db["equipos_data"][eq]["liga"]
        club = obtener_club_principal(eq)
        if club in clubes_en_2a:
            movimientos.append(f"🚫 {eq} no asciende a 2ª División por ser filial de un equipo en 2ª División")
        else:
            if eq in db["ligas"][liga_origen]["equipos"]:
                db["ligas"][liga_origen]["equipos"].remove(eq)
                liga2["equipos"].append(eq)
                db["equipos_data"][eq]["liga"] = "2ª División"
                for j in db["equipos_data"][eq]["jugadores"]:
                    j["equipo_actual"] = eq
                    limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                movimientos.append(f"⬆️ Asciende {eq} a 2ª División")

    # === PLAYOFF 3ª -> 2ª (CON FILIALES) ===
    playoff_3a_a = db.get("playoff_3a_grupo_a", {})
    playoff_3a_b = db.get("playoff_3a_grupo_b", {})

    if playoff_3a_a.get("activo"):
        ascenso_playoff_3a_a = ganador_final_playoff(playoff_3a_a)
        if ascenso_playoff_3a_a:
            club = obtener_club_principal(ascenso_playoff_3a_a)
            if club in clubes_en_2a:
                movimientos.append(f"🚫 {ascenso_playoff_3a_a} no asciende (playoff 3A) por ser filial de un equipo en 2ª División")
            else:
                liga_origen = db["equipos_data"][ascenso_playoff_3a_a]["liga"]
                if ascenso_playoff_3a_a in db["ligas"][liga_origen]["equipos"]:
                    db["ligas"][liga_origen]["equipos"].remove(ascenso_playoff_3a_a)
                    liga2["equipos"].append(ascenso_playoff_3a_a)
                    db["equipos_data"][ascenso_playoff_3a_a]["liga"] = "2ª División"
                    for j in db["equipos_data"][ascenso_playoff_3a_a]["jugadores"]:
                        j["equipo_actual"] = ascenso_playoff_3a_a
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬆️ Asciende {ascenso_playoff_3a_a} a 2ª División (playoff 3A)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "3ª División Grupo A",
            "equipos": playoff_3a_a.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff_3a_a.get("resultados", [])),
            "ascendido": ascenso_playoff_3a_a
        })

    if playoff_3a_b.get("activo"):
        ascenso_playoff_3a_b = ganador_final_playoff(playoff_3a_b)
        if ascenso_playoff_3a_b:
            club = obtener_club_principal(ascenso_playoff_3a_b)
            if club in clubes_en_2a:
                movimientos.append(f"🚫 {ascenso_playoff_3a_b} no asciende (playoff 3B) por ser filial de un equipo en 2ª División")
            else:
                liga_origen = db["equipos_data"][ascenso_playoff_3a_b]["liga"]
                if ascenso_playoff_3a_b in db["ligas"][liga_origen]["equipos"]:
                    db["ligas"][liga_origen]["equipos"].remove(ascenso_playoff_3a_b)
                    liga2["equipos"].append(ascenso_playoff_3a_b)
                    db["equipos_data"][ascenso_playoff_3a_b]["liga"] = "2ª División"
                    for j in db["equipos_data"][ascenso_playoff_3a_b]["jugadores"]:
                        j["equipo_actual"] = ascenso_playoff_3a_b
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬆️ Asciende {ascenso_playoff_3a_b} a 2ª División (playoff 3B)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "3ª División Grupo B",
            "equipos": playoff_3a_b.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff_3a_b.get("resultados", [])),
            "ascendido": ascenso_playoff_3a_b
        })

    # === 4ª -> 3ª y 3ª -> 4ª ===
    descienden_3a_a = df3a.tail(2).index.tolist()
    descienden_3a_b = df3b.tail(2).index.tolist()
    ascienden_4a = df4.head(4).index.tolist()

    for eq in descienden_3a_a:
        if eq in liga3a["equipos"]:
            liga3a["equipos"].remove(eq)
            liga4["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "4ª División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬇️ Desciende {eq} a 4ª División")

    for eq in descienden_3a_b:
        if eq in liga3b["equipos"]:
            liga3b["equipos"].remove(eq)
            liga4["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "4ª División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬇️ Desciende {eq} a 4ª División")

    for i, eq in enumerate(ascienden_4a):
        if eq in liga4["equipos"]:
            liga4["equipos"].remove(eq)
            destino = "3ª División Grupo A" if i < 2 else "3ª División Grupo B"
            db["ligas"][destino]["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = destino
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, j.get("equipo_actual", ""))
            movimientos.append(f"⬆️ Asciende {eq} a {destino}")

    # === REGULARIZAR FILIALES EN 2ª DIVISIÓN ===
    movimientos_filiales = regularizar_filiales_en_liga("2ª División")
    movimientos.extend(movimientos_filiales)

    db["playoff_2a"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }
    db["playoff_3a_grupo_a"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }
    db["playoff_3a_grupo_b"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }

    return movimientos

def aplicar_ascensos_descensos_sub19():
    db = st.session_state.db

    liga1 = db["ligas"]["Sub-19 1 División"]
    liga2 = db["ligas"]["Sub-19 2 División"]
    liga3a = db["ligas"]["Sub-19 3 División Grupo A"]
    liga3b = db["ligas"]["Sub-19 3 División Grupo B"]

    if (
        not liga1["resultados"]
        or not liga2["resultados"]
        or not liga3a["resultados"]
        or not liga3b["resultados"]
    ):
        return []

    df1 = clasificacion_liga(liga1)
    df2 = clasificacion_liga(liga2)
    df3a = clasificacion_liga(liga3a)
    df3b = clasificacion_liga(liga3b)

    if (
        df1.empty or df2.empty or df3a.empty or df3b.empty
        or len(df1) < 3 or len(df2) < 6 or len(df3a) < 5 or len(df3b) < 5
    ):
        return []

    movimientos = []

    descienden_1a = df1.tail(3).index.tolist()
    descenso_2a = df2.tail(4).index.tolist()
    ascienden_directos_3a = [df3a.index[0], df3b.index[0]]

    # === DESCENSOS 1ª -> 2ª ===
    for eq in descienden_1a:
        if eq in liga1["equipos"] and eq not in liga2["equipos"]:
            liga1["equipos"].remove(eq)
            liga2["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "Sub-19 2 División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, eq)
            movimientos.append(f"Desciende {eq} a Sub-19 2 División")

    # === ASCENSOS 2ª -> 1ª ===
    for eq in df2.head(2).index.tolist():
        if eq in liga2["equipos"] and eq not in liga1["equipos"]:
            liga2["equipos"].remove(eq)
            liga1["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "Sub-19 1 División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, eq)
            movimientos.append(f"Asciende {eq} a Sub-19 1 División")

    # === PLAYOFF 2ª -> 1ª ===
    playoff2a = db.get("playoff_sub19_2a", {})
    if playoff2a.get("activo"):
        ascenso_playoff_2a = ganador_final_playoff(playoff2a)
        if ascenso_playoff_2a and ascenso_playoff_2a in liga2["equipos"]:
            liga2["equipos"].remove(ascenso_playoff_2a)
            liga1["equipos"].append(ascenso_playoff_2a)
            db["equipos_data"][ascenso_playoff_2a]["liga"] = "Sub-19 1 División"
            for j in db["equipos_data"][ascenso_playoff_2a]["jugadores"]:
                j["equipo_actual"] = ascenso_playoff_2a
                limitar_valor_por_liga(j, ascenso_playoff_2a)
            movimientos.append(f"Asciende {ascenso_playoff_2a} a Sub-19 1 División (playoff)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "Sub-19 2 División",
            "equipos": playoff2a.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff2a.get("resultados", [])),
            "ascendido": ascenso_playoff_2a
        })

    # === DESCENSOS 2ª -> 3ª ===
    destinos_3a = ["Sub-19 3 División Grupo A", "Sub-19 3 División Grupo B"]
    i_destino = 0
    for eq in descenso_2a:
        if eq in liga2["equipos"]:
            liga2["equipos"].remove(eq)
            destino = destinos_3a[i_destino % 2]
            i_destino += 1
            db["ligas"][destino]["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = destino
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, eq)
            movimientos.append(f"Desciende {eq} a {destino}")

    # === ASCENSOS 3ª -> 2ª DIRECTOS ===
    for eq in ascienden_directos_3a:
        liga_origen = db["equipos_data"][eq]["liga"]
        if eq in db["ligas"][liga_origen]["equipos"]:
            db["ligas"][liga_origen]["equipos"].remove(eq)
            liga2["equipos"].append(eq)
            db["equipos_data"][eq]["liga"] = "Sub-19 2 División"
            for j in db["equipos_data"][eq]["jugadores"]:
                j["equipo_actual"] = eq
                limitar_valor_por_liga(j, eq)
            movimientos.append(f"Asciende {eq} a Sub-19 2 División (directo)")

    # === PLAYOFF 3ª -> 2ª ===
    playoff3a = db.get("playoff_sub19_3agrupoa", {})
    if playoff3a.get("activo"):
        ascenso_playoff_3a = ganador_final_playoff(playoff3a)
        if ascenso_playoff_3a and ascenso_playoff_3a in db["equipos_data"]:
            liga_origen = db["equipos_data"][ascenso_playoff_3a]["liga"]
            if ascenso_playoff_3a in db["ligas"][liga_origen]["equipos"]:
                db["ligas"][liga_origen]["equipos"].remove(ascenso_playoff_3a)
                liga2["equipos"].append(ascenso_playoff_3a)
                db["equipos_data"][ascenso_playoff_3a]["liga"] = "Sub-19 2 División"
                for j in db["equipos_data"][ascenso_playoff_3a]["jugadores"]:
                    j["equipo_actual"] = ascenso_playoff_3a
                    limitar_valor_por_liga(j, ascenso_playoff_3a)
                movimientos.append(f"Asciende {ascenso_playoff_3a} a Sub-19 2 División (playoff 3A)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "Sub-19 3 División Grupo A",
            "equipos": playoff3a.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff3a.get("resultados", [])),
            "ascendido": ascenso_playoff_3a
        })

    playoff3b = db.get("playoff_sub19_3agrupob", {})
    if playoff3b.get("activo"):
        ascenso_playoff_3b = ganador_final_playoff(playoff3b)
        if ascenso_playoff_3b and ascenso_playoff_3b in db["equipos_data"]:
            liga_origen = db["equipos_data"][ascenso_playoff_3b]["liga"]
            if ascenso_playoff_3b in db["ligas"][liga_origen]["equipos"]:
                db["ligas"][liga_origen]["equipos"].remove(ascenso_playoff_3b)
                liga2["equipos"].append(ascenso_playoff_3b)
                db["equipos_data"][ascenso_playoff_3b]["liga"] = "Sub-19 2 División"
                for j in db["equipos_data"][ascenso_playoff_3b]["jugadores"]:
                    j["equipo_actual"] = ascenso_playoff_3b
                    limitar_valor_por_liga(j, ascenso_playoff_3b)
                movimientos.append(f"Asciende {ascenso_playoff_3b} a Sub-19 2 División (playoff 3B)")

        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": db["config"]["temporada"],
            "liga": "Sub-19 3 División Grupo B",
            "equipos": playoff3b.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff3b.get("resultados", [])),
            "ascendido": ascenso_playoff_3b
        })

    # === RESET PLAYOFFS ===
    db["playoff_sub19_2a"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }
    db["playoff_sub19_3agrupoa"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }
    db["playoff_sub19_3agrupob"] = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }

    return movimientos

def aplicar_ascensos_descensos_nacionales():
    """
    Com, Tengu y Folimón (senior):
      1ª División <-> 2ª División
      2 ascensos directos, 2 descensos directos, sin playoffs.
    """
    db = st.session_state.db
    movimientos = []

    # === COM ===
    liga1_com = db["ligas"]["Com 1ª División"]
    liga2_com = db["ligas"]["Com 2ª División"]

    if liga1_com["resultados"] and liga2_com["resultados"]:
        df1 = clasificacion_liga(liga1_com)
        df2 = clasificacion_liga(liga2_com)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            # Descienden 2 de Com 1ª
            for eq in df1.tail(2).index.tolist():
                if eq in liga1_com["equipos"]:
                    liga1_com["equipos"].remove(eq)
                    liga2_com["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Com 2ª División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬇️ Com: {eq} desciende a Com 2ª División")

            # Ascienden 2 de Com 2ª (con regla de filiales)
            movimientos_ascenso, bloqueados = aplicar_ascensos_con_filialidad(
                "Com 2ª División", "Com 1ª División", df2, n_ascensos_directos=2
            )
            movimientos.extend(movimientos_ascenso)
            for eq in bloqueados:
                movimientos.append(f"🚫 Com: {eq} no asciende por ser filial de un equipo en Com 1ª División")

    # === TENGU ===
    liga1_tengu = db["ligas"]["Tengu 1ª División"]
    liga2_tengu = db["ligas"]["Tengu 2ª División"]

    if liga1_tengu["resultados"] and liga2_tengu["resultados"]:
        df1 = clasificacion_liga(liga1_tengu)
        df2 = clasificacion_liga(liga2_tengu)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            for eq in df1.tail(2).index.tolist():
                if eq in liga1_tengu["equipos"]:
                    liga1_tengu["equipos"].remove(eq)
                    liga2_tengu["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Tengu 2ª División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬇️ Tengu: {eq} desciende a Tengu 2ª División")

            # Ascienden 2 de Tengu 2ª (con regla de filiales)
            movimientos_ascenso, bloqueados = aplicar_ascensos_con_filialidad(
                "Tengu 2ª División", "Tengu 1ª División", df2, n_ascensos_directos=2
            )
            movimientos.extend(movimientos_ascenso)
            for eq in bloqueados:
                movimientos.append(f"🚫 Tengu: {eq} no asciende por ser filial de un equipo en Tengu 1ª División")

    # === FOLIMÓN ===
    liga1_folimon = db["ligas"]["Folimón 1ª División"]
    liga2_folimon = db["ligas"]["Folimón 2ª División"]

    if liga1_folimon["resultados"] and liga2_folimon["resultados"]:
        df1 = clasificacion_liga(liga1_folimon)
        df2 = clasificacion_liga(liga2_folimon)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            for eq in df1.tail(2).index.tolist():
                if eq in liga1_folimon["equipos"]:
                    liga1_folimon["equipos"].remove(eq)
                    liga2_folimon["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Folimón 2ª División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, j.get("equipo_actual", ""))
                    movimientos.append(f"⬇️ Folimón: {eq} desciende a Folimón 2ª División")

            # Ascienden 2 de Folimón 2ª (con regla de filiales)
            movimientos_ascenso, bloqueados = aplicar_ascensos_con_filialidad(
                "Folimón 2ª División", "Folimón 1ª División", df2, n_ascensos_directos=2
            )
            movimientos.extend(movimientos_ascenso)
            for eq in bloqueados:
                movimientos.append(f"🚫 Folimón: {eq} no asciende por ser filial de un equipo en Folimón 1ª División")

    return movimientos


def aplicar_ascensos_descensos_nacionales_sub19():
    """
    Com, Tengu y Folimón (Sub‑19):
      Sub‑19 1 División <-> Sub‑19 2 División
      2 ascensos directos, 2 descensos directos, sin playoffs.
    """
    db = st.session_state.db
    movimientos = []

    # === COM SUB‑19 ===
    liga1 = db["ligas"]["Com Sub-19 1 División"]
    liga2 = db["ligas"]["Com Sub-19 2 División"]

    if liga1["resultados"] and liga2["resultados"]:
        df1 = clasificacion_liga(liga1)
        df2 = clasificacion_liga(liga2)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            for eq in df1.tail(2).index.tolist():
                if eq in liga1["equipos"]:
                    liga1["equipos"].remove(eq)
                    liga2["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Com Sub-19 2 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Com Sub-19: {eq} desciende a Com Sub-19 2 División")

            for eq in df2.head(2).index.tolist():
                if eq in liga2["equipos"]:
                    liga2["equipos"].remove(eq)
                    liga1["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Com Sub-19 1 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Com Sub-19: {eq} asciende a Com Sub-19 1 División")

    # === TENGU SUB‑19 ===
    liga1 = db["ligas"]["Tengu Sub-19 1 División"]
    liga2 = db["ligas"]["Tengu Sub-19 2 División"]

    if liga1["resultados"] and liga2["resultados"]:
        df1 = clasificacion_liga(liga1)
        df2 = clasificacion_liga(liga2)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            for eq in df1.tail(2).index.tolist():
                if eq in liga1["equipos"]:
                    liga1["equipos"].remove(eq)
                    liga2["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Tengu Sub-19 2 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Tengu Sub-19: {eq} desciende a Tengu Sub-19 2 División")

            for eq in df2.head(2).index.tolist():
                if eq in liga2["equipos"]:
                    liga2["equipos"].remove(eq)
                    liga1["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Tengu Sub-19 1 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Tengu Sub-19: {eq} asciende a Tengu Sub-19 1 División")

    # === FOLIMÓN SUB‑19 ===
    liga1 = db["ligas"]["Folimón Sub-19 1 División"]
    liga2 = db["ligas"]["Folimón Sub-19 2 División"]

    if liga1["resultados"] and liga2["resultados"]:
        df1 = clasificacion_liga(liga1)
        df2 = clasificacion_liga(liga2)

        if not df1.empty and not df2.empty and len(df1) >= 2 and len(df2) >= 2:
            for eq in df1.tail(2).index.tolist():
                if eq in liga1["equipos"]:
                    liga1["equipos"].remove(eq)
                    liga2["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Folimón Sub-19 2 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Folimón Sub-19: {eq} desciende a Folimón Sub-19 2 División")

            for eq in df2.head(2).index.tolist():
                if eq in liga2["equipos"]:
                    liga2["equipos"].remove(eq)
                    liga1["equipos"].append(eq)
                    db["equipos_data"][eq]["liga"] = "Folimón Sub-19 1 División"
                    for j in db["equipos_data"][eq]["jugadores"]:
                        j["equipo_actual"] = eq
                        limitar_valor_por_liga(j, eq)
                    movimientos.append(f"Folimón Sub-19: {eq} asciende a Folimón Sub-19 1 División")

    return movimientos

def mostrar_playoff_streamlit(db, liga_activa, nombre_liga_objetivo, clave_playoff, slider_key, sim_key_prefix):
    """
    Pinta un playoff (2ª o 3ª) con la misma lógica que el de 2ª.
    """
    if liga_activa != nombre_liga_objetivo:
        return

    playoff = db.get(clave_playoff, {})
    if not playoff or not playoff.get("activo", False):
        return

    if not playoff.get("calendario") or not playoff.get("equipos"):
        db[clave_playoff] = {
            "activo": False,
            "equipos": [],
            "calendario": [],
            "resultados": [],
            "jornada": 0,
            "ganadores_semis": []
        }
        return

    st.divider()
    st.subheader(f"🎟️ Playoff de ascenso - {nombre_liga_objetivo}")

    cal = playoff.get("calendario", [])
    j_actual = playoff.get("jornada", 0)

    if not cal:
        st.info("Todavía no hay calendario de playoff generado.")
        return

    j_max = len(cal)
    prox = min(j_actual + 1, j_max)
    if prox <= 0:
        prox = 1

    j_view = st.slider(
        "Jornada playoff:",
        1,
        j_max,
        prox,
        key=slider_key
    )

    bloque = cal[j_view - 1]
    st.markdown(f"**{bloque['nombre']}**")

    # SI YA ESTÁ JUGADA ESA JORNADA
    if j_view <= j_actual:
        partidos = [r for r in playoff["resultados"] if r.get("jornada_num") == j_view]

        for r in partidos:
            with st.expander(f"{r['local']} {r['goles1']} - {r['goles2']} {r['visitante']}"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**{r['local']}**")
                c1.caption(f"11: {r.get('alineacion1', '-')}")
                c2.markdown(f"**{r['visitante']}**")
                c2.caption(f"11: {r.get('alineacion2', '-')}")
                st.divider()
                for ev in sorted(r.get("eventos", []), key=lambda x: x.get("min", 0)):
                    st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")
                st.divider()
                notas = r.get("notas_partido", [])
                if notas:
                    st.dataframe(pd.DataFrame(notas), hide_index=True, use_container_width=True)

    # SI ES LA PRÓXIMA JORNADA DE PLAYOFF
    elif j_view == j_actual + 1:
        # Mostrar emparejamientos
        for local, visitante in bloque["partidos"]:
            st.write(f"🔹 {local} vs {visitante}")

        if st.button(
            "▶️ SIMULAR JORNADA PLAYOFF",
            type="primary",
            key=f"{sim_key_prefix}_{j_view}"
        ):
            for local, visitante in bloque["partidos"]:
                res = simular_partido(local, visitante, jornada_actual=f"playoff_{clave_playoff}_{j_view}")
                res["jornada_num"] = j_view
                res["jornada_nombre"] = bloque["nombre"]
                playoff["resultados"].append(res)

            playoff["jornada"] = j_view

            # Al acabar las semifinales (jornada 4) se generan las finales
            if j_view == 4:
                ganadores = clasificar_final_playoff(playoff)

                if ganadores and len(playoff["calendario"]) == 4:
                    ganador_semifinal_1, ganador_semifinal_2 = ganadores

                    playoff["calendario"].extend([
                        {
                            "nombre": "Final · Ida",
                            "fase": "final",
                            "partidos": [(ganador_semifinal_1, ganador_semifinal_2)]
                        },
                        {
                            "nombre": "Final · Vuelta",
                            "fase": "final",
                            "partidos": [(ganador_semifinal_2, ganador_semifinal_1)]
                        }
                    ])

                    playoff["ganadores_semis"] = [
                        ganador_semifinal_1,
                        ganador_semifinal_2,
                    ]

            # Al acabar las finales (jornada 6) se saca el ganador del playoff
            if j_view == 6:
                ascendido = ganador_final_playoff(playoff)
                if ascendido:
                    db.setdefault("mercado_log", [])
                    db["mercado_log"].append(
                        f"⬆️ Asciende por playoff ({nombre_liga_objetivo}): {ascendido}"
                    )

            recargar()

    else:
        st.warning("Debes jugar el playoff en orden.")

def registrar_traspaso(jugador, origen, destino, tipo="traspaso", temporada=None, valor=None):
    db = st.session_state.db
    if temporada is None:
        temporada = db["config"]["temporada"]
    mov = {
        "temporada": temporada,
        "jugador": jugador["nombre"],
        "origen": origen,
        "destino": destino,
        "tipo": tipo,
        "valor": valor if valor is not None else jugador["valor"]
    }
    db["historial_traspasos"].append(mov)
    jugador["historial_traspasos"].append(mov.copy())

def oferta_aceptable_para_usuario(
    origen,
    destino,
    jugador,
    tipo,
    cantidad,
    duracion=1,
    opcion_compra=False,
    precio_opcion_compra=0
):
    """
    Comprueba si una oferta que sale desde un club del usuario
    podría aceptarse actualmente.
    """

    clubes_usuario = {
        "CEREZAS",
        "CEREZAS B",
        "CEREZAS Sub-19",
        "RB Zerkas",
        "RB Zerkas B",
        "RB Zerkas Sub-19",
        "EKIPO",
        "EQUPO Sub-19",
    }

    # Solo filtramos las ofertas cuyo origen es un club del usuario.
    if origen not in clubes_usuario:
        return True, None

    db = st.session_state.db
    equipos_data = db.get("equipos_data", {})

    if origen not in equipos_data:
        return False, "El club de origen no existe."

    if destino not in equipos_data:
        return False, "El club destino no existe."

    jugadores_origen = equipos_data[origen].get("jugadores", [])

    jugador_obj = next(
        (
            j for j in jugadores_origen
            if j.get("nombre") == jugador
        ),
        None
    )

    if jugador_obj is None:
        return False, "El jugador ya no pertenece al club de origen."

    if jugador_obj.get("cedido", False):
        return False, "El jugador ya está cedido."

    if son_clubes_vinculados(origen, destino):
        return False, "No se permiten operaciones entre clubes vinculados."

    tipo = str(tipo).lower().strip()

    # Comprobar porteros: el club vendedor debe conservar al menos uno.
    if jugador_obj.get("pos") == "POR":
        porteros = sum(
            1 for j in jugadores_origen
            if j.get("pos") == "POR"
            and not j.get("cedido", False)
        )

        if porteros <= 1:
            return False, "El club se quedaría sin porteros."

    # NUEVO: Control de nivel/encaje (igual que en hacer_traspaso y hacer_cesion)
    if not destino_puede_ficharlo(origen, destino, jugador_obj):
        return False, (
            f"{destino} no es un destino lógico para {jugador} "
            "por nivel o encaje de plantilla."
        )

    # Las cesiones no añaden permanentemente un jugador al destino,
    # pero sí deben tener un destino válido.
    if tipo == "cesion":
        return True, None

    # Desde aquí comprobamos los traspasos definitivos.
    jugadores_destino = equipos_data[destino].get("jugadores", [])

    # El destino no puede superar el tamaño permitido.
    max_jugadores = (
        10
        if es_equipo_sub19(destino)
        else 8
    )

    if len(jugadores_destino) >= max_jugadores:
        return False, (
            f"{destino} ya tiene el máximo de "
            f"{max_jugadores} jugadores."
        )

    # Si es primer equipo, comprobar también los límites del club.
    if es_equipo_principal(destino):
        club_principal = obtener_club_principal(destino)

        if club_principal in equipos_data:
            jugadores_primer_equipo = equipos_data[
                club_principal
            ].get("jugadores", [])

            jugadores_permanentes = [
                j for j in jugadores_primer_equipo
                if not j.get("promocion_temporal", False)
            ]

            if len(jugadores_permanentes) >= 7:
                return False, (
                    f"{club_principal} ya tiene "
                    "7 jugadores permanentes."
                )

            if len(jugadores_primer_equipo) >= 10:
                return False, (
                    f"{club_principal} ya tiene "
                    "10 jugadores efectivos."
                )

    # El comprador debe poder pagar el traspaso.
    precio = float(cantidad or 0)

    presupuesto_comprador = obtener_presupuesto_equipo(destino)

    if presupuesto_comprador < precio:
        return False, (
            f"{destino} no tiene presupuesto suficiente."
        )

    # Si hay opción de compra, comprobar que el precio sea válido.
    if opcion_compra:
        precio_opcion = float(precio_opcion_compra or 0)

        if precio_opcion <= 0:
            return False, (
                "La opción de compra debe tener un precio válido."
            )

    return True, None

def oferta_aceptable_para_ia(origen, destino, jugador, tipo, cantidad, duracion, opcion_compra, precio_opcion_compra):
    """
    Versión flexible para ofertas entre clubes IA.
    - Máximo 2 niveles de diferencia.
    - Prioriza mejorar la plantilla (fichar jugadores de igual o mejor nivel).
    - Permite fichar jugadores de nivel inferior solo si:
      * Es menor de 21 años (proyección).
      * O es para completar una necesidad (ej: portero).
    """

    db = st.session_state.db

    if origen not in db["equipos_data"] or destino not in db["equipos_data"]:
        return False, "Equipo no válido"

    if jugador["nombre"] not in [j["nombre"] for j in db["equipos_data"][origen].get("jugadores", [])]:
        return False, "Jugador no está en el equipo origen"

    # Presupuesto
    presupuesto_destino = db["equipos_data"][destino].get("presupuesto", 0)

    if tipo == "traspaso":
        coste = cantidad
    else:
        coste = cantidad  # cesión

    if coste > presupuesto_destino:
        return False, "Sin presupuesto"

    # Control de nivel: máximo 2 niveles de diferencia
    liga_origen = db["equipos_data"][origen].get("liga", "")
    liga_destino = db["equipos_data"][destino].get("liga", "")

    nivel_origen = nivel_liga(liga_origen)
    nivel_destino = nivel_liga(liga_destino)

    diferencia = abs(nivel_origen - nivel_destino)

    # Máximo 2 niveles de diferencia
    if diferencia > 2:
        return False, "Demasiada diferencia de nivel"

    # Calcular media del equipo destino para ver si el jugador lo mejora
    plantilla_destino = db["equipos_data"][destino].get("jugadores", [])
    media_destino = sum(j.get("media", 0) for j in plantilla_destino) / len(plantilla_destino) if plantilla_destino else 0

    media_jugador = jugador.get("media", 0)
    mejora = media_jugador - media_destino

    edad = jugador.get("edad", 24)

    # Si el jugador es de nivel inferior (empeora la media), solo permitir si:
    # 1. Es menor de 21 años (proyección) → permitir siempre (dentro de 2 niveles)
    # 2. O si la diferencia de nivel es 1 y es para completar una necesidad
    if mejora < 0:
        # Empeora la media del equipo
        if edad < 21:
            # Joven con proyección: permitir aunque empeore la media (dentro de 2 niveles)
            pass
        else:
            # No es joven: aplicar restricciones
            if diferencia > 1:
                return False, "El jugador empeora demasiado el equipo"

            # Si empeora y diferencia es 1, solo permitir si el equipo tiene necesidad
            num_porteros = sum(1 for j in plantilla_destino if j.get("pos") == "POR")
            num_jugadores = len(plantilla_destino)

            if jugador.get("pos") == "POR":
                # Portero: permitir si tiene menos de 2
                if num_porteros >= 2:
                    return False, "Ya tiene suficientes porteros"
            else:
                # Jugador de campo: permitir si tiene menos de 6
                if num_jugadores >= 6:
                    return False, "El equipo ya tiene suficientes jugadores"

    # Si mejora o iguala la media, permitir siempre (dentro del límite de 2 niveles)
    return True, "OK"

def crear_oferta_club(
    origen,
    destino,
    jugador_nombre,
    cantidad,
    temporada=None,
    tipo="traspaso",
    duracion=1,
    opcion_compra=False,
    precio_opcion_compra=0
):
    db = st.session_state.db

    if temporada is None:
        temporada = db["config"]["temporada"]

    db.setdefault("ofertas_pendientes", [])

    if son_clubes_vinculados(origen, destino):
        return False, "No se pueden enviar ofertas entre equipos vinculados"

    jugadores_origen = db["equipos_data"][origen]["jugadores"]
    jugador = next(
        (j for j in jugadores_origen if j["nombre"] == jugador_nombre),
        None
    )

    if jugador is None:
        return False, "Jugador no encontrado en el equipo vendedor"

    if jugador.get("cedido", False):
        return False, "No se puede ofertar por un jugador que está cedido"

    # NUEVO: Validar que la oferta sea aceptable para tus clubes
    es_valida, motivo = oferta_aceptable_para_usuario(
        origen=origen,
        destino=destino,
        jugador=jugador_nombre,
        tipo=tipo,
        cantidad=cantidad,
        duracion=duracion,
        opcion_compra=opcion_compra,
        precio_opcion_compra=precio_opcion_compra,
    )

    if not es_valida:
        return False, motivo

    oferta = {
        "id": (
            f"{tipo}:{origen}->{destino}:"
            f"{jugador_nombre}:{temporada}:"
            f"{len(db['ofertas_pendientes'])}"
        ),
        "tipo": tipo,
        "origen": origen,
        "destino": destino,
        "jugador": jugador_nombre,
        "cantidad": float(cantidad),
        "duracion": int(duracion),
        "opcion_compra": bool(opcion_compra),
        "precio_opcion_compra": float(precio_opcion_compra or 0),
        "temporada": temporada,
        "estado": "pendiente",
    }

    db["ofertas_pendientes"].append(oferta)
    return True, "Oferta creada correctamente"

def generar_ofertas_para_cerezas():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_cerezas = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "CEREZAS" and o["estado"] == "pendiente"
    ]
    if pendientes_cerezas:
        return

    # Probabilidad base de generar alguna oferta
    prob_base = 0.35

    # Si hay al menos un jugador transferible o cedible, aumentamos la probabilidad
    jugadores_cerezas_candidatos = [
        j for j in db["equipos_data"]["CEREZAS"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_cerezas_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_cerezas_candidatos)

    if hay_transferibles or hay_cedibles:
        prob_base = 0.65

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "CEREZAS")
        and not es_equipo_sub19(e)
        and e not in ["RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes:
        return

    # Priorizar jugadores transferibles/cedibles
    candidatos = []
    for j in jugadores_cerezas_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    if not candidatos:
        return

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("CEREZAS") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 24) <= 25
        and jugador_obj.get("media", 0) <= 84
        and random.random() < 0.35
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.08, 0.18), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = random.choice([1, 1, 2])

        crear_oferta_club(
            "CEREZAS",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "CEREZAS", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "CEREZAS",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )



def generar_ofertas_para_cerezas_b():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_cerezas_b = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "CEREZAS B" and o["estado"] == "pendiente"
    ]
    if pendientes_cerezas_b:
        return

    jugadores_cerezas_b_candidatos = [
        j for j in db["equipos_data"]["CEREZAS B"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_cerezas_b_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_cerezas_b_candidatos)

    prob_base = 0.15
    if hay_transferibles or hay_cedibles:
        prob_base = 0.45

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "CEREZAS B")
        and not es_equipo_sub19(e)
        and e not in ["RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes or not jugadores_cerezas_b_candidatos:
        return

    candidatos = []
    for j in jugadores_cerezas_b_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("CEREZAS B") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 24) <= 24
        and jugador_obj.get("media", 0) <= 80
        and random.random() < 0.45
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.10, 0.22), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = random.choice([1, 1, 2])

        crear_oferta_club(
            "CEREZAS B",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "CEREZAS B", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "CEREZAS B",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )



def generar_ofertas_para_cerezas_sub19():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_cerezas_sub19 = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "CEREZAS Sub-19" and o["estado"] == "pendiente"
    ]
    if pendientes_cerezas_sub19:
        return

    jugadores_cerezas_sub19_candidatos = [
        j for j in db["equipos_data"]["CEREZAS Sub-19"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_cerezas_sub19_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_cerezas_sub19_candidatos)

    prob_base = 0.05
    if hay_transferibles or hay_cedibles:
        prob_base = 0.20

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "CEREZAS Sub-19")
        and e not in ["RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes or not jugadores_cerezas_sub19_candidatos:
        return

    candidatos = []
    for j in jugadores_cerezas_sub19_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("CEREZAS Sub-19") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 99) <= 19
        and jugador_obj.get("media", 0) <= 78
        and random.random() < 0.60
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.12, 0.25), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = 1

        crear_oferta_club(
            "CEREZAS Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "CEREZAS Sub-19", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "CEREZAS Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )



def generar_ofertas_para_rb_zerkas():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_rb_zerkas = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "RB Zerkas" and o["estado"] == "pendiente"
    ]
    if pendientes_rb_zerkas:
        return

    jugadores_rb_zerkas_candidatos = [
        j for j in db["equipos_data"]["RB Zerkas"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_rb_zerkas_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_rb_zerkas_candidatos)

    prob_base = 0.35
    if hay_transferibles or hay_cedibles:
        prob_base = 0.65

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "RB Zerkas")
        and not es_equipo_sub19(e)
        and e not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes or not jugadores_rb_zerkas_candidatos:
        return

    candidatos = []
    for j in jugadores_rb_zerkas_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("RB Zerkas") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 24) <= 25
        and jugador_obj.get("media", 0) <= 84
        and random.random() < 0.35
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.08, 0.18), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = random.choice([1, 1, 2])

        crear_oferta_club(
            "RB Zerkas",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "RB Zerkas", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "RB Zerkas",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )



def generar_ofertas_para_rb_zerkas_b():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_rb_zerkas_b = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "RB Zerkas B" and o["estado"] == "pendiente"
    ]
    if pendientes_rb_zerkas_b:
        return

    jugadores_rb_zerkas_b_candidatos = [
        j for j in db["equipos_data"]["RB Zerkas B"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_rb_zerkas_b_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_rb_zerkas_b_candidatos)

    prob_base = 0.15
    if hay_transferibles or hay_cedibles:
        prob_base = 0.45

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "RB Zerkas B")
        and not es_equipo_sub19(e)
        and e not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes or not jugadores_rb_zerkas_b_candidatos:
        return

    candidatos = []
    for j in jugadores_rb_zerkas_b_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("RB Zerkas B") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 24) <= 24
        and jugador_obj.get("media", 0) <= 80
        and random.random() < 0.45
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.10, 0.22), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = random.choice([1, 1, 2])

        crear_oferta_club(
            "RB Zerkas B",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "RB Zerkas B", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "RB Zerkas B",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )



def generar_ofertas_para_rb_zerkas_sub19():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_rb_zerkas_sub19 = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "RB Zerkas Sub-19" and o["estado"] == "pendiente"
    ]
    if pendientes_rb_zerkas_sub19:
        return

    jugadores_rb_zerkas_sub19_candidatos = [
        j for j in db["equipos_data"]["RB Zerkas Sub-19"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_rb_zerkas_sub19_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_rb_zerkas_sub19_candidatos)

    prob_base = 0.05
    if hay_transferibles or hay_cedibles:
        prob_base = 0.20

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "RB Zerkas Sub-19")
        and e not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "EKIPO", "EKIPO Sub-19"]
    ]

    if not clubes or not jugadores_rb_zerkas_sub19_candidatos:
        return

    candidatos = []
    for j in jugadores_rb_zerkas_sub19_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("RB Zerkas Sub-19") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 99) <= 19
        and jugador_obj.get("media", 0) <= 78
        and random.random() < 0.60
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.12, 0.25), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = 1

        crear_oferta_club(
            "RB Zerkas Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "RB Zerkas Sub-19", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "RB Zerkas Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )


def generar_ofertas_para_ekipo():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_ekipo = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "EKIPO" and o["estado"] == "pendiente"
    ]
    if pendientes_ekipo:
        return

    # Probabilidad base de generar alguna oferta
    prob_base = 0.35

    # Si hay al menos un jugador transferible o cedible, aumentamos la probabilidad
    jugadores_ekipo_candidatos = [
        j for j in db["equipos_data"]["EKIPO"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_ekipo_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_ekipo_candidatos)

    if hay_transferibles or hay_cedibles:
        prob_base = 0.65

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "EKIPO")
        and not es_equipo_sub19(e)
        and e not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19"]
    ]

    if not clubes:
        return

    # Priorizar jugadores transferibles/cedibles
    candidatos = []
    for j in jugadores_ekipo_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    if not candidatos:
        return

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("EKIPO") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 24) <= 25
        and jugador_obj.get("media", 0) <= 84
        and random.random() < 0.35
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.08, 0.18), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = random.choice([1, 1, 2])

        crear_oferta_club(
            "EKIPO",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "EKIPO", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "EKIPO",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )




def generar_ofertas_para_ekipo_sub19():
    db = st.session_state.db
    db.setdefault("ofertas_pendientes", [])

    pendientes_ekipo_sub19 = [
        o for o in db["ofertas_pendientes"]
        if o["origen"] == "EKIPO Sub-19" and o["estado"] == "pendiente"
    ]
    if pendientes_ekipo_sub19:
        return

    jugadores_ekipo_sub19_candidatos = [
        j for j in db["equipos_data"]["EKIPO Sub-19"]["jugadores"]
        if not j.get("cedido", False)
    ]
    hay_transferibles = any(j.get("transferible", False) for j in jugadores_ekipo_sub19_candidatos)
    hay_cedibles = any(j.get("cedible", False) for j in jugadores_ekipo_sub19_candidatos)

    prob_base = 0.05
    if hay_transferibles or hay_cedibles:
        prob_base = 0.20

    if random.random() > prob_base:
        return

    clubes = [
        e for e in db["equipos_data"].keys()
        if not son_clubes_vinculados(e, "EKIPO Sub-19")
        and e not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19"]
    ]

    if not clubes or not jugadores_ekipo_sub19_candidatos:
        return

    candidatos = []
    for j in jugadores_ekipo_sub19_candidatos:
        peso = 1.0
        if j.get("transferible", False):
            peso *= 4.0
        if j.get("cedible", False):
            peso *= 2.0
        candidatos.append((j, peso))

    jugador_obj = random.choices(
        [c[0] for c in candidatos],
        weights=[c[1] for c in candidatos],
        k=1
    )[0]

    if jugador_obj["pos"] == "POR" and contar_porteros("EKIPO Sub-19") <= 1:
        return

    club_ofertante = random.choice(clubes)

    usar_cesion_opcion = (
        jugador_obj.get("edad", 99) <= 19
        and jugador_obj.get("media", 0) <= 78
        and random.random() < 0.60
    )

    if usar_cesion_opcion:
        pago_cesion = max(0.1, round(float(jugador_obj["valor"]) * random.uniform(0.12, 0.25), 1))
        precio_opcion = round(
            float(jugador_obj.get("valor", 0)) * random.uniform(0.90, 1.10),
            1
        )
        duracion = 1

        crear_oferta_club(
            "EKIPO Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            pago_cesion,
            tipo="cesion",
            duracion=duracion,
            opcion_compra=True,
            precio_opcion_compra=precio_opcion
        )
    else:
        precio = round(
            calcular_precio_traspaso(jugador_obj, "EKIPO Sub-19", club_ofertante) * random.uniform(0.85, 1.15),
            1
        )
        precio = max(0.1, precio)

        crear_oferta_club(
            "EKIPO Sub-19",
            club_ofertante,
            jugador_obj["nombre"],
            precio,
            tipo="traspaso"
        )

def mercado_automatico_global(db):
    """
    Genera ofertas automáticas para TODOS los clubes,
    no solo para CEREZAS y RB Zerkas.
    """

    clubes_usuario = {
        "CEREZAS",
        "CEREZAS B",
        "CEREZAS Sub-19",
        "RB Zerkas",
        "RB Zerkas B",
        "RB Zerkas Sub-19",
        "EKIPO",
        "EKIPO Sub-19"
    }

    db.setdefault("ofertas_pendientes", [])

    equipos_data = db.get("equipos_data", {})

    # Equipos que participan en el mercado global:
    # - Primeros equipos de España, Com, Tengu y Folimón
    # - Excluyendo filiales (B, C), Sub-19 y clubes del usuario
    equipos_mercado = []

    for equipo, datos_equipo in equipos_data.items():
        liga = datos_equipo.get("liga", "")

        # Excluir filiales y Sub-19
        if equipo.endswith(" B") or equipo.endswith(" C"):
            continue
        if "Sub-19" in equipo or "Sub 19" in equipo:
            continue

        # Excluir CEREZAS, RB Zerkas y todos sus derivados
        if equipo in clubes_usuario:
            continue

        # Incluir primeros equipos senior de España, Com, Tengu y Folimón
        if liga in {
            "1ª División",
            "2ª División",
            "3ª División Grupo A",
            "3ª División Grupo B",
            "4ª División",
            "Com 1ª División",
            "Com 2ª División",
            "Tengu 1ª División",
            "Tengu 2ª División",
            "Folimón 1ª División",
            "Folimón 2ª División",
        }:
            equipos_mercado.append(equipo)

    # Renombramos para que el resto del código no cambie
    equipos_principales = equipos_mercado

    print(f"=== MERCADO GLOBAL ===")
    print(f"Total equipos en mercado: {len(equipos_mercado)}")

    # Ver qué países hay
    paises = {}
    for eq in equipos_mercado:
        liga = equipos_data[eq].get("liga", "")
        pais = liga.split()[0] if liga else "Desconocido"
        paises[pais] = paises.get(pais, 0) + 1
    print(f"Distribución por país: {paises}")

    if len(equipos_principales) < 2:
        print("No hay suficientes equipos, saliendo.")
        return

    # Máximo de ofertas por jornada para no saturar
    max_ofertas = max(3, len(equipos_principales) // 4)
    num_ofertas_generadas = 0

    for intento in range(max_ofertas * 3):  # Intentos
        if num_ofertas_generadas >= max_ofertas:
            break

        # Elegir club vendedor aleatorio
        club_vendedor = random.choice(equipos_principales)

        # Ignorar clubes del usuario (ya tienen sus propias funciones)
        if club_vendedor in clubes_usuario:
            continue

        jugadores_vendedor = equipos_data[club_vendedor].get("jugadores", [])

        if not jugadores_vendedor:
            continue

        # Elegir jugador aleatorio no cedido
        jugador = random.choice(jugadores_vendedor)

        if jugador.get("cedido", False):
            continue

        # Elegir club comprador aleatorio (distinto al vendedor)
        posibles_compradores = [
            eq for eq in equipos_principales
            if eq != club_vendedor
            and not son_clubes_vinculados(eq, club_vendedor)
        ]

        if not posibles_compradores:
            continue

        # Ponderar por nivel de liga
        liga_vendedor = equipos_data[club_vendedor].get("liga", "")
        nivel_vendedor = nivel_liga(liga_vendedor)

        candidatos_compradores = []

        for club_comprador in posibles_compradores:
            liga_comprador = equipos_data[club_comprador].get("liga", "")
            nivel_comprador = nivel_liga(liga_comprador)

            diferencia = abs(nivel_vendedor - nivel_comprador)

            if diferencia == 0:
                prob = 0.35
            elif diferencia == 1:
                prob = 0.30
            elif diferencia == 2:
                prob = 0.15
            else:
                prob = 0.05

            for _ in range(int(prob * 100)):
                candidatos_compradores.append(club_comprador)

        if not candidatos_compradores:
            continue

        club_comprador = random.choice(candidatos_compradores)

        # Validar que la oferta es aceptable
        tipo_oferta = random.choice(["traspaso", "cesion", "cesion"])
        duracion = random.randint(1, 2) if tipo_oferta == "cesion" else 1
        opcion_compra = tipo_oferta == "cesion" and random.random() < 0.4

        if tipo_oferta == "traspaso":
            cantidad = calcular_precio_traspaso(
                jugador,
                club_vendedor,
                club_comprador
            )
        else:
            cantidad = max(0.1, round(float(jugador.get("valor", 1)) * 0.12, 1))

        # Calcular precio de opción (solo si es cesión con opción)
        precio_opcion = 0
        if opcion_compra:
            precio_opcion = round(
                float(jugador.get("valor", 0)) * random.uniform(0.90, 1.10),
                1
            )

        # --- NUEVO: usar filtro distinto según si el destino es usuario o IA ---
        if club_comprador in clubes_usuario:
            # Oferta hacia el usuario: filtro estricto
            es_valida, motivo = oferta_aceptable_para_usuario(
                origen=club_vendedor,
                destino=club_comprador,
                jugador=jugador["nombre"],
                tipo=tipo_oferta,
                cantidad=cantidad,
                duracion=duracion,
                opcion_compra=opcion_compra,
                precio_opcion_compra=precio_opcion,
            )
        else:
            # Oferta entre IA: filtro más flexible
            es_valida, motivo = oferta_aceptable_para_ia(
                origen=club_vendedor,
                destino=club_comprador,
                jugador=jugador,  # pasamos el dict completo
                tipo=tipo_oferta,
                cantidad=cantidad,
                duracion=duracion,
                opcion_compra=opcion_compra,
                precio_opcion_compra=precio_opcion,
            )

        print(f"  Oferta válida: {es_valida} ({motivo})")

        if not es_valida:
            continue

        # Crear oferta
        ok, msg = crear_oferta_club(
            origen=club_vendedor,
            destino=club_comprador,
            jugador_nombre=jugador["nombre"],
            cantidad=cantidad,
            tipo=tipo_oferta,
            duracion=duracion,
            opcion_compra=opcion_compra,
            precio_opcion_compra=precio_opcion,
        )

        print(f"  Oferta creada: {ok} ({msg})")

        if ok:
            num_ofertas_generadas += 1

    print(f"\nTotal ofertas generadas: {num_ofertas_generadas}")
    print(f"========================\n")

def ejecutar_ofertas_ia(db):
    """
    Ejecuta automáticamente las ofertas pendientes entre clubes IA.
    Las ofertas que afectan a CEREZAS o RB Zerkas se mantienen pendientes.
    """

    clubes_usuario = {
        "CEREZAS",
        "CEREZAS B",
        "CEREZAS Sub-19",
        "RB Zerkas",
        "RB Zerkas B",
        "RB Zerkas Sub-19",
        "EKIPO",
        "EKIPO Sub-19",
    }

    ofertas_pendientes = db.setdefault("ofertas_pendientes", [])
    ofertas_restantes = []
    ejecutadas = 0

    for oferta in ofertas_pendientes:
        origen = oferta.get("origen")
        destino = oferta.get("destino")

        # Mantener las ofertas dirigidas a los clubes del usuario
        if origen in clubes_usuario or destino in clubes_usuario:
            ofertas_restantes.append(oferta)
            continue

        # El formato correcto usa "jugador", no "jugador_nombre"
        jugador_nombre = oferta.get("jugador")

        if not jugador_nombre:
            db.setdefault("mercado_log", []).append(
                f"Oferta IA omitida: falta el jugador ({oferta})"
            )
            continue

        tipo = oferta.get("tipo", "traspaso")
        cantidad = float(
            oferta.get("cantidad", oferta.get("precio", 0)) or 0
        )
        duracion = oferta.get("duracion", 1)
        opcion_compra = oferta.get("opcion_compra", False)
        precio_opcion = oferta.get("precio_opcion_compra", 0)

        if tipo == "traspaso":
            ok, msg = hacer_traspaso(
                jugador_nombre,
                origen,
                destino,
                monto=cantidad,
            )
        else:
            ok, msg = hacer_cesion(
                jugador_nombre,
                origen,
                destino,
                monto=cantidad,
                duracion=duracion,
                opcion_compra=opcion_compra,
                precio_opcion_compra=(
                    precio_opcion if opcion_compra else None
                ),
            )

        if ok:
            ejecutadas += 1
            db.setdefault("mercado_log", []).append(
                f"✅ IA: {jugador_nombre} pasa de "
                f"{origen} a {destino} ({tipo})"
            )
        else:
            # Si no se puede ejecutar, no perder la oferta
            ofertas_restantes.append(oferta)
            db.setdefault("mercado_log", []).append(
                f"❌ Oferta IA no ejecutada: {jugador_nombre} "
                f"{origen} → {destino}: {msg}"
            )

    db["ofertas_pendientes"] = ofertas_restantes

    print(
        f"Ofertas IA ejecutadas: {ejecutadas}. "
        f"Pendientes restantes: {len(ofertas_restantes)}"
    )

def aceptar_oferta(oferta_id, forzar_usuario=False):
    db = st.session_state.db

    oferta = next(
        (
            o for o in db["ofertas_pendientes"]
            if o["id"] == oferta_id and o["estado"] == "pendiente"
        ),
        None
    )

    if not oferta:
        return False, "Oferta no encontrada."

    origen = oferta["origen"]
    destino = oferta["destino"]
    jugador_nombre = oferta["jugador"]
    cantidad = float(oferta.get("cantidad", 0))
    tipo_oferta = oferta.get("tipo", "traspaso")

    # Si es cesión
    if tipo_oferta == "cesion":
        ok, msg = hacer_cesion(
            jugador_nombre,
            origen,
            destino,
            monto=cantidad,
            duracion=int(oferta.get("duracion", 1)),
            opcion_compra=bool(oferta.get("opcion_compra", False)),
            precio_opcion_compra=float(oferta.get("precio_opcion_compra", 0)),
            forzar_usuario=forzar_usuario
        )

        if ok:
            oferta["estado"] = "aceptada"
            return True, f"Oferta de cesión aceptada: {jugador_nombre} pasa a {destino}."

        oferta["estado"] = "rechazada"
        return False, msg

    # Traspaso permanente
    jugadores_origen = db["equipos_data"][origen]["jugadores"]
    jugadores_destino = db["equipos_data"][destino]["jugadores"]

    jugador = next(
        (j for j in jugadores_origen if j["nombre"] == jugador_nombre),
        None
    )

    if not jugador:
        oferta["estado"] = "cancelada"
        return False, "El jugador ya no está en el club de origen."

    # Mantener límites reales de plantilla del club comprador
    if es_equipo_principal(destino):
        club_principal = obtener_club_principal(destino)

        if contar_jugadores_primer_equipo(club_principal) >= 7:
            oferta["estado"] = "rechazada"
            return False, (
                f"{club_principal} ya tiene 7 jugadores permanentes "
                f"en el primer equipo."
            )

        if contar_total_efectivos_primer_equipo(club_principal) >= 10:
            oferta["estado"] = "rechazada"
            return False, f"{club_principal} ya tiene 10 jugadores efectivos."

    if len(jugadores_destino) >= 8:
        oferta["estado"] = "rechazada"
        return False, "El equipo destino ya tiene demasiados jugadores."

    # Mantener la protección del último portero
    if jugador["pos"] == "POR" and contar_porteros(origen) <= 1:
        oferta["estado"] = "rechazada"
        return False, (
            "No puedes aceptar esta oferta: el club vendedor debe "
            "quedarse con al menos 1 portero."
        )

    # Ejecutar el traspaso. forzar_usuario=True evita el bloqueo por jugador importante.
    ok, msg = hacer_traspaso(
        jugador_nombre,
        origen,
        destino,
        monto=cantidad,
        forzar_usuario=forzar_usuario
    )

    if not ok:
        oferta["estado"] = "rechazada"
        return False, msg

    oferta["estado"] = "aceptada"

    db["mercado_log"].append(
        f"✅ {origen} acepta oferta de {destino} por "
        f"{jugador_nombre} ({formatear_valor(cantidad)})"
    )

    return (
        True,
        f"Oferta aceptada: {jugador_nombre} a {destino} "
        f"por {formatear_valor(cantidad)}"
    )

def rechazar_oferta(oferta_id):
    db = st.session_state.db

    oferta = next(
        (o for o in db["ofertas_pendientes"] if o["id"] == oferta_id and o["estado"] == "pendiente"),
        None
    )

    if not oferta:
        return False, "Oferta no encontrada."

    oferta["estado"] = "rechazada"
    db["mercado_log"].append(
        f"❌ {oferta['origen']} rechaza oferta de {oferta['destino']} por {oferta['jugador']} ({formatear_valor(oferta['cantidad'])})"
    )

    return True, "Oferta rechazada"

def responder_oferta_automatica(oferta_id):
    db = st.session_state.db

    oferta = next(
        (
            o for o in db["ofertas_pendientes"]
            if o["id"] == oferta_id
            and o["estado"] == "pendiente"
        ),
        None
    )

    if not oferta:
        return False, "Oferta no encontrada."

    origen = oferta["origen"]
    destino = oferta["destino"]
    jugador_nombre = oferta["jugador"]
    cantidad = float(oferta.get("cantidad", 0))
    tipo_oferta = oferta.get("tipo", "traspaso")

    clubes_usuario = {
        "CEREZAS",
        "CEREZAS B",
        "CEREZAS Sub-19",
        "RB Zerkas",
        "RB Zerkas B",
        "RB Zerkas Sub-19",
        "EKIPO",
        "EKIPO Sub-19",
    }

    # Buscar el jugador del club vendedor
    if origen not in db["equipos_data"]:
        oferta["estado"] = "cancelada"
        return False, f"El equipo de origen {origen} no existe."

    jugadores_origen = db["equipos_data"][origen]["jugadores"]

    jugador = next(
        (
            j for j in jugadores_origen
            if j["nombre"] == jugador_nombre
        ),
        None
    )

    if jugador is None:
        oferta["estado"] = "cancelada"
        return False, "El jugador ya no está disponible."

    # Si el destino no existe, cancelar la oferta
    if destino not in db["equipos_data"]:
        oferta["estado"] = "cancelada"
        return False, f"El equipo de destino {destino} no existe."

    # =========================================================
    # CLUBES DEL USUARIO
    # =========================================================
    if origen in clubes_usuario:
        presupuesto_destino = db["equipos_data"][destino].get(
            "presupuesto",
            0
        )

        if tipo_oferta == "cesion":
            pago_cesion = cantidad

            if presupuesto_destino < pago_cesion:
                oferta["estado"] = "rechazada"
                return (
                    True,
                    f"{destino} no tiene suficiente dinero para "
                    f"pagar la cesión de {jugador_nombre}."
                )
        else:
            if presupuesto_destino < cantidad:
                oferta["estado"] = "rechazada"
                return (
                    True,
                    f"{destino} no tiene suficiente dinero para "
                    f"pagar el traspaso de {jugador_nombre}."
                )

        # Si pasa las comprobaciones, no se responde automáticamente
        return (
            False,
            "Oferta pendiente de decisión del usuario."
        )

    # =========================================================
    # RESTO DE CLUBES: RESPUESTA AUTOMÁTICA
    # =========================================================

    if tipo_oferta == "cesion":
        if jugador.get("cedido", False):
            oferta["estado"] = "rechazada"
            return (
                True,
                f"{jugador_nombre} ya está cedido."
            )

        partidos_titular = jugador.get(
            "partidos_titular",
            0
        )

        minutos = jugador.get(
            "minutos_totales",
            0
        )

        media = jugador.get(
            "media",
            0
        )

        valor_base = float(
            jugador.get("valor", 1)
        )

        if (
            media >= 86
            or partidos_titular >= 8
            or minutos >= 320
        ):
            oferta["estado"] = "rechazada"
            db.setdefault("mercado_log", [])
            db["mercado_log"].append(
                f"{origen} rechaza la oferta de cesión de "
                f"{destino} por {jugador_nombre}: "
                f"jugador importante"
            )
            return (
                True,
                f"{origen} considera a {jugador_nombre} "
                f"demasiado importante para una cesión."
            )

        umbral_aceptacion_directa = max(
            0.1,
            round(valor_base * 0.12, 1)
        )

        umbral_aceptacion_dudosa = max(
            0.1,
            round(valor_base * 0.08, 1)
        )

        if cantidad >= umbral_aceptacion_directa:
            ok, msg = aceptar_oferta(oferta_id)
            return ok, msg

        if (
            cantidad >= umbral_aceptacion_dudosa
            and random.random() < 0.45
        ):
            ok, msg = aceptar_oferta(oferta_id)
            return ok, msg

        oferta["estado"] = "rechazada"
        db.setdefault("mercado_log", [])
        db["mercado_log"].append(
            f"{origen} rechaza la oferta de cesión de "
            f"{destino} por {jugador_nombre} "
            f"({formatear_valor(cantidad)})"
        )
        return (
            True,
            f"{origen} ha rechazado la oferta de cesión "
            f"por {jugador_nombre}."
        )

    valor_base = float(
        jugador.get("valor", 1)
    )

    precio_minimo = calcular_precio_traspaso(
        jugador,
        origen,
        destino
    )

    if not jugador_es_vendible(origen, jugador):
        # Aceptar si la oferta es el doble del valor de mercado
        if cantidad >= valor_base * 2.0:
            ok, msg = aceptar_oferta(oferta_id, forzar_usuario=True)
            return ok, msg
        
        # Aceptar si la oferta es un 25% más del precio mínimo
        if cantidad >= precio_minimo * 1.25:
            ok, msg = aceptar_oferta(oferta_id, forzar_usuario=True)
            return ok, msg

        if (
            cantidad >= valor_base * 1.15
            and random.random() < 0.35
        ):
            ok, msg = aceptar_oferta(oferta_id, forzar_usuario=True)
            return ok, msg

        oferta["estado"] = "rechazada"
        db.setdefault("mercado_log", [])
        db["mercado_log"].append(
            f"{origen} rechaza la oferta de {destino} "
            f"por {jugador_nombre}: jugador poco vendible"
        )
        return (
            True,
            f"{origen} no quiere vender ahora mismo "
            f"a {jugador_nombre}."
        )

    if cantidad >= precio_minimo:
        ok, msg = aceptar_oferta(oferta_id)
        return ok, msg

    if (
        cantidad >= precio_minimo * 0.9
        and random.random() < 0.45
    ):
        ok, msg = aceptar_oferta(oferta_id)
        return ok, msg

    if (
        cantidad >= valor_base * 0.8
        and random.random() < 0.20
    ):
        ok, msg = aceptar_oferta(oferta_id)
        return ok, msg

    oferta["estado"] = "rechazada"
    db.setdefault("mercado_log", [])
    db["mercado_log"].append(
        f"{origen} rechaza la oferta de {destino} "
        f"por {jugador_nombre} "
        f"({formatear_valor(cantidad)})"
    )
    return (
        True,
        f"{origen} ha rechazado la oferta por "
        f"{jugador_nombre}."
    )

def contar_porteros(equipo):
    db = st.session_state.db
    return sum(1 for j in db["equipos_data"][equipo]["jugadores"] if j["pos"] == "POR")

def iniciar_alerta_porteria(equipo, jornadas_restantes=3):
    db = st.session_state.db
    jornada_actual = int(db["equipos_data"][equipo].get("control_jornada_porteros", 0))
    db["equipos_data"][equipo]["alerta_porteria"] = {
        "activa": True,
        "jornada_inicio": jornada_actual,
        "jornada_limite": jornada_actual + jornadas_restantes,
    }

def limpiar_alerta_porteria_si_corresponde(equipo):
    db = st.session_state.db
    if contar_porteros(equipo) >= 2:
        db["equipos_data"][equipo]["alerta_porteria"] = {
            "activa": False,
            "jornada_inicio": None,
            "jornada_limite": None,
        }

def equipo_necesita_regularizar_porteria(equipo):
    db = st.session_state.db
    alerta = db["equipos_data"][equipo].get("alerta_porteria", {})
    if not alerta or not alerta.get("activa", False):
        return False

    if contar_porteros(equipo) >= 2:
        limpiar_alerta_porteria_si_corresponde(equipo)
        return False

    jornada_actual = int(db["equipos_data"][equipo].get("control_jornada_porteros", 0))
    return jornada_actual >= int(alerta.get("jornada_limite", 0))

def formatear_valor(valor):
    if valor >= 1:
        return f"{valor} M€"
    return f"{int(valor * 1000)} K€"

def presupuesto_inicial_por_liga(liga):
    # Com, Tengu y Folimón
    if liga in ["Com 1ª División", "Tengu 1ª División", "Folimón 1ª División"]:
        return 100.0
    if liga in ["Com 2ª División", "Tengu 2ª División", "Folimón 2ª División"]:
        return 35.0
    
    # Liga principal
    if liga == "1ª División":
        return 150.0
    if liga == "2ª División":
        return 50.0
    if liga in ["3ª División", "3ª División Grupo A", "3ª División Grupo B"]:
        return 25.0
    if liga == "4ª División":
        return 10.0
    
    # Sub-19 y resto
    return 0


def inicializar_presupuestos():
    db = st.session_state.db
    for equipo, datos in db["equipos_data"].items():
        liga = datos.get("liga", "")

        if es_equipo_sub19(equipo):
            datos.pop("presupuesto", None)
            continue

        if "presupuesto" not in datos:
            datos["presupuesto"] = presupuesto_inicial_por_liga(liga)

def limitar_valor_por_liga(jugador, equipo):
    db = st.session_state.db

    if es_equipo_sub19(equipo):
        jugador["valor"] = min(float(jugador.get("valor", 1)), 1.0)
    else:
        liga = db["equipos_data"].get(equipo, {}).get("liga", "")

        if liga == "2ª División":
            jugador["valor"] = min(float(jugador.get("valor", 1)), 15)
        elif liga in ["3ª División", "3ª División Grupo A", "3ª División Grupo B"]:
            jugador["valor"] = min(float(jugador.get("valor", 1)), 6)
        elif liga == "4ª División":
            jugador["valor"] = min(float(jugador.get("valor", 1)), 1)

    jugador["valor"] = max(0.1, round(float(jugador["valor"]), 1))

def bonus_por_minutos_y_liga(equipo, minutos):
    """
    Bonus de media por minutos jugados, escalado según la división.
    Partidos de 40 min → máximo ~1520 min en 1ª División (38 jornadas).
    """
    db = st.session_state.db
    liga = db["equipos_data"].get(equipo, {}).get("liga", "")

    # Factor por división (más alta → más bonus)
    factores = {
        "1ª División": 1.00,
        "2ª División": 0.85,
        "3ª División Grupo A": 0.70,
        "3ª División Grupo B": 0.70,
        "4ª División": 0.55,
        "Com 1ª División": 0.90,
        "Com 2ª División": 0.75,
        "Tengu 1ª División": 0.90,
        "Tengu 2ª División": 0.75,
        "Folimón 1ª División": 0.90,
        "Folimón 2ª División": 0.75,
        "Sub-19 1 División": 0.60,
        "Sub-19 2 División": 0.50,
        "Sub-19 3 División Grupo A": 0.45,
        "Sub-19 3 División Grupo B": 0.45,
    }

    factor_liga = factores.get(liga, 0.50)

    # Bonus base según minutos (ajustado a partidos de 40 min)
    if minutos <= 200:
        bonus_base = 0.0
    elif minutos <= 600:
        bonus_base = 0.25
    elif minutos <= 1000:
        bonus_base = 0.55
    elif minutos <= 1300:
        bonus_base = 0.85
    else:
        # Máximo alrededor de 1520 en 1ª
        bonus_base = 1.10

    return bonus_base * factor_liga

def calcular_salario_por_temporada(media, edad, es_sub19=False):
    """
    Devuelve el salario anual en millones de euros.

    Referencias para un senior en edad prime:
    99 de media = 15 M€
    70 de media = 1 M€
    60 de media = 0.5 M€
    50 de media = 0.2 M€
    """

    # Salario base en millones según media
    if media >= 99:
        salario = 15.0
    elif media >= 95:
        salario = 12.0
    elif media >= 90:
        salario = 8.0
    elif media >= 85:
        salario = 5.0
    elif media >= 80:
        salario = 3.0
    elif media >= 75:
        salario = 2.0
    elif media >= 70:
        salario = 1.0
    elif media >= 65:
        salario = 0.7
    elif media >= 60:
        salario = 0.5
    elif media >= 55:
        salario = 0.35
    elif media >= 50:
        salario = 0.2
    elif media >= 45:
        salario = 0.1
    elif media >= 40:
        salario = 0.05
    else:
        salario = 0.02

    # Ajuste por edad. El salario de referencia es para 24-28 años.
    if edad <= 19:
        factor_edad = 0.50
    elif edad <= 21:
        factor_edad = 0.70
    elif edad <= 23:
        factor_edad = 0.85
    elif edad <= 28:
        factor_edad = 1.00
    elif edad <= 30:
        factor_edad = 0.95
    elif edad <= 33:
        factor_edad = 0.85
    else:
        factor_edad = 0.75

    # Los equipos Sub-19 tienen salarios algo inferiores incluso
    # en jugadores de 18-19 años.
    if es_sub19:
        factor_edad *= 0.80

    return round(salario * factor_edad, 3)

def obtener_duracion_contrato(edad, es_sub19=False):
    """
    Devuelve la duración de un contrato en temporadas.
    """
    if es_sub19:
        return random.choice([1, 2, 2, 3])

    if edad >= 32:
        return random.choice([1, 1, 2])

    if edad >= 28:
        return random.choice([1, 2, 2, 3])

    return random.choice([2, 3, 3, 4])

def liberar_jugadores_sin_contrato(db):
    """
    Convierte en jugadores libres a quienes ya han llegado a la
    temporada de vencimiento de su contrato.

    Debe llamarse después de aumentar db["config"]["temporada"].
    """
    temporada_actual = db["config"]["temporada"]

    db.setdefault("jugadores_libres", [])
    db.setdefault("mercado_log", [])
    db.setdefault("historial_traspasos", [])

    for equipo, datos_equipo in db["equipos_data"].items():
        plantilla = datos_equipo.get("jugadores", [])

        jugadores_a_liberar = [
            jugador
            for jugador in plantilla
            if jugador.get("fin_contrato") is not None
            and jugador["fin_contrato"] < temporada_actual
        ]

        for jugador in jugadores_a_liberar:
            plantilla.remove(jugador)

            # Evita que siga apareciendo como jugador del antiguo club.
            jugador["equipo_actual"] = "Libre"
            jugador["propietario"] = None
            jugador["cedido"] = False
            jugador["cedido_hasta"] = 0

            # Primera fila en el historial de temporadas como agente libre
            jugador.setdefault("historial_temporadas", []).append({
                "temporada": temporada_actual,
                "equipo": "Sin equipo",
                "division": "",
                "tipo_estancia": "agente libre",
                "nota_total": 0,
                "partidos": 0,
                "partidos_titular": 0,
                "minutos": 0,
                "goles": 0,
                "asistencias": 0,
                "amarillas": 0,
                "rojas": 0,
                "goles_encajados": 0,
                "media_partidos": 0,
                "media_final": jugador.get("media", 0),
                "valor_final": jugador.get("valor", 0),
            })

            db["jugadores_libres"].append({
                "jugador": jugador,
                "equipo_origen": equipo,
                "temporada_libre": temporada_actual
            })

            db["historial_traspasos"].append({
                "temporada": temporada_actual,
                "jugador": jugador["nombre"],
                "origen": equipo,
                "destino": "Sin equipo",
                "tipo": "fin de contrato",
                "valor": 0
            })

            db["mercado_log"].append(
                f"🆓 {jugador['nombre']} queda libre tras finalizar "
                f"su contrato con {equipo}"
            )

def renovar_contrato_jugador(jugador, equipo, db):
    """
    Renueva a un jugador o le da contrato al fichar como libre.

    Se recalcula su salario usando su media actual; por eso, si ha
    mejorado su media desde el contrato anterior, cobrará más.
    """
    temporada_actual = db["config"]["temporada"]
    sub19 = es_equipo_sub19(equipo)
    edad = jugador.get("edad", 20)

    nuevo_salario = calcular_salario_por_temporada(
        jugador.get("media", 40),
        edad,
        sub19
    )

    duracion = obtener_duracion_contrato(edad, sub19)

    jugador["salario"] = nuevo_salario

    # Guarda la temporada absoluta de vencimiento.
    jugador["fin_contrato"] = temporada_actual + duracion - 1

    return nuevo_salario, jugador["fin_contrato"]

def retirar_jugador_manual(jugador_nombre, equipo):
    db = st.session_state.db
    plantilla = db["equipos_data"][equipo]["jugadores"]
    jugador = next((j for j in plantilla if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador["pos"] == "POR" and contar_porteros(equipo) <= 1:
        return False, "No puedes retirar a este portero: el equipo debe quedarse con al menos 1 portero"

    plantilla.remove(jugador)

    if contar_porteros(equipo) == 1:
        iniciar_alerta_porteria(equipo, 3)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo)
    
    db.setdefault("historial_retiradas", []).append({
        "temporada": db["config"]["temporada"],
        "jugador": jugador["nombre"],
        "equipo": equipo,
        "edad": jugador.get("edad", 0),
        "manual": True
    })
    db["mercado_log"].append(f"🛑 Retirada manual: {jugador['nombre']} ({equipo})")
    return True, "Jugador retirado correctamente"

def calcular_precio_traspaso(jugador, equipo_origen, equipo_destino):
    plantilla_origen = st.session_state.db["equipos_data"][equipo_origen]["jugadores"]
    misma_pos = [x for x in plantilla_origen if x["pos"] == jugador["pos"] and x["nombre"] != jugador["nombre"]]
    importancia = 1.0
    if jugador["pos"] == "POR" and len(misma_pos) == 0:
        importancia = 2.2
    elif jugador["pos"] == "POR" and len(misma_pos) == 1:
        importancia = 1.7
    elif jugador["media"] >= 85:
        importancia = 1.6
    elif jugador["media"] >= 80:
        importancia = 1.35
    elif jugador["partidos_titular"] > max(3, jugador["partidos"] * 0.6):
        importancia = 1.25

    edad = jugador.get("edad", 24)
    factor_edad = 1.0
    if edad <= 21:
        factor_edad = 1.25
    elif edad >= 31:
        factor_edad = 0.85

    precio = jugador["valor"] * importancia * factor_edad
    return max(1, round(precio, 1))

def jugador_es_vendible(equipo, jugador):
    db = st.session_state.db
    plantilla = db["equipos_data"][equipo]["jugadores"]


    ordenados = sorted(
        plantilla,
        key=lambda j: (
            j.get("media", 0),
            j.get("partidos_titular", 0),
            j.get("minutos_totales", 0)
        ),
        reverse=True
    )


    # Top 3 o Top 4 del equipo por media (los más importantes)
    num_top = min(4, len(plantilla))  # Máximo 4, mínimo 3 si hay pocos
    if len(plantilla) <= 6:
        num_top = 3  # Si la plantilla es pequeña, solo top 3
    else:
        num_top = 4  # Si es grande, top 4


    top_nombres = [j["nombre"] for j in ordenados[:num_top]]


    nombre = jugador["nombre"]
    media = jugador.get("media", 0)
    partidos_titular = jugador.get("partidos_titular", 0)
    minutos = jugador.get("minutos_totales", 0)
    edad = jugador.get("edad", 24)


    if jugador.get("cedido", False):
        return False


    # Los top 3/4 NO se pueden ceder SIN opción de compra
    # (pero SÍ se pueden vender o ceder con opción si llega buena oferta)
    if nombre in top_nombres:
        return False


    # Jugadores con media muy alta (≥86) que cuenten, no se venden fácilmente
    if media >= 86 and (partidos_titular >= 5 or minutos >= 180):
        return False


    # Jóvenes con proyección (≤21) y media decente (≥78) que cuenten, no se venden fácilmente
    if edad <= 21 and media >= 78 and (partidos_titular >= 4 or minutos >= 140):
        return False


    return True

def nivel_liga(nombre_liga):
    """
    Devuelve un nivel numérico para cada liga.
    1 = máximo nivel, 7 = mínimo.
    """

    # Nivel 1: 1ª División principal
    if nombre_liga == "1ª División":
        return 1

    # Nivel 2: 1ª División Com, Tengu y Folimón
    if nombre_liga in {
        "Com 1ª División",
        "Tengu 1ª División",
        "Folimón 1ª División",
    }:
        return 2

    # Nivel 3: 2ª División principal
    if nombre_liga == "2ª División":
        return 3

    # Nivel 4: 3ª División principal, 2ª División Com/Tengu/Folimón, Sub-19 1ª principal
    if nombre_liga in {
        "3ª División Grupo A",
        "3ª División Grupo B",
        "Com 2ª División",
        "Tengu 2ª División",
        "Folimón 2ª División",
        "Sub-19 1 División",
    }:
        return 4

    # Nivel 5: 4ª División principal, Sub-19 1ª Com/Tengu/Folimón
    if nombre_liga in {
        "4ª División",
        "Com Sub-19 1 División",
        "Tengu Sub-19 1 División",
        "Folimón Sub-19 1 División",
    }:
        return 5

    # Nivel 6: Sub-19 2ª División principal y Com/Tengu/Folimón
    if nombre_liga in {
        "Sub-19 2 División",
        "Com Sub-19 2 División",
        "Tengu Sub-19 2 División",
        "Folimón Sub-19 2 División",
    }:
        return 6

    # Nivel 7: Sub-19 3ª División (todas)
    if nombre_liga in {
        "Sub-19 3 División Grupo A",
        "Sub-19 3 División Grupo B",
    }:
        return 7

    # Cualquier otra liga no mapeada
    return 5

# ============================================================
# COPAS NACIONALES
# ============================================================

def equipo_principal_para_copa(equipo, sub19=False):
    """
    Senior: no permite filiales B/C ni equipos Sub-19.
    Sub-19: permite los equipos Sub-19, pero no filiales B/C.
    """
    if sub19:
        return (
            "Sub-19" in equipo
            and not equipo.endswith(" B")
            and not equipo.endswith(" C")
        )

    return (
        "Sub-19" not in equipo
        and "Sub 19" not in equipo
        and not equipo.endswith(" B")
        and not equipo.endswith(" C")
    )


def crear_cruce_copa(local, visitante, ronda):
    return {
        "local": local,
        "visitante": visitante,
        "ronda": ronda,
        "resultado": None,
        "ganador": None,
        "eventos": [],
        "notas": [],
        "alineacion_local": [],
        "alineacion_visitante": [],
    }


def obtener_ligas_copa_pais(pais, sub19=False):
    """
    Devuelve únicamente las ligas que corresponden a la Copa del país.
    - Senior: solo senior.
    - Sub-19: solo Sub-19.
    - Cada país solo ve sus propias ligas (sin mezclar con otros).
    """

    if pais == "Principal":
        if sub19:
            return [
                "Sub-19 1 División",
                "Sub-19 2 División",
                "Sub-19 3 División Grupo A",
                "Sub-19 3 División Grupo B",
            ]

        return [
            "1ª División",
            "2ª División",
            "3ª División Grupo A",
            "3ª División Grupo B",
            "4ª División",
        ]

    if sub19:
        if pais == "Com":
            return [
                "Com Sub-19 1 División",
                "Com Sub-19 2 División",
            ]
        elif pais == "Tengu":
            return [
                "Tengu Sub-19 1 División",
                "Tengu Sub-19 2 División",
            ]
        elif pais == "Folimón":
            return [
                "Folimón Sub-19 1 División",
                "Folimón Sub-19 2 División",
            ]

        return []

    # Senior
    if pais == "Com":
        return [
            "Com 1ª División",
            "Com 2ª División",
        ]
    elif pais == "Tengu":
        return [
            "Tengu 1ª División",
            "Tengu 2ª División",
        ]
    elif pais == "Folimón":
        return [
            "Folimón 1ª División",
            "Folimón 2ª División",
        ]

    return []

def crear_datos_copa(db, pais, sub19=False):
    """
    Recoge todos los equipos de las divisiones del país.
    Los equipos de divisiones inferiores se guardan primero para
    que entren en las rondas previas.
    """
    equipos_con_nivel = []

    for nombre_liga in obtener_ligas_copa_pais(pais, sub19=sub19):
        liga = db["ligas"].get(nombre_liga)

        if not liga:
            continue

        # Aquí 'liga' es el dict completo: {"equipos": [...], "calendario": [], ...}
        equipos_liga = liga.get("equipos", [])

        for posicion, equipo in enumerate(equipos_liga, start=1):
            if not equipo_principal_para_copa(equipo, sub19=sub19):
                continue

            equipos_con_nivel.append({
                "equipo": equipo,
                "liga": nombre_liga,
                "nivel": nivel_liga(nombre_liga),
                "posicion": posicion,
            })

    # Una misma entidad no puede entrar dos veces en la Copa.
    vistos = set()
    equipos_unicos = []

    for dato in equipos_con_nivel:
        equipo = dato["equipo"]
        if equipo in vistos:
            continue
        vistos.add(equipo)
        equipos_unicos.append(dato)

    # Primero los de divisiones inferiores; los mejores entran después.
    equipos_unicos.sort(
        key=lambda x: (
            -x["nivel"],
            -x["posicion"],
            x["equipo"],
        )
    )

    return equipos_unicos


def crear_copas_temporada(db, temporada):
    """
    Crea las Copas de Com, Tengu y Folimón para la temporada indicada.
    Se puede llamar también para la Temporada 1.
    """
    db.setdefault("copas", {})
    db["copas"]["temporada"] = temporada

    for pais in ["Principal", "Com", "Tengu", "Folimón"]:
        datos_senior = crear_datos_copa(db, pais, sub19=False)
        datos_sub19 = crear_datos_copa(db, pais, sub19=True)

        db["copas"][pais] = {
            "senior": {
                "nombre": f"Copa {pais} Senior",
                "temporada": temporada,
                "equipos": [x["equipo"] for x in datos_senior],
                "equipos_con_nivel": datos_senior,
                "eliminatorias": [],
            },
            "sub19": {
                "nombre": f"Copa {pais} Sub-19",
                "temporada": temporada,
                "equipos": [x["equipo"] for x in datos_sub19],
                "equipos_con_nivel": datos_sub19,
                "eliminatorias": [],
            },
        }


def generar_eliminatorias_copa(competicion):
    """
    Genera una Copa a partido único.
    Los equipos inferiores empiezan en rondas previas y los mejores
    reciben descansos hasta que el número de equipos sea una potencia de 2.
    """
    datos = competicion.get("equipos_con_nivel", [])

    if not datos:
        datos = [
            {
                "equipo": equipo,
                "nivel": 99,
                "posicion": 0,
            }
            for equipo in competicion.get("equipos", [])
        ]

    datos = sorted(
        datos,
        key=lambda x: (
            -x.get("nivel", 99),
            -x.get("posicion", 0),
            x["equipo"],
        )
    )

    # Mezclar dentro de cada nivel para que los cruces varíen cada temporada
    por_nivel = {}
    for d in datos:
        nivel = d["nivel"]
        por_nivel.setdefault(nivel, []).append(d)

    for nivel in por_nivel:
        random.shuffle(por_nivel[nivel])

    datos = [
        d
        for nivel in sorted(por_nivel.keys(), reverse=True)
        for d in por_nivel[nivel]
    ]

    if len(datos) < 2:
        return []

    # Mayor potencia de 2 inferior o igual al total de equipos.
    numero_ronda_final = 1
    while numero_ronda_final * 2 <= len(datos):
        numero_ronda_final *= 2

    equipos_que_entran = datos[:numero_ronda_final]
    equipos_previos = datos[numero_ronda_final:]

    rondas = []

    # Solo generamos "previa" si hay equipos_previos.
    # La siguiente ronda se genera al avanzar desde previa.
    if equipos_previos:
        # Si hay un número impar, el último pasa directamente a la siguiente ronda
        if len(equipos_previos) % 2 == 1:
            equipos_que_entran.append(equipos_previos[-1])
            equipos_previos = equipos_previos[:-1]

        cruces_previos = []

        for i in range(0, len(equipos_previos), 2):
            cruces_previos.append(
                crear_cruce_copa(
                    equipos_previos[i]["equipo"],
                    equipos_previos[i + 1]["equipo"],
                    "previa",
                )
            )

        if cruces_previos:
            rondas.append({
                "ronda": "previa",
                "cruces": cruces_previos,
            })

            # Guardamos los equipos base para usarlos al avanzar desde "previa"
            equipos_base = [x["equipo"] for x in equipos_que_entran]
            competicion["equipos_base"] = equipos_base
    else:
        # Si no hay previa, empezamos directamente con los equipos base
        equipos_base = [x["equipo"] for x in equipos_que_entran]

        if len(equipos_base) == 2:
            nombre_ronda = "semifinales"
        elif len(equipos_base) == 4:
            nombre_ronda = "cuartos"
        elif len(equipos_base) == 8:
            nombre_ronda = "octavos"
        else:
            nombre_ronda = "ronda inicial"

        cruces_base = []

        for i in range(0, len(equipos_base) - 1, 2):
            cruces_base.append(
                crear_cruce_copa(
                    equipos_base[i],
                    equipos_base[i + 1],
                    nombre_ronda,
                )
            )

        if cruces_base:
            rondas.append({
                "ronda": nombre_ronda,
                "cruces": cruces_base,
            })

    return rondas


def avanzar_ronda_copa(competicion):
    eliminatorias = competicion.get("eliminatorias", [])

    if not eliminatorias:
        return

    ronda_actual = eliminatorias[-1]
    ganadores = [
        cruce["ganador"]
        for cruce in ronda_actual.get("cruces", [])
        if cruce.get("ganador")
    ]

    if len(ganadores) < 2:
        return

    # Si venimos de "previa", mezclar ganadores con los equipos base
    if ronda_actual.get("ronda") == "previa":
        equipos_base = competicion.get("equipos_base", [])
        todos = ganadores + equipos_base
        random.shuffle(todos)
        ganadores = todos

    # Calcular la siguiente ronda según el número de equipos
    numero_equipos = len(ganadores)

    # Calcular la mayor potencia de 2 inferior o igual
    potencia = 1
    while potencia * 2 <= numero_equipos:
        potencia *= 2

    if numero_equipos == 2:
        siguiente = "final"
    elif numero_equipos == 4:
        siguiente = "semifinales"
    elif numero_equipos == 8:
        siguiente = "cuartos"
    elif numero_equipos == 16:
        siguiente = "octavos"
    else:
        # Si no es potencia de 2 exacta, seguir en "previa" o "ronda inicial"
        if ronda_actual.get("ronda") == "previa":
            siguiente = "previa"
        else:
            siguiente = "ronda inicial"

    random.shuffle(ganadores)
    cruces = []

    for i in range(0, len(ganadores) - 1, 2):
        cruces.append(
            crear_cruce_copa(
                ganadores[i],
                ganadores[i + 1],
                siguiente,
            )
        )

    if cruces:
        competicion["eliminatorias"].append({
            "ronda": siguiente,
            "cruces": cruces,
        })

def simular_partido_copa(cruce):
    """
    Las Copas usan exactamente la misma simulación que Jornada.
    El partido es único.
    """
    if cruce.get("resultado") is not None:
        return

    local = cruce["local"]
    visitante = cruce["visitante"]

    resultado = simular_partido_copa_interno(
        local,
        visitante,
        competicion="Copa",
    )

    cruce["resultado"] = [
        resultado["goles1"],
        resultado["goles2"],
    ]
    cruce["eventos"] = resultado.get("eventos", [])
    cruce["notas"] = resultado.get("notas_partido", [])
    cruce["alineacion_local"] = resultado.get("alineacion1", "-")
    cruce["alineacion_visitante"] = resultado.get("alineacion2", "-")

    if resultado["goles1"] > resultado["goles2"]:
        cruce["ganador"] = local
    elif resultado["goles2"] > resultado["goles1"]:
        cruce["ganador"] = visitante
    else:
        cruce["ganador"] = random.choice([local, visitante])

def render_pestana_copas():
    db = st.session_state.db

    st.title("🏆 Copas nacionales")

    copas = db.get("copas", {})
    temporada_actual = db["config"]["temporada"]

    if not copas or copas.get("temporada") != temporada_actual:
        st.info(
            "Todavía no hay copas para esta temporada."
        )
        return

    pais = st.selectbox(
        "País",
        ["Principal", "Com", "Tengu", "Folimón"],
        key="copa_pais",
    )

    categoria_visible = st.radio(
        "Categoría",
        ["Senior", "Sub-19"],
        horizontal=True,
        key="copa_categoria",
    )

    categoria = (
        "senior"
        if categoria_visible == "Senior"
        else "sub19"
    )

    competicion = copas.get(pais, {}).get(categoria)

    if not competicion:
        st.info(
            f"No hay Copa {pais} {categoria_visible}."
        )
        return

    st.subheader(competicion["nombre"])

    st.write(
        f"Equipos participantes: "
        f"{len(competicion.get('equipos', []))}"
    )

    with st.expander("Ver equipos participantes"):
        for equipo in competicion.get("equipos", []):
            st.write(f"- {equipo}")

    if not competicion.get("eliminatorias"):
        if len(competicion.get("equipos", [])) < 2:
            st.warning(
                "No hay suficientes equipos para crear la Copa."
            )
            return

        if st.button(
            "Crear eliminatorias",
            key=f"crear_copa_{pais}_{categoria}",
        ):
            competicion["eliminatorias"] = (
                generar_eliminatorias_copa(competicion)
            )
            st.rerun()

        return

    for ronda in competicion["eliminatorias"]:
        st.markdown(
            f"### {ronda['ronda'].capitalize()}"
        )

        for idx, cruce in enumerate(ronda.get("cruces", [])):
            local = cruce["local"]
            visitante = cruce["visitante"]
            resultado = cruce.get("resultado")

            if resultado is None:
                titulo = (
                    f"{local} vs {visitante}"
                )
            else:
                titulo = (
                    f"{local} {resultado[0]} - "
                    f"{resultado[1]} {visitante}"
                )

            with st.expander(titulo):
                if resultado is None:
                    st.write(
                        f"**Local:** {local}"
                    )
                    st.write(
                        f"**Visitante:** {visitante}"
                    )

                    if st.button(
                        "Jugar partido",
                        key=(
                            f"jugar_copa_{pais}_"
                            f"{categoria}_{ronda['ronda']}_{idx}"
                        ),
                    ):
                        simular_partido_copa(cruce)
                        st.rerun()

                else:
                    c1, c2 = st.columns(2)

                    c1.markdown(f"**{local}**")
                    c1.caption(
                        f"11: {cruce.get('alineacion_local', '-')}"
                    )

                    c2.markdown(f"**{visitante}**")
                    c2.caption(
                        f"11: {cruce.get('alineacion_visitante', '-')}"
                    )

                    st.divider()

                    st.success(
                        f"Clasificado: {cruce['ganador']}"
                    )

                    for evento in sorted(
                        cruce.get("eventos", []),
                        key=lambda x: x.get("min", 0),
                    ):
                        st.write(
                            f"**{evento.get('min', 0)}'** "
                            f"{evento.get('texto', '')}"
                        )

                    st.divider()

                    notas = cruce.get("notas", [])
                    if notas:
                        st.dataframe(
                            pd.DataFrame(notas),
                            hide_index=True,
                            use_container_width=True,
                        )

        ronda_completa = all(
            cruce.get("ganador")
            for cruce in ronda.get("cruces", [])
        )

        if ronda_completa:
            if ronda["ronda"] == "final":
                st.success(
                    f"🏆 Campeón: "
                    f"{ronda['cruces'][0]['ganador']}"
                )
            else:
                if st.button(
                    "Avanzar a la siguiente ronda",
                    key=(
                        f"avanzar_copa_{pais}_"
                        f"{categoria}_{ronda['ronda']}"
                    ),
                ):
                    avanzar_ronda_copa(competicion)
                    st.rerun()

def media_plantilla(equipo, pos=None):
    db = st.session_state.db
    jugadores = db["equipos_data"][equipo]["jugadores"]

    if pos:
        jugadores = [j for j in jugadores if j["pos"] == pos]

    if not jugadores:
        return 0

    return sum(j.get("media", 0) for j in jugadores) / len(jugadores)


def destino_puede_ficharlo(equipo_origen, equipo_destino, jugador):
    db = st.session_state.db

    liga_origen = db["equipos_data"][equipo_origen].get("liga", "")
    liga_destino = db["equipos_data"][equipo_destino].get("liga", "")

    nivel_origen = nivel_liga(liga_origen)
    nivel_destino = nivel_liga(liga_destino)

    if abs(nivel_origen - nivel_destino) >= 3:
        return False

    if nivel_destino - nivel_origen >= 2:
        return False

    media_equipo = media_plantilla(equipo_destino, jugador["pos"])
    if media_equipo == 0:
        media_equipo = media_plantilla(equipo_destino)

    diferencia_media = abs(jugador.get("media", 0) - media_equipo)
    edad = jugador.get("edad", 24)
    media_jugador = jugador.get("media", 0)

    if es_equipo_sub19(equipo_destino):
        if edad > 20:
            return False
        if media_jugador > media_equipo + 12:
            return False
        return True

    if nivel_destino < nivel_origen and media_jugador >= media_equipo + 12:
        return False

    if nivel_destino > nivel_origen and media_jugador + 10 < media_equipo:
        return False

    if diferencia_media > 9:
        return False

    return True

def obtener_tramo_activo(jugador):
    temporada_actual = st.session_state.db["config"]["temporada"]
    equipo_actual = jugador.get("equipo_actual", "-")
    jugador.setdefault("historial_temporadas", [])

    for tramo in reversed(jugador["historial_temporadas"]):
        if tramo.get("temporada") == temporada_actual and tramo.get("equipo") == equipo_actual:
            return tramo

    tramo = {
        "temporada": temporada_actual,
        "equipo": equipo_actual,
        "tipo_estancia": "normal",
        "partidos": 0,
        "partidos_titular": 0,
        "minutos": 0,
        "goles": 0,
        "asistencias": 0,
        "amarillas": 0,
        "rojas": 0,
        "goles_encajados": 0,
        "nota_total": 0,
    }
    jugador["historial_temporadas"].append(tramo)
    return tramo


def abrir_tramo_temporada(jugador, equipo, tipo_estancia="normal", competicion="Liga"):
    temporada_actual = st.session_state.db["config"]["temporada"]
    jugador.setdefault("historial_temporadas", [])

    # Buscar tramo existente con la misma clave (temporada, equipo, tipo_estancia, competicion)
    for tramo in reversed(jugador["historial_temporadas"]):
        if (
            tramo.get("temporada") == temporada_actual and
            tramo.get("equipo") == equipo and
            tramo.get("tipo_estancia") == tipo_estancia and
            tramo.get("competicion") == competicion
        ):
            return tramo

    # Si no existe, crear uno nuevo
    tramo = {
        "temporada": temporada_actual,
        "equipo": equipo,
        "tipo_estancia": tipo_estancia,
        "competicion": competicion,
        "partidos": 0,
        "partidos_titular": 0,
        "minutos": 0,
        "goles": 0,
        "asistencias": 0,
        "amarillas": 0,
        "rojas": 0,
        "goles_encajados": 0,
        "nota_total": 0,
    }
    jugador["historial_temporadas"].append(tramo)
    return tramo

def obtener_tramo_equipo_temporada(jugador, equipo, temporada=None):
    if temporada is None:
        temporada = st.session_state.db["config"]["temporada"]

    jugador.setdefault("historial_temporadas", [])

    for tramo in reversed(jugador["historial_temporadas"]):
        if tramo.get("temporada") == temporada and tramo.get("equipo") == equipo:
            return tramo

    return {
        "temporada": temporada,
        "equipo": equipo,
        "tipo_estancia": "normal",
        "partidos": 0,
        "partidos_titular": 0,
        "minutos": 0,
        "goles": 0,
        "asistencias": 0,
        "amarillas": 0,
        "rojas": 0,
        "goles_encajados": 0,
        "nota_total": 0,
        "media_partidos": 0,
    }

def jugador_movido_esta_temporada(jugador):
    temporada_actual = st.session_state.db["config"]["temporada"]
    for mov in jugador.get("historial_traspasos", []):
        if mov.get("temporada") == temporada_actual and mov.get("tipo") != "fin cesión":
            return True
    return False

def liberar_plaza_promocionado(club_principal):
    db = st.session_state.db

    if club_principal not in db["equipos_data"]:
        return False, "Club principal no encontrado."

    plantilla = db["equipos_data"][club_principal]["jugadores"]

    promocionados = [
        j for j in plantilla
        if j.get("promocion_temporal", False)
    ]

    if len(promocionados) < 7:
        return True, None

    # Ordenar por importancia: menos media, menos minutos, menos titular
    candidatos = sorted(
        promocionados,
        key=lambda j: (
            j.get("media", 0),
            j.get("partidos_titular", 0),
            j.get("minutos_totales", 0)
        )
    )

    for jugador in candidatos:
        # No sacar al único portero
        if jugador.get("pos") == "POR":
            if sum(1 for j in plantilla if j.get("pos") == "POR") <= 1:
                continue

        nombre = jugador["nombre"]

        # Intentar cederlo a un equipo vinculado (no Sub-19)
        equipos_vinculados = obtener_equipos_vinculados_del_club(club_principal)

        destinos = [
            eq for eq in equipos_vinculados
            if eq != club_principal
            and eq in db["equipos_data"]
            and not es_equipo_sub19(eq)
        ]

        # Ordenar destinos por nivel de liga y media de plantilla
        destinos.sort(
            key=lambda eq: (
                nivelligaliga(db["equipos_data"][eq].get("liga", "")),
                mediaplantillaequipo(db, eq, jugador.get("pos"))
            ),
            reverse=True
        )

        for destino in destinos:
            precio_cesion = max(0.1, round(float(jugador.get("valor", 0.1)) * 0.15, 1))

            ok, msg = hacer_cesion(
                nombre,
                club_principal,
                destino,
                precio_cesion,
                1,
                False,
                0.0
            )

            if ok:
                return True, f"{nombre} cedido a {destino} para liberar una plaza."

        # Si no se puede ceder, ponerlo a la venta
        if jugador in plantilla:
            plantilla.remove(jugador)

            jugador["promocion_temporal"] = False
            jugador["bloqueado_filial_sub19"] = False
            jugador["equipo_actual"] = None
            jugador["propietario"] = None

            db.setdefault("ofertas_automaticas", []).append({
                "jugador": nombre,
                "origen": club_principal,
                "tipo": "traspaso",
                "precio": max(0.1, float(jugador.get("valor", 0.1))),
                "temporada": db["config"]["temporada"]
            })

            db["mercado_log"].append(
                f"{club_principal} pone a la venta a {nombre} para liberar una plaza de promocionado"
            )

            return True, f"{nombre} puesto a la venta para liberar una plaza."

    return False, "No se pudo liberar ninguna plaza de promocionado."

def promocionar_a_primer_equipo(
    jugador_nombre,
    equipo_origen,
    club_principal
):
    db = st.session_state.db

    if not es_equipo_principal(club_principal):
        return False, "El destino debe ser un primer equipo."

    # Bloque total: CEREZAS y RB Zerkas no reciben promociones automáticas
    if obtener_club_principal(club_principal) in {"CEREZAS", "RB Zerkas", "EKIPO"}:
        return False, f"{club_principal} no recibe promociones automáticas."

    if obtener_club_principal(equipo_origen) != club_principal:
        return False, "Solo puedes promocionar desde un equipo vinculado del mismo club."

    if not puede_promocionar_a_primer_equipo(club_principal):
        return False, f"{club_principal} ya tiene 7 jugadores permanentes en el primer equipo."

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][club_principal]["jugadores"]

    jugador = next(
        (j for j in origen if j["nombre"] == jugador_nombre),
        None
    )
    if jugador is None:
        return False, "Jugador no encontrado."

    if jugador.get("cedido", False):
        return False, "No puedes promocionar a un jugador cedido."

    if jugador.get("ficha_primer_equipo", False):
        return False, "Ese jugador ya tiene ficha del primer equipo."

    if jugador.get("promocion_temporal", False):
        return False, "Ese jugador ya está promocionado al primer equipo."

    origen.remove(jugador)

    if contar_porteros(equipo_origen) == 1:
        iniciar_alerta_porteria(equipo_origen, 3)
        if not es_equipo_sub19(equipo_origen):
            intentar_regularizar_porteria_desde_cantera(equipo_origen)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo_origen)

    destino.append(jugador)

    jugador["equipo_base"] = equipo_origen
    jugador["equipo_actual"] = club_principal
    jugador["propietario"] = club_principal
    jugador["promocion_temporal"] = True
    jugador["bloqueado_filial_sub19"] = True
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = None
    jugador["ficha_filial"] = False
    jugador["filial_asignado"] = None

    abrir_tramo_temporada(jugador, club_principal, "promoción primer equipo")

    registrar_traspaso(
        jugador,
        equipo_origen,
        club_principal,
        tipo="promoción primer equipo",
        temporada=db["config"]["temporada"],
        valor=0,
    )

    db["mercado_log"].append(
        f"🔼 Promoción: {jugador_nombre} sube de {equipo_origen} "
        f"a {club_principal} para el primer equipo"
    )

    return True, "Promoción al primer equipo realizada."

def dar_ficha_primer_equipo(jugador_nombre, equipo_origen, club_principal):
    db = st.session_state.db

    if not es_equipo_principal(club_principal):
        return False, "La ficha solo se puede asignar a un primer equipo."

    if obtener_club_principal(equipo_origen) != club_principal:
        return False, "Solo puedes dar ficha a jugadores del mismo club."

    if not puede_dar_ficha_primer_equipo(club_principal):
        return False, f"{club_principal} ya tiene 10 jugadores efectivos."

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado."

    if jugador.get("cedido", False):
        return False, "No puedes dar ficha a un jugador cedido."

    if jugador.get("promocion_temporal", False):
        return False, "Ese jugador ya está promocionado al primer equipo."

    if jugador.get("ficha_primer_equipo", False) and jugador.get("primer_equipo_asignado") == club_principal:
        return False, "Ese jugador ya tiene ficha del primer equipo."

    jugador["equipo_base"] = equipo_origen
    jugador["ficha_primer_equipo"] = True
    jugador["primer_equipo_asignado"] = club_principal
    jugador["bloqueado_filial_sub19"] = False

    db["mercado_log"].append(
        f"🪪 Ficha primer equipo: {jugador_nombre} queda inscrito con {club_principal} pero sigue en {equipo_origen}"
    )

    return True, "Ficha del primer equipo asignada."

def promocionar_jugador_a_primer_equipo(jugador_nombre, equipo_origen):
    db = st.session_state.db

    if equipo_origen not in db["equipos_data"]:
        return False, "Equipo origen no válido"

    if es_equipo_principal(equipo_origen):
        return False, "Ese jugador ya está en un primer equipo"

    club_principal = obtener_club_principal(equipo_origen)
    if club_principal not in db["equipos_data"]:
        return False, "No se encontró el primer equipo asociado"

    if not puede_promocionar_a_primer_equipo(club_principal):
        return False, f"{club_principal} ya tiene 7 jugadores permanentes en el primer equipo"

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][club_principal]["jugadores"]

    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador.get("cedido", False):
        return False, "No puedes promocionar a un jugador que está cedido"

    if jugador.get("ficha_primer_equipo", False):
        return False, "Ese jugador ya tiene ficha del primer equipo"

    if jugador.get("promocion_temporal", False):
        return False, "Ese jugador ya está promocionado al primer equipo"

    origen.remove(jugador)

    if contar_porteros(equipo_origen) == 1:
        iniciar_alerta_porteria(equipo_origen, 3)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo_origen)

    destino.append(jugador)

    jugador["equipo_actual"] = club_principal
    jugador["propietario"] = club_principal
    jugador["equipo_base"] = equipo_origen
    jugador["promocion_temporal"] = True
    jugador["bloqueado_filial_sub19"] = True
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = None
    jugador["ficha_filial"] = False
    jugador["filial_asignado"] = None

    abrir_tramo_temporada(jugador, club_principal, "promoción primer equipo")

    # NUEVO: registrar la promoción en el historial de traspasos
    registrar_traspaso(
        jugador,
        equipo_origen,
        club_principal,
        tipo="promoción primer equipo",
        temporada=db["config"]["temporada"],
        valor=0,
    )

    db["mercado_log"].append(
        f"🔼 Promoción al primer equipo: {jugador_nombre} pasa de {equipo_origen} a {club_principal}"
    )

    return True, "Jugador promocionado al primer equipo"

def descender_jugador_a_filial(jugador_nombre, equipo_origen, equipo_destino):
    """
    Desciende un jugador del primer equipo al filial (ej: CEREZAS -> CEREZAS B)
    o del filial al Sub-19. El Sub-19 puede tener hasta 10 jugadores.
    El jugador debe pertenecer al equipo origen (no basta con tener ficha).
    Si el destino es Sub-19, el jugador debe tener 19 años o menos.
    """
    db = st.session_state.db
    
    if equipo_origen not in db["equipos_data"] or equipo_destino not in db["equipos_data"]:
        return False, "Equipo origen o destino no válido"
    
    # Solo permitido entre equipos vinculados
    if not son_clubes_vinculados(equipo_origen, equipo_destino):
        return False, "Solo se puede descender entre equipos del mismo club"
    
    # El destino debe ser un equipo inferior (filial o Sub-19)
    if not (equipo_destino.endswith(" B") or equipo_destino.endswith(" C") or es_equipo_sub19(equipo_destino)):
        return False, "El destino debe ser un filial o Sub-19"
    
    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][equipo_destino]["jugadores"]
    
    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado en el equipo origen"
    
    # El jugador debe pertenecer al equipo (no vale con tener ficha)
    if jugador.get("equipo_actual") != equipo_origen:
        return False, f"El jugador no pertenece a {equipo_origen}, está en {jugador.get('equipo_actual')}"
    
    # No se puede descender a un jugador cedido
    if jugador.get("cedido", False):
        return False, "No puedes descender a un jugador que está cedido"
    
    # Si el destino es Sub-19, el jugador debe tener 19 años o menos
    if es_equipo_sub19(equipo_destino) and jugador.get("edad", 0) > 19:
        return False, f"No se puede descender a {equipo_destino} a un jugador de {jugador.get('edad')} años (máx. 19)"
    
    # Comprobar límite del equipo destino (Sub-19 puede tener 10, filiales 8)
    max_jugadores_destino = 10 if es_equipo_sub19(equipo_destino) else 8
    if len(destino) >= max_jugadores_destino:
        return False, f"{equipo_destino} ya tiene demasiados jugadores (máx. {max_jugadores_destino})"
    
    # Mover al jugador
    origen.remove(jugador)
    destino.append(jugador)
    
    # Actualizar datos del jugador
    jugador["equipo_actual"] = equipo_destino
    jugador["propietario"] = equipo_destino
    jugador["equipo_base"] = equipo_destino
    jugador["promocion_temporal"] = False
    jugador["bloqueado_filial_sub19"] = False
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = None
    jugador["ficha_filial"] = False
    jugador["filial_asignado"] = None
    
    # Registrar en historial
    abrir_tramo_temporada(jugador, equipo_destino, "descenso interno")
    registrar_traspaso(
        jugador,
        equipo_origen,
        equipo_destino,
        tipo="descenso interno",
        temporada=db["config"]["temporada"],
        valor=0,
    )
    
    db["mercado_log"].append(
        f"⬇️ Descenso interno: {jugador_nombre} pasa de {equipo_origen} a {equipo_destino}"
    )
    
    return True, f"Jugador descendido a {equipo_destino}"


def descender_jugador_a_sub19(jugador_nombre, equipo_origen):
    """
    Desciende un jugador del filial al Sub-19 (ej: CEREZAS B -> CEREZAS Sub-19)
    """
    db = st.session_state.db
    
    club_base = obtener_club_principal(equipo_origen)
    
    # Buscar el Sub-19 del club
    equipo_destino = None
    for eq in db["equipos_data"].keys():
        if obtener_club_principal(eq) == club_base and es_equipo_sub19(eq):
            equipo_destino = eq
            break
    
    if not equipo_destino:
        return False, "No se encontró el equipo Sub-19 asociado"
    
    return descender_jugador_a_filial(jugador_nombre, equipo_origen, equipo_destino)

def ascender_portero_entre_vinculados(jugador_nombre, equipo_origen, equipo_destino):
    db = st.session_state.db

    if equipo_origen not in db["equipos_data"] or equipo_destino not in db["equipos_data"]:
        return False, "Equipo origen o destino no válido"

    if not son_clubes_vinculados(equipo_origen, equipo_destino):
        return False, "Solo se permiten ascensos entre equipos vinculados del mismo club"

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][equipo_destino]["jugadores"]

    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador.get("pos") != "POR":
        return False, "Solo se usa esta función para porteros"

    if jugador.get("cedido", False):
        return False, "No puedes ascender a un jugador cedido"

    origen.remove(jugador)

    if contar_porteros(equipo_origen) == 1:
        iniciar_alerta_porteria(equipo_origen, 3)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo_origen)

    destino.append(jugador)

    jugador["equipo_actual"] = equipo_destino
    jugador["propietario"] = equipo_destino
    jugador["equipo_base"] = equipo_origen
    jugador["cedido"] = False
    jugador["cedido_hasta"] = 0
    jugador["promocion_temporal"] = True
    jugador["bloqueado_filial_sub19"] = True
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = equipo_destino if es_equipo_principal(equipo_destino) else None

    abrir_tramo_temporada(jugador, equipo_destino, "ascenso portero")

    # NUEVO: registrar ascenso interno en historial de traspasos
    registrar_traspaso(
        jugador,
        equipo_origen,
        equipo_destino,
        tipo="ascenso portero interno",
        temporada=db["config"]["temporada"],
        valor=0,
    )

    db["mercado_log"].append(
        f"🧤 Ascenso portero: {jugador_nombre} pasa de {equipo_origen} a {equipo_destino}"
    )

    if contar_porteros(equipo_destino) >= 2:
        limpiar_alerta_porteria_si_corresponde(equipo_destino)

    return True, "Ascenso de portero realizado"

def dar_ficha_primer_equipo_a_jugador(jugador_nombre, equipo_origen):
    db = st.session_state.db

    if equipo_origen not in db["equipos_data"]:
        return False, "Equipo origen no válido"

    if es_equipo_principal(equipo_origen):
        return False, "Ese jugador ya pertenece al primer equipo"

    club_principal = obtener_club_principal(equipo_origen)
    if club_principal not in db["equipos_data"]:
        return False, "No se encontró el primer equipo asociado"

    if not puede_dar_ficha_primer_equipo(club_principal):
        return False, f"{club_principal} ya tiene 10 jugadores efectivos."

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador.get("cedido", False):
        return False, "No puedes dar ficha a un jugador cedido"

    if jugador.get("ficha_primer_equipo", False):
        return False, "Ese jugador ya tiene ficha del primer equipo"

    jugador["ficha_primer_equipo"] = True
    jugador["primer_equipo_asignado"] = club_principal
    jugador["promocion_temporal"] = False
    jugador["bloqueado_filial_sub19"] = False

    db["mercado_log"].append(
        f"🪪 Ficha de primer equipo: {jugador_nombre} mantiene plaza en {equipo_origen} y obtiene ficha con {club_principal}"
    )
    return True, "Jugador con ficha del primer equipo"

def ascender_jugador_al_siguiente_equipo(jugador_nombre, equipo_origen):
    db = st.session_state.db

    if equipo_origen not in db["equipos_data"]:
        return False, "Equipo origen no válido"

    destino = obtener_siguiente_equipo_por_edad(equipo_origen)
    if not destino or destino not in db["equipos_data"]:
        return False, "No existe un equipo superior disponible para ese jugador"

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    plantilla_destino = db["equipos_data"][destino]["jugadores"]

    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador.get("cedido", False):
        return False, "No puedes ascender a un jugador que está cedido"

    if len(plantilla_destino) >= 8:
        return False, f"{destino} ya tiene demasiados jugadores"

    origen.remove(jugador)
    plantilla_destino.append(jugador)

    jugador["equipo_actual"] = destino
    jugador["propietario"] = destino
    jugador["equipo_base"] = destino
    jugador["promocion_temporal"] = False
    jugador["bloqueado_filial_sub19"] = False
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = None

    abrir_tramo_temporada(jugador, destino, "ascenso interno")

    # NUEVO: registrar ascenso interno en historial de traspasos
    registrar_traspaso(
        jugador,
        equipo_origen,
        destino,
        tipo="ascenso interno",
        temporada=db["config"]["temporada"],
        valor=0,
    )

    db["mercado_log"].append(
        f"🔼 Ascenso interno: {jugador_nombre} pasa de {equipo_origen} a {destino}"
    )

    return True, f"Jugador ascendido a {destino}"

def dar_ficha_filial_a_jugador(jugador_nombre, equipo_origen, equipo_filial):
    db = st.session_state.db

    if equipo_origen not in db["equipos_data"] or equipo_filial not in db["equipos_data"]:
        return False, "Equipo no válido"

    if not es_equipo_sub19(equipo_origen):
        return False, "La ficha del filial solo se puede dar desde un Sub-19"

    if obtener_club_principal(equipo_origen) != obtener_club_principal(equipo_filial):
        return False, "Solo puedes dar ficha dentro de la misma estructura del club"

    if not puede_dar_ficha_filial(equipo_filial):
        return False, f"{equipo_filial} ya tiene 10 jugadores efectivos."

    origen = db["equipos_data"][equipo_origen]["jugadores"]
    jugador = next((j for j in origen if j["nombre"] == jugador_nombre), None)
    if jugador is None:
        return False, "Jugador no encontrado"

    if jugador.get("cedido", False):
        return False, "No puedes dar ficha a un jugador cedido"

    if jugador.get("promocion_temporal", False):
        return False, "Ese jugador ya está promocionado"

    if jugador.get("ficha_filial", False) and jugador.get("filial_asignado") == equipo_filial:
        return False, "Ese jugador ya tiene ficha del filial"

    jugador["equipo_base"] = equipo_origen
    jugador["ficha_filial"] = True
    jugador["filial_asignado"] = equipo_filial
    jugador["bloqueado_filial_sub19"] = False

    db["mercado_log"].append(
        f"🪪 Ficha filial: {jugador_nombre} queda inscrito con {equipo_filial} pero sigue en {equipo_origen}"
    )

    return True, f"Ficha de {equipo_filial} asignada"

    
def quitar_ficha_primer_equipo(jugador):
    jugador["ficha_primer_equipo"] = False
    jugador["primer_equipo_asignado"] = None
            
def hacer_traspaso(
    jugador_nombre,
    equipo_origen,
    equipo_destino,
    monto=None,
    forzar_usuario=False
):
    db = st.session_state.db
    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][equipo_destino]["jugadores"]

    jugador = next(
        (j for j in origen if j["nombre"] == jugador_nombre),
        None
    )

    if jugador is None:
        return False, "Jugador no encontrado"

    if son_clubes_vinculados(equipo_origen, equipo_destino):
        return False, (
            "Entre equipos vinculados no se usa el mercado normal; "
            "usa movimiento interno"
        )

    if jugador_movido_esta_temporada(jugador):
        return False, "Este jugador ya ha sido movido esta temporada"

    # Límites reales del equipo comprador
    if es_equipo_principal(equipo_destino):
        club_principal = obtener_club_principal(equipo_destino)

        if contar_jugadores_primer_equipo(club_principal) >= 7:
            return False, (
                f"{club_principal} ya tiene 7 jugadores permanentes "
                f"en el primer equipo."
            )

        if contar_total_efectivos_primer_equipo(club_principal) >= 10:
            return False, f"{club_principal} ya tiene 10 jugadores efectivos."

    if len(destino) >= 8:
        return False, "El equipo destino ya tiene demasiados jugadores"

    # Nunca vender el último portero
    if jugador["pos"] == "POR" and contar_porteros(equipo_origen) <= 1:
        return False, (
            "No puedes traspasar ese portero: el equipo origen "
            "debe quedarse con al menos 1 portero"
        )

    # Mantener la regla de nivel/encaje del club comprador
    if not destino_puede_ficharlo(equipo_origen, equipo_destino, jugador):
        return False, (
            f"{equipo_destino} no debería fichar a {jugador_nombre} "
            "por nivel o por encaje de plantilla"
        )

    # Solo los clubes IA respetan la regla de jugador importante/no vendible
    if not forzar_usuario:
        if not jugador_es_vendible(equipo_origen, jugador):
            return False, f"{jugador_nombre} no está en venta ahora mismo"

    liga_origen = db["equipos_data"][equipo_origen].get("liga", "")
    liga_destino = db["equipos_data"][equipo_destino].get("liga", "")

    partidos_titular = jugador.get("partidos_titular", 0)
    minutos = jugador.get("minutos_totales", 0)
    media = jugador.get("media", 0)
    edad = jugador.get("edad", 24)

    # Para clubes automáticos se conserva la regla de no bajar de 1ª a 2ª.
    # Para una aceptación manual tuya se permite.
    if (
        not forzar_usuario
        and liga_origen == "1ª División"
        and liga_destino == "2ª División"
    ):
        es_poco_importante = partidos_titular <= 3 or minutos < 180
        perfil_aceptable_bajar = media <= 78 or edad >= 30

        if not (es_poco_importante or perfil_aceptable_bajar):
            return False, f"{jugador_nombre} no quiere bajar de 1ª a 2ª División"

    if monto is None:
        monto = calcular_precio_traspaso(
            jugador,
            equipo_origen,
            equipo_destino
        )

    monto = float(monto)

    if es_equipo_sub19(equipo_destino) and monto > 1.5:
        return False, f"{equipo_destino} no puede fichar por más de 1,5M"

    # Nunca se salta el presupuesto del comprador
    presupuesto_destino = obtener_presupuesto_equipo(equipo_destino)

    if presupuesto_destino < monto:
        club_pagador = obtener_equipo_pagador(equipo_destino)
        return False, (
            f"{club_pagador} no tiene presupuesto suficiente "
            f"para fichar a {jugador_nombre}"
        )

    origen.remove(jugador)

    if contar_porteros(equipo_origen) == 1:
        iniciar_alerta_porteria(equipo_origen, 3)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo_origen)

    destino.append(jugador)

    jugador["equipo_actual"] = equipo_destino
    jugador["propietario"] = equipo_destino
    jugador["cedido"] = False
    jugador["cedido_hasta"] = 0

    restar_presupuesto_equipo(equipo_destino, monto)
    sumar_presupuesto_equipo(equipo_origen, monto)

    abrir_tramo_temporada(jugador, equipo_destino, "traspaso")

    registrar_traspaso(
        jugador,
        equipo_origen,
        equipo_destino,
        tipo="traspaso",
        valor=monto
    )

    # Registrar en movimientos de presupuesto
    db.setdefault("movimientos_presupuesto", []).append({
        "equipo": equipo_origen,
        "temporada": db["config"]["temporada"],
        "tipo": "ingreso",
        "concepto": f"Traspaso de {jugador_nombre} a {equipo_destino}",
        "importe": monto
    })
    db["movimientos_presupuesto"].append({
        "equipo": equipo_destino,
        "temporada": db["config"]["temporada"],
        "tipo": "gasto",
        "concepto": f"Traspaso de {jugador_nombre} desde {equipo_origen}",
        "importe": monto
    })

    db["mercado_log"].append(
        f"✅ Traspaso: {jugador_nombre} de {equipo_origen} "
        f"a {equipo_destino} por {formatear_valor(monto)} "
        f"(paga {obtener_equipo_pagador(equipo_destino)})"
    )

    return True, "Traspaso realizado"


def hacer_cesion(
    jugador_nombre,
    equipo_origen,
    equipo_destino,
    monto=0,
    duracion=1,
    opcion_compra=False,
    precio_opcion_compra=None,
    forzar_usuario=False
):
    db = st.session_state.db
    origen = db["equipos_data"][equipo_origen]["jugadores"]
    destino = db["equipos_data"][equipo_destino]["jugadores"]

    jugador = next(
        (j for j in origen if j["nombre"] == jugador_nombre),
        None
    )

    if jugador is None:
        return False, "Jugador no encontrado"

    if son_clubes_vinculados(equipo_origen, equipo_destino):
        return False, (
            "Entre equipos vinculados no se usa la cesión normal; "
            "usa movimiento interno"
        )

    if jugador_movido_esta_temporada(jugador):
        return False, "Este jugador ya ha sido movido esta temporada"

    if jugador["cedido"]:
        return False, "El jugador ya está cedido"

    # Límites reales del equipo que recibe al jugador
    if es_equipo_principal(equipo_destino):
        club_principal = obtener_club_principal(equipo_destino)

        if contar_jugadores_primer_equipo(club_principal) >= 7:
            return False, (
                f"{club_principal} ya tiene 7 jugadores permanentes "
                f"en el primer equipo."
            )

        if contar_total_efectivos_primer_equipo(club_principal) >= 10:
            return False, f"{club_principal} ya tiene 10 jugadores efectivos."

    if len(destino) >= 8:
        return False, "El equipo destino ya tiene demasiados jugadores"

    # Nunca ceder al último portero
    if jugador["pos"] == "POR" and contar_porteros(equipo_origen) <= 1:
        return False, (
            "No puedes ceder ese portero: el equipo origen "
            "debe quedarse con al menos 1 portero"
        )

    # Mantener control de nivel / encaje
    if not destino_puede_ficharlo(equipo_origen, equipo_destino, jugador):
        return False, f"{equipo_destino} no es un destino lógico para {jugador_nombre}"

    # Bloqueos de importancia solo para clubes automáticos
    if not forzar_usuario:
        if not jugador_es_vendible(equipo_origen, jugador):
            return False, f"{jugador_nombre} no está disponible para salir ahora mismo"

    liga_origen = db["equipos_data"][equipo_origen].get("liga", "")
    liga_destino = db["equipos_data"][equipo_destino].get("liga", "")

    partidos_titular = jugador.get("partidos_titular", 0)
    minutos = jugador.get("minutos_totales", 0)
    media = jugador.get("media", 0)

    jugador_importante = (
        partidos_titular >= 6
        or minutos >= 240
        or media >= 84
    )

    # Si tú lo decides manualmente, puede salir aunque sea importante
    if not forzar_usuario and jugador_importante:
        return False, (
            f"{jugador_nombre} no sale cedido porque cuenta mucho "
            f"para {equipo_origen}"
        )

    if (
        not forzar_usuario
        and liga_origen == "1ª División"
        and liga_destino == "1ª División"
        and minutos >= 180
        and partidos_titular >= 4
    ):
        return False, (
            f"{jugador_nombre} no necesita cesión "
            "porque ya está teniendo protagonismo"
        )

    # Nunca se salta el presupuesto del club que recibe la cesión
    monto = float(monto)
    presupuesto_destino = obtener_presupuesto_equipo(equipo_destino)

    if presupuesto_destino < monto:
        club_pagador = obtener_equipo_pagador(equipo_destino)
        return False, (
            f"{club_pagador} no tiene presupuesto suficiente "
            f"para la cesión de {jugador_nombre}"
        )

    if opcion_compra:
        if precio_opcion_compra is None:
            precio_opcion_compra = round(
                calcular_precio_traspaso(
                    jugador,
                    equipo_origen,
                    equipo_destino
                ) * 0.95,
                1
            )

        precio_opcion_compra = max(
            0.1,
            round(float(precio_opcion_compra), 1
            )
        )
    else:
        precio_opcion_compra = 0

    origen.remove(jugador)

    if contar_porteros(equipo_origen) == 1:
        iniciar_alerta_porteria(equipo_origen, 3)
    else:
        limpiar_alerta_porteria_si_corresponde(equipo_origen)

    destino.append(jugador)

    jugador["equipo_actual"] = equipo_destino
    jugador["propietario"] = equipo_origen
    jugador["cedido"] = True
    jugador["cedido_hasta"] = (
        db["config"]["temporada"] + max(1, duracion) - 1
    )

    jugador["opcion_compra"] = bool(opcion_compra)
    jugador["precio_opcion_compra"] = precio_opcion_compra
    jugador["equipo_opcion_compra"] = (
        equipo_destino if opcion_compra else None
    )
    jugador["temporada_opcion_compra"] = (
        jugador["cedido_hasta"] if opcion_compra else None
    )

    restar_presupuesto_equipo(equipo_destino, monto)
    sumar_presupuesto_equipo(equipo_origen, monto)

    # Registrar en movimientos de presupuesto (solo si hay dinero)
    if monto > 0:
        db.setdefault("movimientos_presupuesto", []).append({
            "equipo": equipo_origen,
            "temporada": db["config"]["temporada"],
            "tipo": "ingreso",
            "concepto": f"Cesión de {jugador_nombre} a {equipo_destino}",
            "importe": monto
        })
        db["movimientos_presupuesto"].append({
            "equipo": equipo_destino,
            "temporada": db["config"]["temporada"],
            "tipo": "gasto",
            "concepto": f"Cesión de {jugador_nombre} desde {equipo_origen}",
            "importe": monto
        })

    abrir_tramo_temporada(jugador, equipo_destino, "cesión")

    tipo_mov = f"cesión ({duracion} temp.)"
    if opcion_compra:
        tipo_mov += (
            f" con OP "
            f"({formatear_valor(precio_opcion_compra)})"
        )

    registrar_traspaso(
        jugador,
        equipo_origen,
        equipo_destino,
        tipo=tipo_mov,
        valor=monto
    )

    texto_log = (
        f"📤 Cesión: {jugador_nombre} de {equipo_origen} "
        f"a {equipo_destino} por {formatear_valor(monto)} "
        f"durante {duracion} temporada(s)"
    )

    if opcion_compra:
        texto_log += (
            f" con OP de "
            f"{formatear_valor(precio_opcion_compra)}"
        )

    texto_log += f" (paga {obtener_equipo_pagador(equipo_destino)})"

    db["mercado_log"].append(texto_log)

    return True, "Cesión realizada"


def ejecutar_opcion_compra(jugador, equipo_actual_cesion):
    db = st.session_state.db

    if not jugador.get("cedido", False):
        return False, "El jugador no está cedido"

    if not jugador.get("opcion_compra", False):
        return False, "La cesión no tiene opción de compra"

    propietario = jugador.get("propietario")
    comprador = jugador.get("equipo_opcion_compra", equipo_actual_cesion)
    precio = float(jugador.get("precio_opcion_compra", 0))

    if equipo_actual_cesion != comprador:
        return False, "El jugador no está en el club con derecho de compra"

    if propietario not in db["equipos_data"] or comprador not in db["equipos_data"]:
        return False, "Club no válido"

    presupuesto = obtener_presupuesto_equipo(comprador)
    if presupuesto < precio:
        return False, f"{obtener_equipo_pagador(comprador)} no tiene presupuesto suficiente"

    jugador["propietario"] = comprador
    jugador["equipo_actual"] = comprador
    jugador["cedido"] = False
    jugador["cedido_hasta"] = 0

    restar_presupuesto_equipo(comprador, precio)
    sumar_presupuesto_equipo(propietario, precio)

    # Registrar en movimientos de presupuesto
    db.setdefault("movimientos_presupuesto", []).append({
        "equipo": propietario,
        "temporada": db["config"]["temporada"],
        "tipo": "ingreso",
        "concepto": f"Opción de compra de {jugador['nombre']} desde {comprador}",
        "importe": precio
    })
    db["movimientos_presupuesto"].append({
        "equipo": comprador,
        "temporada": db["config"]["temporada"],
        "tipo": "gasto",
        "concepto": f"Opción de compra de {jugador['nombre']} a {propietario}",
        "importe": precio
    })

    registrar_traspaso(jugador, propietario, comprador, tipo="opción de compra ejecutada", valor=precio)
    abrir_tramo_temporada(jugador, comprador, "traspaso")

    jugador["opcion_compra"] = False
    jugador["precio_opcion_compra"] = 0
    jugador["equipo_opcion_compra"] = None
    jugador["temporada_opcion_compra"] = None

    db["mercado_log"].append(
        f"🛒 Opción de compra ejecutada: {jugador['nombre']} pasa de {propietario} a {comprador} por {formatear_valor(precio)} "
        f"(paga {obtener_equipo_pagador(comprador)})"
    )

    return True, "Opción de compra ejecutada"

def decidir_opcion_compra_ia(jugador, equipo_actual_cesion):
    db = st.session_state.db

    if not jugador.get("cedido", False):
        return False, "El jugador no está cedido"

    if not jugador.get("opcion_compra", False):
        return False, "La cesión no tiene opción de compra"

    precio = float(jugador.get("precio_opcion_compra", 0))
    presupuesto = obtener_presupuesto_equipo(equipo_actual_cesion)

    if presupuesto < precio:
        return False, f"{equipo_actual_cesion} no tiene presupuesto para ejecutar la opción"

    media = jugador.get("media", 0)
    edad = jugador.get("edad", 24)
    minutos = jugador.get("minutos_totales", 0)
    partidos_titular = jugador.get("partidos_titular", 0)

    media_equipo = media_plantilla(equipo_actual_cesion, jugador.get("pos"))
    if media_equipo == 0:
        media_equipo = media_plantilla(equipo_actual_cesion)

    mejora = media - media_equipo
    factor_uso = partidos_titular + (minutos / 90.0)
    factor_precio = precio / max(1.0, presupuesto)

    prob = 0.20

    if mejora >= 3:
        prob += 0.25
    elif mejora >= 1:
        prob += 0.15

    if edad <= 23:
        prob += 0.15
    elif edad >= 30:
        prob -= 0.10

    if factor_uso >= 6:
        prob += 0.20
    elif factor_uso >= 3:
        prob += 0.10

    if factor_precio > 0.7:
        prob -= 0.20
    elif factor_precio > 0.5:
        prob -= 0.10
    elif factor_precio < 0.25:
        prob += 0.10

    prob = max(0.05, min(0.90, prob))

    if random.random() < prob:
        return ejecutar_opcion_compra(jugador, equipo_actual_cesion)

    return False, f"{equipo_actual_cesion} decide no ejecutar la opción de compra"

def reset_relaciones_primer_equipo_temporada():
    db = st.session_state.db

    for equipo, datos in db["equipos_data"].items():
        for jugador in datos["jugadores"][:]:
            if jugador.get("promocion_temporal", False):
                equipo_base = jugador.get("equipo_base")

                if equipo_base and equipo_base in db["equipos_data"] and equipo != equipo_base:
                    db["equipos_data"][equipo]["jugadores"].remove(jugador)
                    db["equipos_data"][equipo_base]["jugadores"].append(jugador)
                    jugador["equipo_actual"] = equipo_base
                    jugador["propietario"] = equipo_base

                jugador["promocion_temporal"] = False
                jugador["bloqueado_filial_sub19"] = False
                jugador["ficha_primer_equipo"] = False
                jugador["primer_equipo_asignado"] = None
                jugador["ficha_filial"] = False
                jugador["filial_asignado"] = None
                jugador["ultima_jornada_jugada"] = None

            elif jugador.get("ficha_primer_equipo", False) or jugador.get("ficha_filial", False):
                jugador["ficha_primer_equipo"] = False
                jugador["primer_equipo_asignado"] = None
                jugador["ficha_filial"] = False
                jugador["filial_asignado"] = None
                jugador["ultima_jornada_jugada"] = None

def devolver_cedidos():
    db = st.session_state.db

    for eq, edata in db["equipos_data"].items():
        for j in edata["jugadores"][:]:
            if not j.get("cedido", False):
                continue

            if j.get("cedido_hasta", 0) >= db["config"]["temporada"]:
                continue

            propietario = j.get("propietario", eq)

            # Solo ejecutar opción de compra automática si NO es uno de nuestros clubes
            if (
                j.get("opcion_compra", False)
                and j.get("equipo_opcion_compra") == eq
                and j.get("temporada_opcion_compra") is not None
                and db["config"]["temporada"] > j.get("temporada_opcion_compra", 0)
                and eq not in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19", "EKIPO", "EKIPO Sub-19"]  # NUEVO: excluir nuestros clubes
            ):
                ok, msg = decidir_opcion_compra_ia(j, eq)
                if ok:
                    continue
                db["mercado_log"].append(f"❌ Opción no ejecutada: {j['nombre']} sigue sin fichar por {eq}")

            # Si no se ejecutó la opción, el jugador vuelve al propietario
            if propietario != eq and propietario in db["equipos_data"]:
                db["equipos_data"][eq]["jugadores"].remove(j)
                db["equipos_data"][propietario]["jugadores"].append(j)

                registrar_traspaso(j, eq, propietario, tipo="fin cesión", valor=0)

                j["equipo_actual"] = propietario
                j["cedido"] = False
                j["cedido_hasta"] = 0
                j["opcion_compra"] = False
                j["precio_opcion_compra"] = 0
                j["equipo_opcion_compra"] = None
                j["temporada_opcion_compra"] = None

                abrir_tramo_temporada(j, propietario, "fin cesión")
                db["mercado_log"].append(f"↩️ Fin cesión: {j['nombre']} vuelve a {propietario}")

def promocionar_sub19_por_edad():
    db = st.session_state.db
    movimientos = []

    for equipo, datos in db["equipos_data"].items():
        if not es_equipo_sub19(equipo):
            continue

        jugadores = datos.get("jugadores", [])
        a_mover = [j for j in jugadores if j.get("edad", 0) >= 20]

        for jugador in a_mover:
            destino = obtener_siguiente_equipo_por_edad(equipo)
            if not destino or destino not in db["equipos_data"]:
                continue

            datos["jugadores"].remove(jugador)
            db["equipos_data"][destino]["jugadores"].append(jugador)

            jugador["equipo_actual"] = destino
            jugador["propietario"] = destino
            jugador["cedido"] = False
            jugador["cedido_hasta"] = 0

            abrir_tramo_temporada(jugador, destino, "promoción edad")
            limitar_valor_por_liga(jugador, destino)

            movimientos.append(
                f"🔼 Promoción por edad: {jugador['nombre']} pasa de {equipo} a {destino} al cumplir 20 años"
            )

    db.setdefault("mercado_log", []).extend(movimientos)
    return movimientos

def procesar_retiradas():
    db = st.session_state.db
    db.setdefault("jugadores_retirados", [])
    retirados = []

    for eq, edata in db["equipos_data"].items():
        plantilla = edata["jugadores"][:]
        for j in plantilla:
            edad = j.get("edad", 20)
            prob = 0
            if edad >= 36:
                prob = 0.5
            elif edad >= 34:
                prob = 0.2
            elif edad >= 33:
                prob = 0.08

            if prob > 0 and random.random() < prob:
                copia = copy.deepcopy(j)
                copia["ultimo_equipo"] = eq
                copia["retirado"] = True
                db["jugadores_retirados"].append(copia)

                edata["jugadores"].remove(j)
                retirados.append({
                    "temporada": db["config"]["temporada"],
                    "jugador": j["nombre"],
                    "equipo": eq,
                    "edad": edad
                })
                db["mercado_log"].append(f"🧓 Retirada: {j['nombre']} ({eq})")

    db.setdefault("historial_retiradas", [])
    db["historial_retiradas"].extend(retirados)

def crear_canteranos_temporada():
    """
    Crea los canteranos necesarios para que cada Sub-19 termine la
    temporada con exactamente 3 porteros y 7 jugadores de campo.
    Solo se ejecuta al inicio de cada nueva temporada.
    """
    db = st.session_state.db
    movimientos = []

    for eq, datos in db["equipos_data"].items():
        if not es_equipo_sub19(eq):
            continue

        plantilla = datos.get("jugadores", [])

        porteros = [j for j in plantilla if j.get("pos") == "POR"]
        jugadores_campo = [j for j in plantilla if j.get("pos") != "POR"]

        # Rellenar hasta 3 porteros
        while len(porteros) < 3:
            canterano = generar_canterano_sub19(eq, "POR")
            plantilla.append(canterano)
            porteros.append(canterano)

            # Registrar en historial de traspasos del club
            db["historial_traspasos"].append({
                "temporada": db["config"]["temporada"],
                "jugador": canterano["nombre"],
                "origen": "Cantera",
                "destino": eq,
                "tipo": "Canterano",
                "valor": None
            })

            movimientos.append(
                f"🌱 Canterano: {canterano['nombre']} (POR) sube a {eq}"
            )

        # Rellenar hasta 7 jugadores de campo
        while len(jugadores_campo) < 7:
            canterano = generar_canterano_sub19(eq, "JUG")
            plantilla.append(canterano)
            jugadores_campo.append(canterano)

            # Registrar en historial de traspasos del club
            db["historial_traspasos"].append({
                "temporada": db["config"]["temporada"],
                "jugador": canterano["nombre"],
                "origen": "Cantera",
                "destino": eq,
                "tipo": "Canterano",
                "valor": None
            })

            movimientos.append(
                f"🌱 Canterano: {canterano['nombre']} (JUG) sube a {eq}"
            )

    if movimientos:
        db.setdefault("mercado_log", []).extend(movimientos)

    return movimientos

def generar_canterano(equipo):
    nombre = f"Canterano {equipo[:4]} {random.randint(100,999)}"
    pos = "POR" if random.random() < 0.25 else "JUG"
    media = random.randint(60, 72)
    valor = random.randint(1, 5)
    return {
        "nombre": nombre, "media": media, "valor": valor, "pos": pos,
        "goles": 0, "asistencias": 0, "amarillas": 0, "rojas": 0, "partidos": 0,
        "nota_total": 0, "goles_encajados": 0, "lesion_jornadas": 0, "cansancio": 0,
        "partidos_titular": 0, "minutos_totales": 0, "edad": random.randint(16, 19),
        "retirarse_al_final": False, "cedido": False, "cedido_hasta": 0,
        "propietario": equipo, "historial_valor": [valor], "historial_media": [media],
        "historial_temporadas": [], "historial_traspasos": [], "equipo_actual": equipo
    }

def generar_canterano_sub19(equipo, pos):
    """
    Genera un canterano de 16 años para un equipo Sub-19.
    La media depende de la división del Sub-19.
    """
    db = st.session_state.db
    nombre_base = "Portero" if pos == "POR" else "Jugador"
    nombre = f"{nombre_base} Canterano {equipo[:4]} {random.randint(100, 999)}"

    # Obtener la liga/división del equipo Sub-19
    liga = db["equipos_data"].get(equipo, {}).get("liga", "")

    # Determinar rango de media según división
    if "Sub-19 1 División" in liga or "Sub-19 1ª División" in liga:
        # Liga principal: 45-55 normal, 55-60 muy raro
        if random.random() < 0.08:
            media = random.randint(55, 60)
        else:
            media = random.choices(
                range(45, 56),
                weights=[10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
            )[0]
    elif "Sub-19 2 División" in liga or "Sub-19 2ª División" in liga:
        # Liga principal: 40-45 normal, 45-50 muy raro
        if random.random() < 0.08:
            media = random.randint(45, 50)
        else:
            media = random.choices(
                range(40, 46),
                weights=[10, 9, 8, 7, 6, 5]
            )[0]
    elif "Sub-19 3 División" in liga or "Sub-19 3ª División" in liga:
        # Liga principal: 35-40 normal, 40-45 muy raro
        if random.random() < 0.08:
            media = random.randint(40, 45)
        else:
            media = random.choices(
                range(35, 41),
                weights=[10, 9, 8, 7, 6, 5]
            )[0]
    elif (
        "Com Sub-19 1 División" in liga
        or "Tengu Sub-19 1 División" in liga
        or "Folimón Sub-19 1 División" in liga
        or "Folimn Sub-19 1 División" in liga
    ):
        # Com/Tengu/Folimón: 45-50 normal, 50-55 muy raro
        if random.random() < 0.08:
            media = random.randint(50, 55)
        else:
            media = random.choices(
                range(45, 51),
                weights=[10, 9, 8, 7, 6, 5]
            )[0]
    elif (
        "Com Sub-19 2 División" in liga
        or "Tengu Sub-19 2 División" in liga
        or "Folimón Sub-19 2 División" in liga
        or "Folimn Sub-19 2 División" in liga
    ):
        # Com/Tengu/Folimón: 35-45 normal, 45-50 muy raro
        if random.random() < 0.08:
            media = random.randint(45, 50)
        else:
            media = random.choices(
                range(35, 46),
                weights=[10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
            )[0]
    else:
        # Por defecto, si no coincide con ninguna división conocida
        media = random.randint(40, 50)

    # Valor inicial bajo para canteranos
    valor = round(random.uniform(0.1, 0.6), 1)

    return {
        "nombre": nombre,
        "media": media,
        "valor": valor,
        "pos": pos,
        "goles": 0,
        "asistencias": 0,
        "amarillas": 0,
        "rojas": 0,
        "partidos": 0,
        "nota_total": 0,
        "goles_encajados": 0,
        "lesion_jornadas": 0,
        "cansancio": 0,
        "partidos_titular": 0,
        "minutos_totales": 0,
        "edad": 16,
        "retirarse_al_final": False,
        "cedido": False,
        "cedido_hasta": 0,
        "propietario": equipo,
        "historial_valor": [valor],
        "historial_media": [media],
        "historial_temporadas": [],
        "historial_traspasos": [],
        "equipo_actual": equipo
    }


def rellenar_plantillas_si_hace_falta():
    db = st.session_state.db

    for eq, edata in db["equipos_data"].items():
        if not ("Sub-19" in eq or "Sub 19" in eq):
            continue

        plantilla = edata["jugadores"]

        porteros = [j for j in plantilla if j.get("pos") == "POR"]
        jugadores_campo = [j for j in plantilla if j.get("pos") != "POR"]

        while len(porteros) < 3:
            nuevo = generar_canterano_sub19(eq, "POR")
            plantilla.append(nuevo)
            porteros.append(nuevo)

        while len(jugadores_campo) < 7:
            nuevo = generar_canterano_sub19(eq, "JUG")
            plantilla.append(nuevo)
            jugadores_campo.append(nuevo)
            
def mercado_abierto_en_jornada(jornada):
    return (1 <= jornada <= 5) or (17 <= jornada <= 22)

def mercado_automatico():
    db = st.session_state.db
    equipos = list(db["equipos_data"].keys())

    # -----------------------------------------
    # FICHAR JUGADORES LIBRES PRIMERO
    # -----------------------------------------
    libres = db.get("jugadores_libres", [])
    if libres:
        # Barajar para que no siempre fichén los mismos primero
        random.shuffle(libres)

        for libre in libres[:]:  # Copia para poder borrar mientras iteras
            jugador = libre["jugador"]
            equipo_origen = libre["equipo_origen"]

            # Buscar equipos IA que necesiten ese jugador
            candidatos_destino = []

            for destino in equipos:
                if destino in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19",
                               "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19"]:
                    continue

                plantilla_destino = db["equipos_data"][destino]["jugadores"]

                # Solo si tiene hueco (menos de 8 jugadores)
                if len(plantilla_destino) >= 8:
                    continue

                # Si necesita portero, solo mirar porteros
                num_porteros = sum(1 for j in plantilla_destino if j["pos"] == "POR")
                if jugador["pos"] == "POR" and num_porteros >= 2:
                    continue
                if jugador["pos"] != "POR" and num_porteros < 1:
                    # Si no tiene porteros, priorizar porteros antes que jugadores de campo
                    continue

                # Comprobar presupuesto
                presupuesto_destino = obtener_presupuesto_equipo(destino)
                salario = jugador.get("salario", 0)

                if salario > presupuesto_destino:
                    continue

                # Comprobar encaje (no fichar si es muy malo para el equipo)
                media_destino = media_plantilla(destino)
                if jugador["media"] < media_destino - 15:
                    continue

                # Encaje por edad en Sub-19
                if es_equipo_sub19(destino) and jugador.get("edad", 99) > 19:
                    continue

                # Prioridad según necesidad
                prioridad = 1.0
                if jugador["pos"] == "POR" and num_porteros < 2:
                    prioridad = 3.0
                elif jugador["pos"] != "POR" and len([j for j in plantilla_destino if j["pos"] == "JUG"]) < 5:
                    prioridad = 2.0

                candidatos_destino.append((destino, prioridad))

            if candidatos_destino:
                # Elegir destino con peso por prioridad
                destino_elegido, _ = random.choices(
                    candidatos_destino,
                    weights=[p for _, p in candidatos_destino],
                    k=1
                )[0]

                # Fichar al jugador
                plantilla_destino = db["equipos_data"][destino_elegido]["jugadores"]
                plantilla_destino.append(jugador)

                jugador["equipo_actual"] = destino_elegido
                jugador["propietario"] = destino_elegido
                jugador["cedido"] = False
                jugador["cedido_hasta"] = 0

                # Pagar salario
                restar_presupuesto_equipo(destino_elegido, jugador.get("salario", 0))

                # Registrar en historial
                db.setdefault("historial_traspasos", []).append({
                    "temporada": db["config"]["temporada"],
                    "jugador": jugador["nombre"],
                    "origen": equipo_origen,
                    "destino": destino_elegido,
                    "tipo": "agente libre",
                    "valor": 0
                })

                db.setdefault("mercado_log", []).append(
                    f"✅ {jugador['nombre']} ficha por {destino_elegido} "
                    f"como agente libre (salario: {formatear_valor(jugador.get('salario', 0))}/temp.)"
                )

                # Quitar de la lista de libres
                libres.remove(libre)

    # -----------------------------------------
    # MERCADO NORMAL (entre equipos)
    # -----------------------------------------
    equipos = list(db["equipos_data"].keys())

    max_operaciones = random.choice([1, 2, 2, 3])
    operaciones_hechas = 0


    for destino in equipos:
        if operaciones_hechas >= max_operaciones:
            break


        if destino in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19",
               "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19",
               "EKIPO", "EKIPO Sub-19"]:
            continue


        plantilla_destino = db["equipos_data"][destino]["jugadores"]
        num_porteros_destino = sum(1 for j in plantilla_destino if j["pos"] == "POR")
        necesita_portero = num_porteros_destino < 2


        if len(plantilla_destino) >= 8:
            continue


        # Calcular media por posición para detectar necesidades
        media_por_pos = {}
        for pos in ["POR", "JUG"]:
            jugadores_pos = [j for j in plantilla_destino if j["pos"] == pos]
            if jugadores_pos:
                media_por_pos[pos] = sum(j["media"] for j in jugadores_pos) / len(jugadores_pos)
            else:
                media_por_pos[pos] = 0


        # Detectar si necesita reforzar alguna posición (media < 65 es muy baja)
        necesita_refuerzo_jug = media_por_pos.get("JUG", 0) < 65 and len([j for j in plantilla_destino if j["pos"] == "JUG"]) < 5


        # Bonus de probabilidad según división (más mercado en divisiones bajas)
        liga_destino = db["equipos_data"][destino].get("liga", "")
        if liga_destino == "1ª División":
            bonus_division = 1.0
        elif liga_destino == "2ª División":
            bonus_division = 1.3
        elif liga_destino in ["3ª División", "3ª División Grupo A", "3ª División Grupo B"]:
            bonus_division = 1.5
        elif liga_destino == "4ª División":
            bonus_division = 1.7
        else:
            bonus_division = 1.0


        if es_equipo_sub19(destino):
            prob_base = 0.08 if (necesita_portero or necesita_refuerzo_jug) else 0.04
        else:
            prob_base = 0.55 if (necesita_portero or necesita_refuerzo_jug) else 0.18


        # Aplicar bonus de división
        prob = min(0.95, prob_base * bonus_division)


        if random.random() >= prob:
            continue


        candidatos = []
        presupuesto_destino = obtener_presupuesto_equipo(destino)


        for origen in equipos:
            if origen in ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19", "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19", "EKIPO", "EKIPO SUB-19"]:
                continue
            if origen == destino:
                continue
            if son_clubes_vinculados(origen, destino):
                continue


            if es_equipo_sub19(origen) and random.random() < 0.90:
                continue


            plantilla_origen = db["equipos_data"][origen]["jugadores"]
            num_porteros_origen = sum(1 for j in plantilla_origen if j["pos"] == "POR")


            for j in plantilla_origen:
                if j.get("cedido"):
                    continue


                # Si necesita portero, solo mirar porteros; si no, mirar cualquier posición
                if necesita_portero and j["pos"] != "POR":
                    continue


                # No sacar porteros si el origen solo tiene 1
                if j["pos"] == "POR" and num_porteros_origen <= 1:
                    continue


                # IMPORTANTE: No ceder jugadores importantes (ya existe esta función)
                if not jugador_es_vendible(origen, j):
                    continue


                if not destino_puede_ficharlo(origen, destino, j):
                    continue


                if es_equipo_sub19(destino) and j.get("edad", 99) > 19:
                    continue


                precio = calcular_precio_traspaso(j, origen, destino)


                if es_equipo_sub19(destino):
                    precio = min(precio, 1.0)


                if precio > presupuesto_destino:
                    continue


                # Prioridad según necesidad
                if j["pos"] == "POR":
                    prioridad = 2.5 if necesita_portero else 0.4
                else:
                    prioridad = 2.0 if necesita_refuerzo_jug else 1.0


                # Calcular cuánto mejora (o empeora) al equipo destino
                media_objetivo = media_plantilla(destino, j["pos"])
                if media_objetivo == 0:
                    media_objetivo = media_plantilla(destino)


                mejora_real = j["media"] - media_objetivo


                # Bonus por juventud: si es joven (≤21), se permite que empeore un poco la media
                edad = j.get("edad", 24)
                if edad <= 21:
                    # Jóvenes pueden ficharse aunque empeoren hasta 8 puntos la media
                    if mejora_real < -8:
                        continue
                elif edad <= 23:
                    # Hasta 23 años, se permite empeorar hasta 5 puntos
                    if mejora_real < -5:
                        continue
                else:
                    # Mayores de 23, solo si no empeoran o mejoran
                    if mejora_real < -3:
                        continue


                diferencia_media = abs(j["media"] - media_objetivo)
                ajuste_media = max(0.25, 1 - (diferencia_media / 10))
                ajuste_precio = max(0.3, 1 - (precio / max(1, presupuesto_destino)))
                calidad = max(0.5, j["media"] / 80)


                # Bonus por juventud y proyección (más importante que la edad exacta)
                bonus_juventud = 1.0
                if edad <= 21:
                    bonus_juventud = 1.5
                elif edad <= 23:
                    bonus_juventud = 1.25
                elif edad <= 25:
                    bonus_juventud = 1.1


                peso = prioridad * calidad * ajuste_media * ajuste_precio * bonus_juventud
                if es_equipo_sub19(destino):
                    peso *= 0.35


                candidatos.append((origen, j, precio, peso))


        if not candidatos:
            continue


        origen, jugador, precio, _ = random.choices(
            candidatos,
            weights=[x[3] for x in candidatos],
            k=1
        )[0]


        if es_equipo_sub19(destino):
            if jugador.get("edad", 99) > 19:
                continue


            precio = min(precio, 1.0)


            if random.random() < 0.85:
                precio_cesion = max(0.1, round(precio * random.uniform(0.05, 0.12), 1))
                precio_cesion = min(precio_cesion, 1.0)


                if precio_cesion <= presupuesto_destino:
                    duracion = 1
                    usar_opcion = jugador.get("edad", 99) <= 19 and random.random() < 0.55
                    precio_opcion = None


                    if usar_opcion:
                        precio_opcion = round(
                            float(jugador["valor"]) * random.uniform(0.90, 1.10),
                            1
                        )


                    ok, msg = hacer_cesion(
                        jugador["nombre"],
                        origen,
                        destino,
                        monto=precio_cesion,
                        duracion=duracion,
                        opcion_compra=usar_opcion,
                        precio_opcion_compra=precio_opcion
                    )


                    if ok:
                        operaciones_hechas += 1
                else:
                    ok, msg = hacer_traspaso(
                        jugador["nombre"],
                        origen,
                        destino,
                        monto=min(precio, 1.0)
                    )
                    if ok:
                        operaciones_hechas += 1
        else:
            # Decidir si cesión o traspaso según minutos jugados y media (no solo edad)
            edad = jugador.get("edad", 24)
            minutos = jugador.get("minutos_totales", 0)
            partidos_titular = jugador.get("partidos_titular", 0)
            media = jugador.get("media", 0)


            # Jugador que no cuenta: pocos minutos o pocos partidos titular
            no_cuenta = minutos < 200 or partidos_titular < 4


            # Joven con proyección: ≤23 años y media decente (≤80)
            es_joven_con_proyeccion = edad <= 23 and media <= 80


            # Jugador veterano que no cuenta (ej: 26+ años, pocos minutos)
            es_veterano_sin_rol = edad >= 26 and no_cuenta and media <= 78


            es_necesidad_urgente = necesita_portero or necesita_refuerzo_jug


            # Preferir cesión si: no cuenta, es joven con proyección, o es veterano sin rol
            if (no_cuenta or es_joven_con_proyeccion or es_veterano_sin_rol) and not es_necesidad_urgente and random.random() < 0.65:
                precio_cesion = max(0.2, round(precio * random.uniform(0.08, 0.15), 1))
                if precio_cesion <= presupuesto_destino:
                    duracion = random.choice([1, 1, 2])


                    # Opción de compra más probable si es joven y tiene buena media
                    usar_opcion = (edad <= 23 and media >= 70) and random.random() < 0.55
                    precio_opcion = None


                    if usar_opcion:
                        precio_opcion = round(
                            float(jugador["valor"]) * random.uniform(0.90, 1.10),
                            1
                        )


                    ok, msg = hacer_cesion(
                        jugador["nombre"],
                        origen,
                        destino,
                        monto=precio_cesion,
                        duracion=duracion,
                        opcion_compra=usar_opcion,
                        precio_opcion_compra=precio_opcion
                    )


                    if ok:
                        operaciones_hechas += 1
            else:
                # Traspaso directo para necesidades urgentes o jugadores consolidados
                ok, msg = hacer_traspaso(jugador["nombre"], origen, destino, monto=precio)
                if ok:
                    operaciones_hechas += 1

def panel_convocatoria_manual(equipo, db):
    """
    Panel Streamlit para elegir:
    - 8 jugadores de convocatoria
    - 3 titulares (1 POR + 2 JUG)
    - Cambios previstos: (minuto, quién sale, quién entra)
    Incluye jugadores con ficha (primer equipo y filial) del mismo club.
    """
    st.subheader(f"📋 Convocatoria manual - {equipo}")

    # 1) Recoger jugadores “base” del equipo
    jugadores_base = db["equipos_data"].get(equipo, {}).get("jugadores", [])

    # 2) Añadir jugadores con ficha de primer equipo de este club
    jugadores_ficha_pe = []
    if es_equipo_principal(equipo):
        # Este equipo es un primer equipo: añadir sus jugadores con ficha
        jugadores_ficha_pe = obtener_jugadores_con_ficha_primer_equipo(equipo)
    else:
        # Si es filial o Sub-19, mirar si hay jugadores con ficha de primer equipo
        # cuyo club principal sea el mismo que el de este equipo
        club_base = obtener_club_principal(equipo)
        for eq_club, data in db["equipos_data"].items():
            if obtener_club_principal(eq_club) == club_base and es_equipo_principal(eq_club):
                jugadores_ficha_pe = obtener_jugadores_con_ficha_primer_equipo(eq_club)
                break

    # 3) Añadir jugadores con ficha filial de este filial
    jugadores_ficha_filial = []
    if equipo.endswith(" B") or equipo.endswith(" C"):
        jugadores_ficha_filial = obtener_jugadores_con_ficha_filial(equipo)

    # Unir todos, evitando duplicados por nombre
    vistos = set()
    jugadores = []
    for lista in (jugadores_base, jugadores_ficha_pe, jugadores_ficha_filial):
        for j in lista:
            if j["nombre"] in vistos:
                continue
            vistos.add(j["nombre"])
            jugadores.append(j)

    if not jugadores:
        st.warning(f"No hay jugadores disponibles para {equipo}")
        return

    # 1) Seleccionar 8 jugadores de convocatoria
    nombres = [j["nombre"] for j in jugadores]
    convocados = st.multiselect(
        "Selecciona 8 jugadores para la convocatoria",
        options=nombres,
        default=nombres[:8],
        max_selections=8,
        key=f"convocatoria_{equipo}"
    )

    if len(convocados) != 8:
        st.info("Debes seleccionar exactamente 8 jugadores para continuar.")
        return

    # Filtrar datos solo de convocados
    convocados_data = [j for j in jugadores if j["nombre"] in convocados]

    # 2) Seleccionar once titular (1 POR + 2 JUG)
    porteros = [j for j in convocados_data if j["pos"] == "POR"]
    jugadores_campo = [j for j in convocados_data if j["pos"] != "POR"]

    if len(porteros) < 1:
        st.error("Necesitas al menos 1 portero en la convocatoria.")
        return
    if len(jugadores_campo) < 2:
        st.error("Necesitas al menos 2 jugadores de campo en la convocatoria.")
        return

    titular_por = st.selectbox(
        "Portero titular",
        options=[j["nombre"] for j in porteros],
        key=f"titular_por_{equipo}"
    )

    titulares_campo_nombres = st.multiselect(
        "Selecciona 2 jugadores titulares (campo)",
        options=[j["nombre"] for j in jugadores_campo],
        default=[j["nombre"] for j in jugadores_campo[:2]],
        max_selections=2,
        key=f"titulares_campo_{equipo}"
    )

    if len(titulares_campo_nombres) != 2:
        st.info("Debes seleccionar exactamente 2 jugadores de campo titulares.")
        return

    once_nombres = {titular_por} | set(titulares_campo_nombres)
    once = [j for j in convocados_data if j["nombre"] in once_nombres]
    banquillo = [j for j in convocados_data if j["nombre"] not in once_nombres]

    # 3) Cambios previstos: (minuto, quién sale, quién entra)
    st.caption("Cambios previstos (minuto aprox., titular que sale y suplente que entra)")
    cambios_previstos = []

    # Ahora TODOS los titulares (incluido el portero) pueden salir
    titulares_para_cambios = once

    for i in range(3):
        col1, col2, col3 = st.columns(3)
        with col1:
            minuto = st.number_input(
                "Minuto",
                min_value=21,
                max_value=40,
                value=21 + i * 5,
                key=f"cambio_min_{equipo}_{i}"
            )
        with col2:
            sale = st.selectbox(
                "Titular que sale",
                options=[j["nombre"] for j in titulares_para_cambios],
                key=f"cambio_sale_{equipo}_{i}"
            )
        with col3:
            # Solo mostrar suplentes de la misma posición que el que sale
            jugador_sale = next((j for j in once if j["nombre"] == sale), None)
            pos_sale = jugador_sale["pos"] if jugador_sale else "JUG"

            suplentes_misma_pos = [j["nombre"] for j in banquillo if j["pos"] == pos_sale]
            if not suplentes_misma_pos:
                st.warning(f"No hay suplentes de posición {pos_sale} en el banquillo.")
                suplentes_misma_pos = [j["nombre"] for j in banquillo]

            entra = st.selectbox(
                "Suplente que entra",
                options=suplentes_misma_pos,
                key=f"cambio_entra_{equipo}_{i}"
            )
        cambios_previstos.append({"min": minuto, "sale": sale, "entra": entra})

    # Validar que no se repita el mismo suplente en varios cambios
    suplentes_elegidos = [c["entra"] for c in cambios_previstos]
    if len(suplentes_elegidos) != len(set(suplentes_elegidos)):
        st.warning("No puedes repetir el mismo suplente en varios cambios.")
        return

    if st.button("✅ Confirmar convocatoria", key=f"confirmar_convocatoria_{equipo}"):
        st.session_state.setdefault("convocatorias_manuales", {})
        st.session_state.convocatorias_manuales[equipo] = {
            "convocatoria": convocados_data,
            "once": once,
            "banquillo": banquillo,
            "cambios_previstos": cambios_previstos
        }
        st.success(f"Convocatoria de {equipo} guardada.")

def actualizar_lesiones_jornada(jornada_actual):
    """
    Reduce las lesiones una sola vez por jornada.
    """
    db = st.session_state.db
    clave = f"lesiones_jornada_{jornada_actual}"

    # Evita reducir las mismas lesiones más de una vez
    if db.get("ultima_jornada_lesiones") == jornada_actual:
        return

    for origen in ("equipos_data", "equipos_data_sub19"):
        for equipo, datos in db.get(origen, {}).items():
            for jugador in datos.get("jugadores", []):
                lesiones = jugador.get("lesion_jornadas", 0)

                if lesiones > 0:
                    jugador["lesion_jornadas"] = max(0, lesiones - 1)

    db["ultima_jornada_lesiones"] = jornada_actual

def simular_partido(eq1, eq2, jornada_actual=None):
    db = st.session_state.db
        
    def tipo_estancia_partido(jugador, equipo_convocante):
        if jugador.get("equipo_actual") == equipo_convocante:
            return "normal"
        if jugador.get("ficha_primer_equipo", False) and jugador.get("primer_equipo_asignado") == equipo_convocante:
            return "ficha_primer_equipo"
        if jugador.get("ficha_filial", False) and jugador.get("filial_asignado") == equipo_convocante:
            return "ficha_filial"
        return "normal"
    
    data_eq1 = obtener_equipo_data(eq1)
    data_eq2 = obtener_equipo_data(eq2)

    asegurar_convocatoria_partido(eq1, eq2, jornada_actual)

    p1 = obtener_plantilla_disponible_partido(eq1, jornada_actual)
    p2 = obtener_plantilla_disponible_partido(eq2, jornada_actual)

    m1 = sum(j["media"] for j in p1) / len(p1) if p1 else 0
    m2 = sum(j["media"] for j in p2) / len(p2) if p2 else 0

    def elegir_once_y_banquillo(equipo_convocante, plantilla, rival_fuerte):
        disponibles = [x for x in plantilla if x["lesion_jornadas"] == 0]

        porteros = [x for x in disponibles if x["pos"] == "POR"]
        jugadores = [x for x in disponibles if x["pos"] != "POR"]

        titular_por = None
        if porteros:
            porteros_ordenados = sorted(
                porteros,
                key=lambda k: (
                    k["media"],
                    -k.get("partidos_titular", 0),
                    -k.get("minutos_totales", 0),
                    -k["cansancio"],
                ),
                reverse=True,
            )

            if len(porteros_ordenados) > 1:
                p0 = porteros_ordenados[0]
                p1_alt = porteros_ordenados[1]
                muy_cansado = p0["cansancio"] >= 6
                muy_usado = p0.get("partidos_titular", 0) >= 5

                if rival_fuerte:
                    prob_rotacion_por = 0.05
                    if muy_cansado:
                        prob_rotacion_por += 0.25
                else:
                    prob_rotacion_por = 0.25
                    if muy_cansado:
                        prob_rotacion_por += 0.35
                    if muy_usado:
                        prob_rotacion_por += 0.2

                prob_rotacion_por = max(0.0, min(0.9, prob_rotacion_por))

                if random.random() < prob_rotacion_por:
                    titular_por = p1_alt
                else:
                    titular_por = p0
            else:
                titular_por = porteros_ordenados[0]
        else:
            jugadores_ordenados = sorted(jugadores, key=lambda k: k["media"], reverse=True)
            titular_por = jugadores_ordenados.pop(0) if jugadores_ordenados else None
            jugadores = jugadores_ordenados

        jugadores_ordenados = []
        for j in jugadores:
            partidos_tit = j.get("partidos_titular", 0)
            mins = j.get("minutos_totales", 0)
            carga = partidos_tit + mins / 20.0

            base = j["media"] - j["cansancio"] * 2.0

            es_reserva_con_ficha = (
                j.get("ficha_primer_equipo", False)
                and j.get("primer_equipo_asignado") == equipo_convocante
                and j.get("equipo_actual") != equipo_convocante
            )

            es_reserva_filial = (
                j.get("ficha_filial", False)
                and j.get("filial_asignado") == equipo_convocante
                and j.get("equipo_actual") != equipo_convocante
            )

            penalizacion_reserva = 0.0
            if es_reserva_con_ficha:
                penalizacion_reserva += 5
            if es_reserva_filial:
                penalizacion_reserva += 4

            if rival_fuerte:
                score = base - 0.15 * carga - penalizacion_reserva * 1.2
            else:
                score = base - 0.35 * carga - penalizacion_reserva * 1.2

            j["_score_once"] = score
            jugadores_ordenados.append(j)

        jugadores_ordenados.sort(key=lambda x: x["_score_once"], reverse=True)

        titulares_campo = []
        banquillo_campo = []
        max_titulares_campo = 2

        for j in jugadores_ordenados:
            if len(titulares_campo) >= max_titulares_campo:
                banquillo_campo.append(j)
                continue

            muy_cansado = j["cansancio"] >= 7
            muy_usado = j.get("partidos_titular", 0) >= 5
            es_estrella = j["media"] >= 85

            if rival_fuerte:
                prob_rotacion = 0.05
                if muy_cansado:
                    prob_rotacion += 0.25
            else:
                prob_rotacion = 0.2
                if muy_cansado:
                    prob_rotacion += 0.4
                if muy_usado:
                    prob_rotacion += 0.2

            if es_estrella:
                prob_rotacion -= 0.1

            prob_rotacion = max(0.0, min(0.9, prob_rotacion))

            if random.random() < prob_rotacion:
                banquillo_campo.append(j)
            else:
                titulares_campo.append(j)

        while len(titulares_campo) < max_titulares_campo and banquillo_campo:
            titulares_campo.append(banquillo_campo.pop(0))

        for j in jugadores_ordenados:
            j.pop("_score_once", None)

        titulares = ([titular_por] if titular_por else []) + titulares_campo
        banquillo = [p for p in porteros if p != titular_por] + banquillo_campo

        return titulares, banquillo

    # Comprobar si hay convocatoria manual para este equipo
    convocatorias_manuales = st.session_state.get("convocatorias_manuales", {})

    usar_manual_1 = eq1 in convocatorias_manuales
    usar_manual_2 = eq2 in convocatorias_manuales

    if usar_manual_1:
        cm1 = convocatorias_manuales[eq1]
        tit1 = list(cm1["once"])
        banq1 = list(cm1["banquillo"])
        cambios_previstos_1 = cm1["cambios_previstos"]
    else:
        tit1, banq1 = elegir_once_y_banquillo(eq1, p1, m2 > m1 - 5)
        cambios_previstos_1 = None

    if usar_manual_2:
        cm2 = convocatorias_manuales[eq2]
        tit2 = list(cm2["once"])
        banq2 = list(cm2["banquillo"])
        cambios_previstos_2 = cm2["cambios_previstos"]
    else:
        tit2, banq2 = elegir_once_y_banquillo(eq2, p2, m1 > m2 - 5)
        cambios_previstos_2 = None

    c1, c2 = list(tit1), list(tit2)
    tj1, tj2 = list(tit1), list(tit2)

    entrados1, entrados2 = set(), set()
    salidos1, salidos2 = set(), set()
    minutos1, minutos2, goles_part1, goles_part2, asis_part1, asis_part2 = {}, {}, {}, {}, {}, {}
    g1, g2, evs, exp1, exp2 = 0, 0, [], [], []
    pr1 = 0.025 + ((m1 - m2) * 0.001)
    pr2 = 0.025 - ((m1 - m2) * 0.001)

    max_cambios_normales = 3
    cambio_lesion_extra_1 = False
    cambio_lesion_extra_2 = False


    def generar_plan_cambios(banquillo, max_cambios=3):
        # Queremos exactamente max_cambios cambios si hay banquillo suficiente
        suplentes_cambios = []
        intentos = 0
        while len(suplentes_cambios) < max_cambios and len(banquillo) > len(suplentes_cambios) and intentos < 50:
            intentos += 1
            candidatos = [s for s in banquillo if s not in suplentes_cambios]
            if not candidatos:
                break
            suplente = random.choice(candidatos)
            suplentes_cambios.append(suplente)

        if not suplentes_cambios:
            return []

        minutos_posibles = list(range(21, 41))
        random.shuffle(minutos_posibles)
        plan = [
            {"min": m, "jug": s}
            for s, m in zip(suplentes_cambios, minutos_posibles[:len(suplentes_cambios)])
        ]
        return plan

    # Si hay cambios previstos (convocatoria manual), usarlos; si no, generar aleatorio
    if cambios_previstos_1:
        plan_cambios1 = [
            {
                "min": c["min"],
                "sale": c["sale"],
                "entra": c["entra"],
                "jug": next(j for j in banq1 if j["nombre"] == c["entra"])
            }
            for c in cambios_previstos_1
        ]
    else:
        plan_cambios1 = generar_plan_cambios(banq1, max_cambios_normales)

    if cambios_previstos_2:
        plan_cambios2 = [
            {
                "min": c["min"],
                "sale": c["sale"],
                "entra": c["entra"],
                "jug": next(j for j in banq2 if j["nombre"] == c["entra"])
            }
            for c in cambios_previstos_2
        ]
    else:
        plan_cambios2 = generar_plan_cambios(banq2, max_cambios_normales)

    def hacer_cambios_por_minuto(plan, en_campo, entrados, salidos, equipo, banquillo, minuto, eventos, todos_jugados, minutos):
        pendientes = [p for p in plan if p["min"] == minuto]

        for p in pendientes:
            # Si el cambio es manual (tiene "sale" y "entra"), usarlo directamente
            if "sale" in p and "entra" in p:
                nombre_sale = p["sale"]
                nombre_entra = p["entra"]

                # Buscar jugadores por nombre
                sale = next((x for x in en_campo if x["nombre"] == nombre_sale), None)
                entra = next((x for x in banquillo if x["nombre"] == nombre_entra), None)

                if sale is None or entra is None:
                    # Si no están disponibles, saltar este cambio
                    continue

                # Comprobar posición (solo cambiar si misma posición)
                if sale["pos"] != entra["pos"]:
                    continue

                # Evitar repetir cambios
                if nombre_entra in entrados or nombre_sale in salidos:
                    continue

                # Aplicar cambio
                banquillo.remove(entra)
                en_campo.remove(sale)
                en_campo.append(entra)

                entrados.add(nombre_entra)
                salidos.add(nombre_sale)

                if all(x["nombre"] != nombre_entra for x in todos_jugados):
                    todos_jugados.append(entra)

                eventos.append({
                    "min": minuto,
                    "texto": f"🔄 Cambio ({equipo}): {nombre_sale} -> {nombre_entra}"
                })
                continue

            # Lógica antigua para cambios automáticos (si no hay "sale"/"entra")
            entra = p["jug"]
            nombre_entra = entra["nombre"]

            if entra not in banquillo:
                # Suplente ya no disponible: intentar otro suplente de la misma posición
                reemplazo = next((x for x in banquillo if x["pos"] == entra["pos"]), None)
                if reemplazo is not None:
                    entra = reemplazo
                    nombre_entra = entra["nombre"]
                    p["jug"] = entra
                else:
                    # No hay suplente válido: reprogramar o eliminar
                    if minuto < 40:
                        p["min"] = minuto + 1
                    else:
                        plan.remove(p)
                    continue

            if nombre_entra in entrados or nombre_entra in salidos:
                # Ya ha participado: reprogramar o eliminar
                if minuto < 40:
                    p["min"] = minuto + 1
                else:
                    plan.remove(p)
                continue

            candidatos = [
                x for x in en_campo
                if x["pos"] == entra["pos"] and x["nombre"] not in entrados
            ]

            if not candidatos:
                # Intentar otro suplente de la misma posición
                otro_suplente = next(
                    (x for x in banquillo if x["pos"] == entra["pos"] and x is not entra),
                    None
                )
                if otro_suplente is not None:
                    entra = otro_suplente
                    nombre_entra = entra["nombre"]
                    p["jug"] = entra
                    candidatos = [
                        x for x in en_campo
                        if x["pos"] == entra["pos"] and x["nombre"] not in entrados
                    ]

            if not candidatos:
                # No hay nadie de esa posición que pueda salir: reprogramar o eliminar
                if minuto < 40:
                    p["min"] = minuto + 1
                else:
                    plan.remove(p)
                continue

            sale = max(candidatos, key=lambda x: minutos.get(x["nombre"], 0))
            nombre_sale = sale["nombre"]

            banquillo.remove(entra)
            en_campo.remove(sale)
            en_campo.append(entra)

            entrados.add(nombre_entra)
            salidos.add(nombre_sale)

            if all(x["nombre"] != nombre_entra for x in todos_jugados):
                todos_jugados.append(entra)

            plan.remove(p)

            eventos.append({
                "min": minuto,
                "texto": f"🔄 Cambio ({equipo}): {sale['nombre']} -> {entra['nombre']}"
            })

    def forzar_cambios_extra(en_campo, banquillo, entrados, salidos, equipo, eventos, todos_jugados, minutos, max_cambios=3, minuto_base=40):
        # Forzar cambios hasta llegar a max_cambios si es necesario
        while len(entrados) < max_cambios and banquillo:
            # Buscar suplente disponible (no portero si no hay porteros en banquillo)
            suplente = None
            for s in banquillo:
                if s["nombre"] not in entrados:
                    # Si el suplente es portero, solo puede entrar si hay otro portero en el campo que pueda salir
                    if s["pos"] == "POR":
                        # Buscar portero titular que pueda salir
                        porteros_campo = [x for x in en_campo if x["pos"] == "POR" and x["nombre"] not in entrados]
                        if porteros_campo:
                            suplente = s
                            break
                    else:
                        suplente = s
                        break
            
            if not suplente:
                break
            
            # Buscar titular de la misma posición que pueda salir
            candidatos_salida = [
                x for x in en_campo
                if x["pos"] == suplente["pos"] and x["nombre"] not in entrados
            ]
            
            if not candidatos_salida:
                # No hay nadie de esa posición: probar con otro suplente
                banquillo.remove(suplente)
                continue
            
            sale = max(candidatos_salida, key=lambda x: minutos.get(x["nombre"], 0))

            banquillo.remove(suplente)
            en_campo.remove(sale)
            en_campo.append(suplente)

            entrados.add(suplente["nombre"])
            salidos.add(sale["nombre"])

            if all(x["nombre"] != suplente["nombre"] for x in todos_jugados):
                todos_jugados.append(suplente)

            eventos.append({
                "min": minuto_base,
                "texto": f"🔄 Cambio extra ({equipo}): {sale['nombre']} -> {suplente['nombre']}"
            })


    def elegir_goleador(lista):
        if not lista:
            return None
        pesos = []
        for p in lista:
            base = max(0.2, p["media"] / 100)
            if p["pos"] == "POR":
                base *= 0.05
                if random.random() < 0.02:
                    base *= 8
            pesos.append(base)
        return random.choices(lista, weights=pesos, k=1)[0]


    for mn in range(1, 41):
        hacer_cambios_por_minuto(
            plan_cambios1,
            c1,
            entrados1,
            salidos1,
            eq1,
            banq1,
            mn,
            evs,
            tj1,
            minutos1
        )


        hacer_cambios_por_minuto(
            plan_cambios2,
            c2,
            entrados2,
            salidos2,
            eq2,
            banq2,
            mn,
            evs,
            tj2,
            minutos2
        )

        # Al llegar al minuto 40, forzar cambios si algún equipo no ha hecho 3
        if mn == 40:
            forzar_cambios_extra(c1, banq1, entrados1, salidos1, eq1, evs, tj1, minutos1, 3, minuto_base=40)
            forzar_cambios_extra(c2, banq2, entrados2, salidos2, eq2, evs, tj2, minutos2, 3, minuto_base=40)


        if random.random() < 0.003:
            eq_lesionado = eq1 if random.random() < 0.5 else eq2
            campo = c1 if eq_lesionado == eq1 else c2
            banq = banq1 if eq_lesionado == eq1 else banq2
            usados = tj1 if eq_lesionado == eq1 else tj2

            if campo:
                lesionado = random.choice(campo)
                dur = random.randint(1, 4)
                lesionado["lesion_jornadas"] = dur
                evs.append({
                    "min": mn,
                    "texto": f"🚑 LESIÓN: {lesionado['nombre']} ({eq_lesionado}) - baja {dur} partido(s)"
                })
                campo.remove(lesionado)

                sustituto = None
                if banq:
                    sustituto = next(
                        (x for x in banq if x["pos"] == lesionado["pos"]),
                        None
                    )
                    if sustituto:
                        banq.remove(sustituto)

                puede_entrar = False

                if eq_lesionado == eq1:
                    # Si aún no se han hecho 3 cambios, usar uno normal
                    if len(entrados1) < 3:
                        puede_entrar = True
                    # Si ya hay 3 cambios hechos, permitir un 4º solo por lesión
                    elif len(entrados1) == 3 and not cambio_lesion_extra_1:
                        cambio_lesion_extra_1 = True
                        puede_entrar = True
                else:
                    if len(entrados2) < 3:
                        puede_entrar = True
                    elif len(entrados2) == 3 and not cambio_lesion_extra_2:
                        cambio_lesion_extra_2 = True
                        puede_entrar = True

            
                if sustituto and puede_entrar:
                    campo.append(sustituto)

                    if all(x["nombre"] != sustituto["nombre"] for x in usados):
                        usados.append(sustituto)

                    # Añadir a entrados para que cuente como cambio hecho
                    if eq_lesionado == eq1:
                        entrados1.add(sustituto["nombre"])
                    else:
                        entrados2.add(sustituto["nombre"])

                    evs.append({
                        "min": mn,
                        "texto": f"🔄 SUST ({eq_lesionado}): Entra {sustituto['nombre']}"
                    })
                else:
                    evs.append({
                        "min": mn,
                        "texto": f"⚠️ {eq_lesionado} juega con uno menos"
                    })


        f1 = 0.5 if exp1 else 1.0
        f2 = 0.5 if exp2 else 1.0
        portero_actual_2 = next((x for x in c2 if x["pos"] == "POR"), None)
        portero_actual_1 = next((x for x in c1 if x["pos"] == "POR"), None)


        if c1 and random.random() < pr1 * f1:
            g1 += 1
            gl = elegir_goleador(c1)
            if gl:
                nombre = gl["nombre"]
                goles_part1[nombre] = goles_part1.get(nombre, 0) + 1
                candidatos = [x for x in c1 if x != gl and x["pos"] != "POR"]
                if candidatos and random.random() < 0.85:
                    asis = random.choice(candidatos)
                    nom_a = asis["nombre"]
                    asis_part1[nom_a] = asis_part1.get(nom_a, 0) + 1
                    evs.append({
                        "min": mn,
                        "texto": f"🅰️ Asistencia de {asis['nombre']} ({eq1})"
                    })
                evs.append({
                    "min": mn,
                    "texto": f"⚽ GOL {gl['nombre']} ({eq1})"
                })
            if portero_actual_2:
                portero_actual_2["goles_encajados"] += 1
                # Actualizar también el tramo de temporada del portero
                tipo_estancia_p2 = tipo_estancia_partido(portero_actual_2, eq2)
                tramo_p2 = abrir_tramo_temporada(portero_actual_2, eq2, tipo_estancia_p2)
                tramo_p2["goles_encajados"] += 1


        if c2 and random.random() < pr2 * f2:
            g2 += 1
            gl = elegir_goleador(c2)
            if gl:
                nombre = gl["nombre"]
                goles_part2[nombre] = goles_part2.get(nombre, 0) + 1
                candidatos = [x for x in c2 if x != gl and x["pos"] != "POR"]
                if candidatos and random.random() < 0.85:
                    asis = random.choice(candidatos)
                    nom_a = asis["nombre"]
                    asis_part2[nom_a] = asis_part2.get(nom_a, 0) + 1
                    evs.append({
                        "min": mn,
                        "texto": f"🅰️ Asistencia de {asis['nombre']} ({eq2})"
                    })
                evs.append({
                    "min": mn,
                    "texto": f"⚽️ GOL {gl['nombre']} ({eq2})"
                })
            if portero_actual_1:
                portero_actual_1["goles_encajados"] += 1
                # Actualizar también el tramo de temporada del portero
                tipo_estancia_p1 = tipo_estancia_partido(portero_actual_1, eq1)
                tramo_p1 = abrir_tramo_temporada(portero_actual_1, eq1, tipo_estancia_p1)
                tramo_p1["goles_encajados"] += 1

        if random.random() < 0.005:
            tg = (
                random.choice(c1)
                if c1 and random.random() < 0.5
                else (random.choice(c2) if c2 else None)
            )
            if tg:
                tg["amarillas"] += 1
                evs.append({
                    "min": mn,
                    "texto": f"🟨 Amarilla {tg['nombre']}"
                })


        if random.random() < 0.0015:
            es_eq1 = random.random() < 0.5
            cr = c1 if es_eq1 else c2
            er = exp1 if es_eq1 else exp2
            if cr:
                rj = random.choice(cr)
                if not (rj["pos"] == "POR" and sum(1 for x in cr if x["pos"] == "POR") <= 1):
                    rj["rojas"] += 1
                    cr.remove(rj)
                    er.append({"j": rj, "t": mn + 5})
                    evs.append({
                        "min": mn,
                        "texto": f"🟥 ROJA {rj['nombre']} (5 min fuera)"
                    })


        for e in exp1[:]:
            if mn >= e["t"]:
                c1.append(e["j"])
                exp1.remove(e)
                evs.append({
                    "min": mn,
                    "texto": f"↩️ Vuelve {e['j']['nombre']}"
                })
        for e in exp2[:]:
            if mn >= e["t"]:
                c2.append(e["j"])
                exp2.remove(e)
                evs.append({
                    "min": mn,
                    "texto": f"↩️ Vuelve {e['j']['nombre']}"
                })


        for j in c1:
            minutos1[j["nombre"]] = minutos1.get(j["nombre"], 0) + 1
            j["cansancio"] = min(10, j.get("cansancio", 0) + 0.08)
        for j in c2:
            minutos2[j["nombre"]] = minutos2.get(j["nombre"], 0) + 1
            j["cansancio"] = min(10, j.get("cansancio", 0) + 0.08)


    notas = []
    tit1_nombres = {j["nombre"] for j in tit1}
    for j in {x["nombre"]: x for x in tj1}.values():
        nombre = j["nombre"]
        mins = minutos1.get(nombre, 0)
        if mins <= 0:
            continue


        equipo_stats = equipo_en_el_que_juega_hoy(j, eq1)
        tipo_estancia = tipo_estancia_partido(j, eq1)
        tramo = abrir_tramo_temporada(j, equipo_stats, tipo_estancia, competicion="Liga")


        j["partidos"] += 1
        tramo["partidos"] += 1


        j["minutos_totales"] += mins
        tramo["minutos"] += mins


        if nombre in tit1_nombres:
            j["partidos_titular"] += 1
            tramo["partidos_titular"] += 1


        g_part = goles_part1.get(nombre, 0)
        a_part = asis_part1.get(nombre, 0)


        j["goles"] += g_part
        tramo["goles"] += g_part


        j["asistencias"] += a_part
        tramo["asistencias"] += a_part

        nota = random.uniform(6.0, 8.3)


        tipo_estancia = tipo_estancia_partido(j, eq1 if nombre in tit1_nombres else eq2)
        if tipo_estancia in ("ficha_primer_equipo", "ficha_filial"):
            penal_media = max(0, (80 - j["media"]) / 40.0)
            nota -= (0.6 + penal_media)


        if g_part > 0:
            nota += 1.2 + 0.2 * (g_part - 1)
        if a_part > 0:
            nota += 0.4


        nota_minima_garantizada = 5.0
        if g_part >= 2:
            nota_minima_garantizada = 8.0
        elif g_part == 1 and a_part >= 1:
            nota_minima_garantizada = 8.0
        elif g_part == 1:
            nota_minima_garantizada = 7.0
        elif a_part >= 2:
            nota_minima_garantizada = 7.0
        elif a_part == 1:
            nota_minima_garantizada = 6.5


        nota = max(nota, nota_minima_garantizada)


        if mins < 10 and g_part == 0 and a_part == 0:
            nota = min(nota, 7.0)
        nota = round(max(3, min(10, nota)), 1)


        j["nota_total"] += nota
        tramo["nota_total"] += nota


        update_valor_temporada(j)


        notas.append({
            "Jugador": nombre,
            "Equipo": equipo_stats,
            "Minutos": mins,
            "Nota": nota,
            "Goles": g_part,
            "Asistencias": a_part
        })


    tit2_nombres = {j["nombre"] for j in tit2}
    for j in {x["nombre"]: x for x in tj2}.values():
        nombre = j["nombre"]
        mins = minutos2.get(nombre, 0)
        if mins <= 0:
            continue


        equipo_stats = equipo_en_el_que_juega_hoy(j, eq2)
        tipo_estancia = tipo_estancia_partido(j, eq2)
        tramo = abrir_tramo_temporada(j, equipo_stats, tipo_estancia, competicion="Liga")


        j["partidos"] += 1
        tramo["partidos"] += 1


        j["minutos_totales"] += mins
        tramo["minutos"] += mins


        if nombre in tit2_nombres:
            j["partidos_titular"] += 1
            tramo["partidos_titular"] += 1


        g_part = goles_part2.get(nombre, 0)
        a_part = asis_part2.get(nombre, 0)


        j["goles"] += g_part
        tramo["goles"] += g_part


        j["asistencias"] += a_part
        tramo["asistencias"] += a_part
        
        nota = random.uniform(6.0, 8.3)


        tipo_estancia = tipo_estancia_partido(j, eq1 if nombre in tit1_nombres else eq2)
        if tipo_estancia in ("ficha_primer_equipo", "ficha_filial"):
            penal_media = max(0, (80 - j["media"]) / 40.0)
            nota -= (0.6 + penal_media)


        if g_part > 0:
            nota += 1.2 + 0.2 * (g_part - 1)
        if a_part > 0:
            nota += 0.4


        nota_minima_garantizada = 5.0
        if g_part >= 2:
            nota_minima_garantizada = 8.0
        elif g_part == 1 and a_part >= 1:
            nota_minima_garantizada = 8.0
        elif g_part == 1:
            nota_minima_garantizada = 7.0
        elif a_part >= 2:
            nota_minima_garantizada = 7.0
        elif a_part == 1:
            nota_minima_garantizada = 6.5


        nota = max(nota, nota_minima_garantizada)


        if mins < 10 and g_part == 0 and a_part == 0:
            nota = min(nota, 7.0)
        nota = round(max(3, min(10, nota)), 1)


        j["nota_total"] += nota
        tramo["nota_total"] += nota


        update_valor_temporada(j)


        notas.append({
            "Jugador": nombre,
            "Equipo": equipo_stats,
            "Minutos": mins,
            "Nota": nota,
            "Goles": g_part,
            "Asistencias": a_part
        })

    def formatear_once(lista):
        return ", ".join([f"{x['nombre']} ({x['pos']})" for x in lista])


    jugadores_utilizados_1 = [j for j in tj1 if minutos1.get(j["nombre"], 0) > 0]
    jugadores_utilizados_2 = [j for j in tj2 if minutos2.get(j["nombre"], 0) > 0]


    marcar_jugadores_como_usados_en_jornada(jugadores_utilizados_1, jornada_actual)
    marcar_jugadores_como_usados_en_jornada(jugadores_utilizados_2, jornada_actual)


    return {
        "local": eq1,
        "visitante": eq2,
        "goles1": g1,
        "goles2": g2,
        "eventos": evs,
        "notas_partido": notas,
        "alineacion1": formatear_once(tit1),
        "alineacion2": formatear_once(tit2),
        "jornada_num": 0,
    }

def simular_partido_copa_interno(eq1, eq2, competicion="Copa"):
    db = st.session_state.db
        
    def tipo_estancia_partido(jugador, equipo_convocante):
        if jugador.get("equipo_actual") == equipo_convocante:
            return "normal"
        if jugador.get("ficha_primer_equipo", False) and jugador.get("primer_equipo_asignado") == equipo_convocante:
            return "ficha_primer_equipo"
        if jugador.get("ficha_filial", False) and jugador.get("filial_asignado") == equipo_convocante:
            return "ficha_filial"
        return "normal"
    
    data_eq1 = obtener_equipo_data(eq1)
    data_eq2 = obtener_equipo_data(eq2)

    asegurar_convocatoria_partido(eq1, eq2, jornada_actual=None)

    p1 = obtener_plantilla_disponible_partido(eq1, jornada_actual=None)
    p2 = obtener_plantilla_disponible_partido(eq2, jornada_actual=None)

    m1 = sum(j["media"] for j in p1) / len(p1) if p1 else 0
    m2 = sum(j["media"] for j in p2) / len(p2) if p2 else 0

    def elegir_once_y_banquillo(equipo_convocante, plantilla, rival_fuerte):
        disponibles = [x for x in plantilla if x["lesion_jornadas"] == 0]

        porteros = [x for x in disponibles if x["pos"] == "POR"]
        jugadores = [x for x in disponibles if x["pos"] != "POR"]

        titular_por = None
        if porteros:
            porteros_ordenados = sorted(
                porteros,
                key=lambda k: (
                    k["media"],
                    -k.get("partidos_titular", 0),
                    -k.get("minutos_totales", 0),
                    -k["cansancio"],
                ),
                reverse=True,
            )

            if len(porteros_ordenados) > 1:
                p0 = porteros_ordenados[0]
                p1_alt = porteros_ordenados[1]
                muy_cansado = p0["cansancio"] >= 6
                muy_usado = p0.get("partidos_titular", 0) >= 5

                if rival_fuerte:
                    prob_rotacion_por = 0.05
                    if muy_cansado:
                        prob_rotacion_por += 0.25
                else:
                    prob_rotacion_por = 0.25
                    if muy_cansado:
                        prob_rotacion_por += 0.35
                    if muy_usado:
                        prob_rotacion_por += 0.2

                prob_rotacion_por = max(0.0, min(0.9, prob_rotacion_por))

                if random.random() < prob_rotacion_por:
                    titular_por = p1_alt
                else:
                    titular_por = p0
            else:
                titular_por = porteros_ordenados[0]
        else:
            jugadores_ordenados = sorted(jugadores, key=lambda k: k["media"], reverse=True)
            titular_por = jugadores_ordenados.pop(0) if jugadores_ordenados else None
            jugadores = jugadores_ordenados

        jugadores_ordenados = []
        for j in jugadores:
            partidos_tit = j.get("partidos_titular", 0)
            mins = j.get("minutos_totales", 0)
            carga = partidos_tit + mins / 20.0

            base = j["media"] - j["cansancio"] * 2.0

            es_reserva_con_ficha = (
                j.get("ficha_primer_equipo", False)
                and j.get("primer_equipo_asignado") == equipo_convocante
                and j.get("equipo_actual") != equipo_convocante
            )

            es_reserva_filial = (
                j.get("ficha_filial", False)
                and j.get("filial_asignado") == equipo_convocante
                and j.get("equipo_actual") != equipo_convocante
            )

            penalizacion_reserva = 0.0
            if es_reserva_con_ficha:
                penalizacion_reserva += 5
            if es_reserva_filial:
                penalizacion_reserva += 4

            if rival_fuerte:
                score = base - 0.15 * carga - penalizacion_reserva * 1.2
            else:
                score = base - 0.35 * carga - penalizacion_reserva * 1.2

            j["_score_once"] = score
            jugadores_ordenados.append(j)

        jugadores_ordenados.sort(key=lambda x: x["_score_once"], reverse=True)

        titulares_campo = []
        banquillo_campo = []
        max_titulares_campo = 2

        for j in jugadores_ordenados:
            if len(titulares_campo) >= max_titulares_campo:
                banquillo_campo.append(j)
                continue

            muy_cansado = j["cansancio"] >= 7
            muy_usado = j.get("partidos_titular", 0) >= 5
            es_estrella = j["media"] >= 85

            if rival_fuerte:
                prob_rotacion = 0.05
                if muy_cansado:
                    prob_rotacion += 0.25
            else:
                prob_rotacion = 0.2
                if muy_cansado:
                    prob_rotacion += 0.4
                if muy_usado:
                    prob_rotacion += 0.2

            if es_estrella:
                prob_rotacion -= 0.1

            prob_rotacion = max(0.0, min(0.9, prob_rotacion))

            if random.random() < prob_rotacion:
                banquillo_campo.append(j)
            else:
                titulares_campo.append(j)

        while len(titulares_campo) < max_titulares_campo and banquillo_campo:
            titulares_campo.append(banquillo_campo.pop(0))

        for j in jugadores_ordenados:
            j.pop("_score_once", None)

        titulares = ([titular_por] if titular_por else []) + titulares_campo
        banquillo = [p for p in porteros if p != titular_por] + banquillo_campo

        return titulares, banquillo

    # Comprobar si hay convocatoria manual para este equipo
    convocatorias_manuales = st.session_state.get("convocatorias_manuales", {})

    usar_manual_1 = eq1 in convocatorias_manuales
    usar_manual_2 = eq2 in convocatorias_manuales

    if usar_manual_1:
        cm1 = convocatorias_manuales[eq1]
        tit1 = list(cm1["once"])
        banq1 = list(cm1["banquillo"])
        cambios_previstos_1 = cm1["cambios_previstos"]
    else:
        tit1, banq1 = elegir_once_y_banquillo(eq1, p1, m2 > m1 - 5)
        cambios_previstos_1 = None

    if usar_manual_2:
        cm2 = convocatorias_manuales[eq2]
        tit2 = list(cm2["once"])
        banq2 = list(cm2["banquillo"])
        cambios_previstos_2 = cm2["cambios_previstos"]
    else:
        tit2, banq2 = elegir_once_y_banquillo(eq2, p2, m1 > m2 - 5)
        cambios_previstos_2 = None

    c1, c2 = list(tit1), list(tit2)
    tj1, tj2 = list(tit1), list(tit2)

    entrados1, entrados2 = set(), set()
    salidos1, salidos2 = set(), set()
    minutos1, minutos2, goles_part1, goles_part2, asis_part1, asis_part2 = {}, {}, {}, {}, {}, {}
    g1, g2, evs, exp1, exp2 = 0, 0, [], [], []
    pr1 = 0.025 + ((m1 - m2) * 0.001)
    pr2 = 0.025 - ((m1 - m2) * 0.001)

    max_cambios_normales = 3
    cambio_lesion_extra_1 = False
    cambio_lesion_extra_2 = False


    def generar_plan_cambios(banquillo, max_cambios=3):
        # Queremos exactamente max_cambios cambios si hay banquillo suficiente
        suplentes_cambios = []
        intentos = 0
        while len(suplentes_cambios) < max_cambios and len(banquillo) > len(suplentes_cambios) and intentos < 50:
            intentos += 1
            candidatos = [s for s in banquillo if s not in suplentes_cambios]
            if not candidatos:
                break
            suplente = random.choice(candidatos)
            suplentes_cambios.append(suplente)

        if not suplentes_cambios:
            return []

        minutos_posibles = list(range(21, 41))
        random.shuffle(minutos_posibles)
        plan = [
            {"min": m, "jug": s}
            for s, m in zip(suplentes_cambios, minutos_posibles[:len(suplentes_cambios)])
        ]
        return plan

    # Si hay cambios previstos (convocatoria manual), usarlos; si no, generar aleatorio
    if cambios_previstos_1:
        plan_cambios1 = [
            {
                "min": c["min"],
                "sale": c["sale"],
                "entra": c["entra"],
                "jug": next(j for j in banq1 if j["nombre"] == c["entra"])
            }
            for c in cambios_previstos_1
        ]
    else:
        plan_cambios1 = generar_plan_cambios(banq1, max_cambios_normales)

    if cambios_previstos_2:
        plan_cambios2 = [
            {
                "min": c["min"],
                "sale": c["sale"],
                "entra": c["entra"],
                "jug": next(j for j in banq2 if j["nombre"] == c["entra"])
            }
            for c in cambios_previstos_2
        ]
    else:
        plan_cambios2 = generar_plan_cambios(banq2, max_cambios_normales)

    def hacer_cambios_por_minuto(plan, en_campo, entrados, salidos, equipo, banquillo, minuto, eventos, todos_jugados, minutos):
        pendientes = [p for p in plan if p["min"] == minuto]

        for p in pendientes:
            # Si el cambio es manual (tiene "sale" y "entra"), usarlo directamente
            if "sale" in p and "entra" in p:
                nombre_sale = p["sale"]
                nombre_entra = p["entra"]

                # Buscar jugadores por nombre
                sale = next((x for x in en_campo if x["nombre"] == nombre_sale), None)
                entra = next((x for x in banquillo if x["nombre"] == nombre_entra), None)

                if sale is None or entra is None:
                    # Si no están disponibles, saltar este cambio
                    continue

                # Comprobar posición (solo cambiar si misma posición)
                if sale["pos"] != entra["pos"]:
                    continue

                # Evitar repetir cambios
                if nombre_entra in entrados or nombre_sale in salidos:
                    continue

                # Aplicar cambio
                banquillo.remove(entra)
                en_campo.remove(sale)
                en_campo.append(entra)

                entrados.add(nombre_entra)
                salidos.add(nombre_sale)

                if all(x["nombre"] != nombre_entra for x in todos_jugados):
                    todos_jugados.append(entra)

                eventos.append({
                    "min": minuto,
                    "texto": f"🔄 Cambio ({equipo}): {nombre_sale} -> {nombre_entra}"
                })
                continue

            # Lógica antigua para cambios automáticos (si no hay "sale"/"entra")
            entra = p["jug"]
            nombre_entra = entra["nombre"]

            if entra not in banquillo:
                # Suplente ya no disponible: intentar otro suplente de la misma posición
                reemplazo = next((x for x in banquillo if x["pos"] == entra["pos"]), None)
                if reemplazo is not None:
                    entra = reemplazo
                    nombre_entra = entra["nombre"]
                    p["jug"] = entra
                else:
                    # No hay suplente válido: reprogramar o eliminar
                    if minuto < 40:
                        p["min"] = minuto + 1
                    else:
                        plan.remove(p)
                    continue

            if nombre_entra in entrados or nombre_entra in salidos:
                # Ya ha participado: reprogramar o eliminar
                if minuto < 40:
                    p["min"] = minuto + 1
                else:
                    plan.remove(p)
                continue

            candidatos = [
                x for x in en_campo
                if x["pos"] == entra["pos"] and x["nombre"] not in entrados
            ]

            if not candidatos:
                # Intentar otro suplente de la misma posición
                otro_suplente = next(
                    (x for x in banquillo if x["pos"] == entra["pos"] and x is not entra),
                    None
                )
                if otro_suplente is not None:
                    entra = otro_suplente
                    nombre_entra = entra["nombre"]
                    p["jug"] = entra
                    candidatos = [
                        x for x in en_campo
                        if x["pos"] == entra["pos"] and x["nombre"] not in entrados
                    ]

            if not candidatos:
                # No hay nadie de esa posición que pueda salir: reprogramar o eliminar
                if minuto < 40:
                    p["min"] = minuto + 1
                else:
                    plan.remove(p)
                continue

            sale = max(candidatos, key=lambda x: minutos.get(x["nombre"], 0))
            nombre_sale = sale["nombre"]

            banquillo.remove(entra)
            en_campo.remove(sale)
            en_campo.append(entra)

            entrados.add(nombre_entra)
            salidos.add(nombre_sale)

            if all(x["nombre"] != nombre_entra for x in todos_jugados):
                todos_jugados.append(entra)

            plan.remove(p)

            eventos.append({
                "min": minuto,
                "texto": f"🔄 Cambio ({equipo}): {sale['nombre']} -> {entra['nombre']}"
            })

    def forzar_cambios_extra(en_campo, banquillo, entrados, salidos, equipo, eventos, todos_jugados, minutos, max_cambios=3, minuto_base=40):
        # Forzar cambios hasta llegar a max_cambios si es necesario
        while len(entrados) < max_cambios and banquillo:
            # Buscar suplente disponible (no portero si no hay porteros en banquillo)
            suplente = None
            for s in banquillo:
                if s["nombre"] not in entrados:
                    # Si el suplente es portero, solo puede entrar si hay otro portero en el campo que pueda salir
                    if s["pos"] == "POR":
                        # Buscar portero titular que pueda salir
                        porteros_campo = [x for x in en_campo if x["pos"] == "POR" and x["nombre"] not in entrados]
                        if porteros_campo:
                            suplente = s
                            break
                    else:
                        suplente = s
                        break
            
            if not suplente:
                break
            
            # Buscar titular de la misma posición que pueda salir
            candidatos_salida = [
                x for x in en_campo
                if x["pos"] == suplente["pos"] and x["nombre"] not in entrados
            ]
            
            if not candidatos_salida:
                # No hay nadie de esa posición: probar con otro suplente
                banquillo.remove(suplente)
                continue
            
            sale = max(candidatos_salida, key=lambda x: minutos.get(x["nombre"], 0))

            banquillo.remove(suplente)
            en_campo.remove(sale)
            en_campo.append(suplente)

            entrados.add(suplente["nombre"])
            salidos.add(sale["nombre"])

            if all(x["nombre"] != suplente["nombre"] for x in todos_jugados):
                todos_jugados.append(suplente)

            eventos.append({
                "min": minuto_base,
                "texto": f"🔄 Cambio extra ({equipo}): {sale['nombre']} -> {suplente['nombre']}"
            })


    def elegir_goleador(lista):
        if not lista:
            return None
        pesos = []
        for p in lista:
            base = max(0.2, p["media"] / 100)
            if p["pos"] == "POR":
                base *= 0.05
                if random.random() < 0.02:
                    base *= 8
            pesos.append(base)
        return random.choices(lista, weights=pesos, k=1)[0]


    for mn in range(1, 41):
        hacer_cambios_por_minuto(
            plan_cambios1,
            c1,
            entrados1,
            salidos1,
            eq1,
            banq1,
            mn,
            evs,
            tj1,
            minutos1
        )


        hacer_cambios_por_minuto(
            plan_cambios2,
            c2,
            entrados2,
            salidos2,
            eq2,
            banq2,
            mn,
            evs,
            tj2,
            minutos2
        )

        # Al llegar al minuto 40, forzar cambios si algún equipo no ha hecho 3
        if mn == 40:
            forzar_cambios_extra(c1, banq1, entrados1, salidos1, eq1, evs, tj1, minutos1, 3, minuto_base=40)
            forzar_cambios_extra(c2, banq2, entrados2, salidos2, eq2, evs, tj2, minutos2, 3, minuto_base=40)


        if random.random() < 0.003:
            eq_lesionado = eq1 if random.random() < 0.5 else eq2
            campo = c1 if eq_lesionado == eq1 else c2
            banq = banq1 if eq_lesionado == eq1 else banq2
            usados = tj1 if eq_lesionado == eq1 else tj2

            if campo:
                lesionado = random.choice(campo)
                dur = random.randint(1, 4)
                lesionado["lesion_jornadas"] = dur
                evs.append({
                    "min": mn,
                    "texto": f"🚑 LESIÓN: {lesionado['nombre']} ({eq_lesionado}) - baja {dur} partido(s)"
                })
                campo.remove(lesionado)

                sustituto = None
                if banq:
                    sustituto = next(
                        (x for x in banq if x["pos"] == lesionado["pos"]),
                        None
                    )
                    if sustituto:
                        banq.remove(sustituto)

                puede_entrar = False

                if eq_lesionado == eq1:
                    # Si aún no se han hecho 3 cambios, usar uno normal
                    if len(entrados1) < 3:
                        puede_entrar = True
                    # Si ya hay 3 cambios hechos, permitir un 4º solo por lesión
                    elif len(entrados1) == 3 and not cambio_lesion_extra_1:
                        cambio_lesion_extra_1 = True
                        puede_entrar = True
                else:
                    if len(entrados2) < 3:
                        puede_entrar = True
                    elif len(entrados2) == 3 and not cambio_lesion_extra_2:
                        cambio_lesion_extra_2 = True
                        puede_entrar = True

            
                if sustituto and puede_entrar:
                    campo.append(sustituto)

                    if all(x["nombre"] != sustituto["nombre"] for x in usados):
                        usados.append(sustituto)

                    # Añadir a entrados para que cuente como cambio hecho
                    if eq_lesionado == eq1:
                        entrados1.add(sustituto["nombre"])
                    else:
                        entrados2.add(sustituto["nombre"])

                    evs.append({
                        "min": mn,
                        "texto": f"🔄 SUST ({eq_lesionado}): Entra {sustituto['nombre']}"
                    })
                else:
                    evs.append({
                        "min": mn,
                        "texto": f"⚠️ {eq_lesionado} juega con uno menos"
                    })


        f1 = 0.5 if exp1 else 1.0
        f2 = 0.5 if exp2 else 1.0
        portero_actual_2 = next((x for x in c2 if x["pos"] == "POR"), None)
        portero_actual_1 = next((x for x in c1 if x["pos"] == "POR"), None)


        if c1 and random.random() < pr1 * f1:
            g1 += 1
            gl = elegir_goleador(c1)
            if gl:
                nombre = gl["nombre"]
                goles_part1[nombre] = goles_part1.get(nombre, 0) + 1
                candidatos = [x for x in c1 if x != gl and x["pos"] != "POR"]
                if candidatos and random.random() < 0.85:
                    asis = random.choice(candidatos)
                    nom_a = asis["nombre"]
                    asis_part1[nom_a] = asis_part1.get(nom_a, 0) + 1
                    evs.append({
                        "min": mn,
                        "texto": f"🅰️ Asistencia de {asis['nombre']} ({eq1})"
                    })
                evs.append({
                    "min": mn,
                    "texto": f"⚽ GOL {gl['nombre']} ({eq1})"
                })
            if portero_actual_2:
                portero_actual_2["goles_encajados"] += 1
                # Actualizar también el tramo de temporada del portero
                tipo_estancia_p2 = tipo_estancia_partido(portero_actual_2, eq2)
                tramo_p2 = abrir_tramo_temporada(
                    portero_actual_2,
                    eq2,
                    tipo_estancia_p2,
                    competicion=competicion,
                )
                tramo_p2["goles_encajados"] += 1


        if c2 and random.random() < pr2 * f2:
            g2 += 1
            gl = elegir_goleador(c2)
            if gl:
                nombre = gl["nombre"]
                goles_part2[nombre] = goles_part2.get(nombre, 0) + 1
                candidatos = [x for x in c2 if x != gl and x["pos"] != "POR"]
                if candidatos and random.random() < 0.85:
                    asis = random.choice(candidatos)
                    nom_a = asis["nombre"]
                    asis_part2[nom_a] = asis_part2.get(nom_a, 0) + 1
                    evs.append({
                        "min": mn,
                        "texto": f"🅰️ Asistencia de {asis['nombre']} ({eq2})"
                    })
                evs.append({
                    "min": mn,
                    "texto": f"⚽️ GOL {gl['nombre']} ({eq2})"
                })
            if portero_actual_1:
                portero_actual_1["goles_encajados"] += 1
                # Actualizar también el tramo de temporada del portero
                tipo_estancia_p1 = tipo_estancia_partido(portero_actual_1, eq1)
                tramo_p1 = abrir_tramo_temporada(
                    portero_actual_1,
                    eq1,
                    tipo_estancia_p1,
                    competicion=competicion,
                )
                tramo_p1["goles_encajados"] += 1

        if random.random() < 0.005:
            tg = (
                random.choice(c1)
                if c1 and random.random() < 0.5
                else (random.choice(c2) if c2 else None)
            )
            if tg:
                tg["amarillas"] += 1
                evs.append({
                    "min": mn,
                    "texto": f"🟨 Amarilla {tg['nombre']}"
                })


        if random.random() < 0.0015:
            es_eq1 = random.random() < 0.5
            cr = c1 if es_eq1 else c2
            er = exp1 if es_eq1 else exp2
            if cr:
                rj = random.choice(cr)
                if not (rj["pos"] == "POR" and sum(1 for x in cr if x["pos"] == "POR") <= 1):
                    rj["rojas"] += 1
                    cr.remove(rj)
                    er.append({"j": rj, "t": mn + 5})
                    evs.append({
                        "min": mn,
                        "texto": f"🟥 ROJA {rj['nombre']} (5 min fuera)"
                    })


        for e in exp1[:]:
            if mn >= e["t"]:
                c1.append(e["j"])
                exp1.remove(e)
                evs.append({
                    "min": mn,
                    "texto": f"↩️ Vuelve {e['j']['nombre']}"
                })
        for e in exp2[:]:
            if mn >= e["t"]:
                c2.append(e["j"])
                exp2.remove(e)
                evs.append({
                    "min": mn,
                    "texto": f"↩️ Vuelve {e['j']['nombre']}"
                })


        for j in c1:
            minutos1[j["nombre"]] = minutos1.get(j["nombre"], 0) + 1
            j["cansancio"] = min(10, j.get("cansancio", 0) + 0.08)
        for j in c2:
            minutos2[j["nombre"]] = minutos2.get(j["nombre"], 0) + 1
            j["cansancio"] = min(10, j.get("cansancio", 0) + 0.08)


    notas = []
    tit1_nombres = {j["nombre"] for j in tit1}
    for j in {x["nombre"]: x for x in tj1}.values():
        nombre = j["nombre"]
        mins = minutos1.get(nombre, 0)
        if mins <= 0:
            continue


        equipo_stats = equipo_en_el_que_juega_hoy(j, eq1)
        tipo_estancia = tipo_estancia_partido(j, eq1)
        tramo = abrir_tramo_temporada(j, equipo_stats, tipo_estancia, competicion=competicion)


        j["partidos"] += 1
        tramo["partidos"] += 1


        j["minutos_totales"] += mins
        tramo["minutos"] += mins


        if nombre in tit1_nombres:
            j["partidos_titular"] += 1
            tramo["partidos_titular"] += 1


        g_part = goles_part1.get(nombre, 0)
        a_part = asis_part1.get(nombre, 0)


        j["goles"] += g_part
        tramo["goles"] += g_part


        j["asistencias"] += a_part
        tramo["asistencias"] += a_part

        nota = random.uniform(6.0, 8.3)


        tipo_estancia = tipo_estancia_partido(j, eq1 if nombre in tit1_nombres else eq2)
        if tipo_estancia in ("ficha_primer_equipo", "ficha_filial"):
            penal_media = max(0, (80 - j["media"]) / 40.0)
            nota -= (0.6 + penal_media)


        if g_part > 0:
            nota += 1.2 + 0.2 * (g_part - 1)
        if a_part > 0:
            nota += 0.4


        nota_minima_garantizada = 5.0
        if g_part >= 2:
            nota_minima_garantizada = 8.0
        elif g_part == 1 and a_part >= 1:
            nota_minima_garantizada = 8.0
        elif g_part == 1:
            nota_minima_garantizada = 7.0
        elif a_part >= 2:
            nota_minima_garantizada = 7.0
        elif a_part == 1:
            nota_minima_garantizada = 6.5


        nota = max(nota, nota_minima_garantizada)


        if mins < 10 and g_part == 0 and a_part == 0:
            nota = min(nota, 7.0)
        nota = round(max(3, min(10, nota)), 1)


        j["nota_total"] += nota
        tramo["nota_total"] += nota

        notas.append({
            "Jugador": nombre,
            "Equipo": equipo_stats,
            "Minutos": mins,
            "Nota": nota,
            "Goles": g_part,
            "Asistencias": a_part,
        })


    tit2_nombres = {j["nombre"] for j in tit2}
    for j in {x["nombre"]: x for x in tj2}.values():
        nombre = j["nombre"]
        mins = minutos2.get(nombre, 0)
        if mins <= 0:
            continue


        equipo_stats = equipo_en_el_que_juega_hoy(j, eq2)
        tipo_estancia = tipo_estancia_partido(j, eq2)
        tramo = abrir_tramo_temporada(j, equipo_stats, tipo_estancia, competicion=competicion)


        j["partidos"] += 1
        tramo["partidos"] += 1


        j["minutos_totales"] += mins
        tramo["minutos"] += mins


        if nombre in tit2_nombres:
            j["partidos_titular"] += 1
            tramo["partidos_titular"] += 1


        g_part = goles_part2.get(nombre, 0)
        a_part = asis_part2.get(nombre, 0)


        j["goles"] += g_part
        tramo["goles"] += g_part


        j["asistencias"] += a_part
        tramo["asistencias"] += a_part
        
        nota = random.uniform(6.0, 8.3)


        tipo_estancia = tipo_estancia_partido(j, eq1 if nombre in tit1_nombres else eq2)
        if tipo_estancia in ("ficha_primer_equipo", "ficha_filial"):
            penal_media = max(0, (80 - j["media"]) / 40.0)
            nota -= (0.6 + penal_media)


        if g_part > 0:
            nota += 1.2 + 0.2 * (g_part - 1)
        if a_part > 0:
            nota += 0.4


        nota_minima_garantizada = 5.0
        if g_part >= 2:
            nota_minima_garantizada = 8.0
        elif g_part == 1 and a_part >= 1:
            nota_minima_garantizada = 8.0
        elif g_part == 1:
            nota_minima_garantizada = 7.0
        elif a_part >= 2:
            nota_minima_garantizada = 7.0
        elif a_part == 1:
            nota_minima_garantizada = 6.5


        nota = max(nota, nota_minima_garantizada)


        if mins < 10 and g_part == 0 and a_part == 0:
            nota = min(nota, 7.0)
        nota = round(max(3, min(10, nota)), 1)


        j["nota_total"] += nota
        tramo["nota_total"] += nota


        update_valor_temporada(j)

        notas.append({
            "Jugador": nombre,
            "Equipo": equipo_stats,
            "Minutos": mins,
            "Nota": nota,
            "Goles": g_part,
            "Asistencias": a_part,
        })

    def formatear_once(lista):
        return ", ".join([f"{x['nombre']} ({x['pos']})" for x in lista])


    jugadores_utilizados_1 = [j for j in tj1 if minutos1.get(j["nombre"], 0) > 0]
    jugadores_utilizados_2 = [j for j in tj2 if minutos2.get(j["nombre"], 0) > 0]


    marcar_jugadores_como_usados_en_jornada(jugadores_utilizados_1, jornada_actual=None)
    marcar_jugadores_como_usados_en_jornada(jugadores_utilizados_2, jornada_actual=None)


    return {
        "local": eq1,
        "visitante": eq2,
        "goles1": g1,
        "goles2": g2,
        "eventos": evs,
        "notas_partido": notas,
        "alineacion1": formatear_once(tit1),
        "alineacion2": formatear_once(tit2),
        "jornada_num": 0,
    }

def perfil_jugador(nombre_jugador):
    db = st.session_state.db

    for base in [db["equipos_data"], db.get("equipos_data_sub19", {})]:
        for eq, edata in base.items():
            for j in edata["jugadores"]:
                if j["nombre"] == nombre_jugador:
                    media_actual = round(j["nota_total"] / j["partidos"], 2) if j["partidos"] > 0 else 0
                    actual = {
                        "posicion": j["pos"],
                        "equipo_actual": j.get("equipo_actual", eq),
                        "media_actual": media_actual,
                        "partidos": j["partidos"],
                        "goles": j["goles"],
                        "asistencias": j["asistencias"],
                        "amarillas": j["amarillas"],
                        "rojas": j["rojas"],
                        "partidos_titular": j["partidos_titular"],
                        "minutos_totales": j["minutos_totales"],
                        "media_global": j["media"],
                        "edad": j["edad"],
                        "valor": j["valor"],
                        "encajados": j["goles_encajados"],
                        "retirado": False
                    }
                    return j, actual

    # Buscar en jugadores libres (agentes libres)
    for libre in db.get("jugadores_libres", []):
        j = libre["jugador"]
        if j["nombre"] == nombre_jugador:
            actual = {
                "posicion": j["pos"],
                "equipo_actual": "Agente libre",
                "media_actual": 0,
                "partidos": 0,
                "goles": 0,
                "asistencias": 0,
                "amarillas": 0,
                "rojas": 0,
                "partidos_titular": 0,
                "minutos_totales": 0,
                "media_global": j["media"],
                "edad": j["edad"],
                "valor": j["valor"],
                "encajados": 0,
                "retirado": False
            }
            return j, actual

    for j in db.get("jugadores_retirados", []):
        if j["nombre"] == nombre_jugador:
            actual = {
                "posicion": j["pos"],
                "equipo_actual": j.get("ultimo_equipo", "Retirado"),
                "media_actual": 0,
                "partidos": j.get("partidos", 0),
                "goles": j.get("goles", 0),
                "asistencias": j.get("asistencias", 0),
                "amarillas": j.get("amarillas", 0),
                "rojas": j.get("rojas", 0),
                "partidos_titular": j.get("partidos_titular", 0),
                "minutos_totales": j.get("minutos_totales", 0),
                "media_global": j["media"],
                "edad": j["edad"],
                "valor": j["valor"],
                "encajados": j.get("goles_encajados", 0),
                "retirado": True
            }
            return j, actual

    return None, None

def equipo_stats_tabla(eq):
    equipo_data = obtener_equipo_data(eq)
    filas = []
    temporada_actual = st.session_state.db["config"]["temporada"]

    jugadores_equipo = list(equipo_data["jugadores"])

    if es_equipo_principal(eq):
        jugadores_equipo += obtener_jugadores_con_ficha_primer_equipo(eq)
    elif (eq.endswith(" B") or eq.endswith(" C")) and "obtener_jugadores_con_ficha_filial" in globals():
        jugadores_equipo += obtener_jugadores_con_ficha_filial(eq)

    vistos = set()

    for j in jugadores_equipo:
        clave = (j["nombre"], eq, temporada_actual)
        if clave in vistos:
            continue
        vistos.add(clave)

        # Determinar tipo_estancia según si tiene ficha
        if j.get("ficha_primer_equipo", False) and j.get("primer_equipo_asignado") == eq:
            tipo_estancia = "ficha_primer_equipo"
        elif j.get("ficha_filial", False) and j.get("filial_asignado") == eq:
            tipo_estancia = "ficha_filial"
        else:
            tipo_estancia = "normal"

        tramo = abrir_tramo_temporada(j, eq, tipo_estancia)

        filas.append({
            "Nombre": f"{''.join(j.get('banderas', []))} {j['nombre']}",
            "Pos": j["pos"],
            "Edad": j["edad"],
            "Media": j["media"],
            "Valor": formatear_valor(j["valor"]),
            "ValorNum": j["valor"],
            "PJ": tramo.get("partidos", 0),
            "Titular": tramo.get("partidos_titular", 0),
            "Minutos": tramo.get("minutos", 0),
            "Goles": tramo.get("goles", 0),
            "Asistencias": tramo.get("asistencias", 0),
            "Amarillas": tramo.get("amarillas", 0),
            "Rojas": tramo.get("rojas", 0),
            "Encajados": tramo.get("goles_encajados", 0),
            "Minuto/Goles": round(tramo.get("minutos", 0) / tramo.get("goles_encajados", 1), 2) if tramo.get("goles_encajados", 0) > 0 else 0,
            "Lesión": j["lesion_jornadas"],
            "Cansancio": round(j["cansancio"], 2),
            "Nota": round(tramo.get("nota_total", 0) / tramo.get("partidos", 0), 2) if tramo.get("partidos", 0) > 0 else 0,
            "Salario": formatear_valor(j.get("salario", 0)),
            "Fin contrato": j.get("fin_contrato", "-"),
        })

    return pd.DataFrame(filas)


def todos_los_jugadores_de_liga(liga_activa):
    filas = []
    temporada_actual = st.session_state.db["config"]["temporada"]

    liga_data = obtener_liga_data(liga_activa)
    equipos_liga = liga_data["equipos"]

    vistos = set()

    for eq in equipos_liga:
        equipo_data = obtener_equipo_data(eq)
        jugadores_equipo = list(equipo_data["jugadores"])

        if es_equipo_principal(eq):
            jugadores_equipo += obtener_jugadores_con_ficha_primer_equipo(eq)
        elif (eq.endswith(" B") or eq.endswith(" C")) and "obtener_jugadores_con_ficha_filial" in globals():
            jugadores_equipo += obtener_jugadores_con_ficha_filial(eq)

        for j in jugadores_equipo:
            clave = (j["nombre"], eq, temporada_actual)
            if clave in vistos:
                continue
            vistos.add(clave)

            # Determinar tipo_estancia según si tiene ficha
            if j.get("ficha_primer_equipo", False) and j.get("primer_equipo_asignado") == eq:
                tipo_estancia = "ficha_primer_equipo"
            elif j.get("ficha_filial", False) and j.get("filial_asignado") == eq:
                tipo_estancia = "ficha_filial"
            else:
                tipo_estancia = "normal"

            tramo = abrir_tramo_temporada(j, eq, tipo_estancia)
            banderas = j.get("banderas", [])

            filas.append({
                "Nombre": f"{''.join(banderas)} {j['nombre']}",
                "Nacionalidad": "".join(banderas) if banderas else "🏳️",
                "Equipo": eq,
                "Pos": j["pos"],
                "Edad": j["edad"],
                "Media": j["media"],
                "Valor": formatear_valor(j["valor"]),
                "ValorNum": j["valor"],
                "PJ": tramo.get("partidos", 0),
                "Titular": tramo.get("partidos_titular", 0),
                "Minutos": tramo.get("minutos", 0),
                "Goles": tramo.get("goles", 0),
                "Asistencias": tramo.get("asistencias", 0),
                "Amarillas": tramo.get("amarillas", 0),
                "Rojas": tramo.get("rojas", 0),
                "Encajados": tramo.get("goles_encajados", 0),
                "Lesión": j["lesion_jornadas"],
                "Cansancio": round(j["cansancio"], 2),
                "Nota": round(tramo.get("nota_total", 0) / tramo.get("partidos", 0), 2) if tramo.get("partidos", 0) > 0 else 0,
            })

    # Añadir agentes libres (jugadores_libres)
    for libre in st.session_state.db.get("jugadores_libres", []):
        j = libre["jugador"]
        clave = (j["nombre"], "Sin equipo", temporada_actual)
        if clave in vistos:
            continue
        vistos.add(clave)

        banderas = j.get("banderas", [])

        filas.append({
            "Nombre": f"{''.join(banderas)} {j['nombre']}",
            "Nacionalidad": "".join(banderas) if banderas else "🏳️",
            "Equipo": "Sin equipo",
            "Pos": j["pos"],
            "Edad": j["edad"],
            "Media": j["media"],
            "Valor": formatear_valor(j["valor"]),
            "ValorNum": j["valor"],
            "PJ": 0,
            "Titular": 0,
            "Minutos": 0,
            "Goles": 0,
            "Asistencias": 0,
            "Amarillas": 0,
            "Rojas": 0,
            "Encajados": 0,
            "Lesión": 0,
            "Cansancio": 0,
            "Nota": 0,
        })

    return pd.DataFrame(filas)

def todos_los_jugadores_de_copa(pais=None, categoria=None, todas=False):
    db = st.session_state.db
    copas = db.get("copas", {})
    equipos_data = db.get("equipos_data", {})


    stats = {}
    def crear_registro(nombre, equipo, posicion="JUG", copa="-"):
        return {
            "Nombre": nombre,
            "Equipo": equipo,
            "Pos": posicion,
            "Goles": 0,
            "Asistencias": 0,
            "PJ": 0,
            "Minutos": 0,
            "Nota": 0.0,
            "Notas_contadas": 0,
            "Encajados": 0,
            "Copa": copa,
        }


    def obtener_datos_jugador(nombre, equipo):
        """
        Busca el jugador en:
        - El equipo principal
        - Equipos vinculados (filiales B, C)
        - Sub-19 del mismo club
        Así funciona con jugadores de ficha primer equipo y ficha filial.
        """
        nombre_limpio = str(nombre).strip()


        # 1. Buscar en el equipo directo
        datos_equipo = equipos_data.get(equipo, {})
        jugadores = datos_equipo.get("jugadores", [])


        for jugador in jugadores:
            nombre_jugador = str(jugador.get("nombre", "")).strip()
            if nombre_jugador == nombre_limpio:
                return jugador


        # 2. Si no está, buscar en equipos vinculados del mismo club
        club_base = obtener_club_principal(equipo)


        for eq, edata in equipos_data.items():
            if obtener_club_principal(eq) != club_base:
                continue


            for jugador in edata.get("jugadores", []):
                nombre_jugador = str(jugador.get("nombre", "")).strip()


                if nombre_jugador == nombre_limpio:
                    return jugador


        # 3. Si sigue sin encontrarse, devolver vacío
        return {}


    def normalizar_nombre(nombre):
        return str(nombre).strip()


    if todas:
        paises = ["Principal", "Com", "Tengu", "Folimón"]
        categorias = ["senior", "sub19"]
    else:
        paises = [pais] if pais else []
        categorias = [categoria] if categoria else []


    for pais_c in paises:
        for cat_c in categorias:
            competicion = copas.get(pais_c, {}).get(cat_c)


            if not competicion:
                continue


            nombre_copa = f"{pais_c} {cat_c.capitalize()}"


            for ronda in competicion.get("eliminatorias", []):
                for cruce in ronda.get("cruces", []):
                    resultado = cruce.get("resultado")


                    if resultado is None:
                        continue


                    local = cruce.get("local", "")
                    visitante = cruce.get("visitante", "")


                    equipos_partido = [
                        (local, cruce.get("alineacionlocal", "")),
                        (visitante, cruce.get("alineacionvisitante", "")),
                    ]


                    # Registrar los 3 jugadores de cada equipo
                    for equipo, alineacion in equipos_partido:
                        jugadores_partido = []


                        if isinstance(alineacion, str):
                            jugadores_partido = [
                                parte.strip()
                                for parte in alineacion.split(",")
                                if parte.strip()
                            ]
                        elif isinstance(alineacion, list):
                            jugadores_partido = alineacion


                        for jugador_alineacion in jugadores_partido:
                            if isinstance(jugador_alineacion, dict):
                                nombre = jugador_alineacion.get("nombre", "")
                                posicion = jugador_alineacion.get("pos", "JUG")
                            else:
                                texto_jugador = str(jugador_alineacion).strip()


                                if "(" in texto_jugador and ")" in texto_jugador:
                                    nombre = texto_jugador.rsplit("(", 1)[0].strip()
                                    posicion = texto_jugador.rsplit("(", 1)[1].split(")", 1)[0].strip()
                                else:
                                    nombre = texto_jugador
                                    posicion = "JUG"


                            nombre = normalizar_nombre(nombre)


                            if not nombre:
                                continue


                            datos_jugador = obtener_datos_jugador(nombre, equipo)
                            posicion_real = datos_jugador.get("pos", posicion)


                            if posicion_real:
                                posicion_real = str(posicion_real).upper()


                            if nombre not in stats:
                                stats[nombre] = crear_registro(
                                    nombre=nombre,
                                    equipo=equipo,
                                    posicion=posicion_real,
                                    copa=nombre_copa,
                                )


                            stats[nombre]["Equipo"] = equipo
                            stats[nombre]["Pos"] = posicion_real
                            stats[nombre]["PJ"] += 1


                    # Leer estadísticas desde las notas
                    notas = cruce.get("notas", [])


                    for nota in notas:
                        nombre = nota.get("Jugador", "")
                        nombre = normalizar_nombre(nombre)


                        if not nombre:
                            continue


                        equipo_nota = nota.get("Equipo", "")


                        if not equipo_nota or equipo_nota == "-":
                            for equipo, alineacion in equipos_partido:
                                if nombre in str(alineacion):
                                    equipo_nota = equipo
                                    break


                        if not equipo_nota:
                            equipo_nota = "-"


                        datos_jugador = obtener_datos_jugador(nombre, equipo_nota)
                        posicion = datos_jugador.get("pos", "JUG")
                        posicion = str(posicion).upper()


                        if nombre not in stats:
                            stats[nombre] = crear_registro(
                                nombre=nombre,
                                equipo=equipo_nota,
                                posicion=posicion,
                                copa=nombre_copa,
                            )


                        if stats[nombre]["PJ"] == 0:
                            stats[nombre]["PJ"] = 1


                        if stats[nombre]["Equipo"] == "-":
                            stats[nombre]["Equipo"] = equipo_nota


                        if stats[nombre]["Pos"] == "JUG" and posicion != "JUG":
                            stats[nombre]["Pos"] = posicion


                        stats[nombre]["Minutos"] += nota.get("Minutos", 0)
                        stats[nombre]["Nota"] += nota.get("Nota", 0)
                        stats[nombre]["Notas_contadas"] += 1
                        stats[nombre]["Goles"] += nota.get("Goles", 0)
                        stats[nombre]["Asistencias"] += nota.get("Asistencias", 0)


                    # Calcular encajados para porteros desde los goles del rival
                    # (por si las notas no tienen "Encajados")
                    for equipo, _ in equipos_partido:
                        datos_jugador = obtener_datos_jugador("PORTERO", equipo)
                        # Esto no funciona así, hay que hacerlo desde las notas


                    # Eventos para goles y asistencias
                    for evento in cruce.get("eventos", []):
                        texto = str(evento.get("texto", ""))


                        if "GOL" in texto:
                            try:
                                nombre = texto.split("GOL", 1)[1]
                                nombre = nombre.split("(", 1)[0].strip()
                            except Exception:
                                nombre = ""


                            if nombre:
                                for equipo, alineacion in equipos_partido:
                                    if nombre in str(alineacion):
                                        if nombre not in stats:
                                            datos_jugador = obtener_datos_jugador(nombre, equipo)
                                            stats[nombre] = crear_registro(
                                                nombre,
                                                equipo,
                                                str(datos_jugador.get("pos", "JUG")).upper(),
                                                nombre_copa,
                                            )
                                        stats[nombre]["Goles"] += 1
                                        break


                        if "Asistencia de" in texto:
                            try:
                                nombre = texto.split("Asistencia de", 1)[1]
                                nombre = nombre.split("(", 1)[0].strip()
                            except Exception:
                                nombre = ""


                            if nombre:
                                for equipo, alineacion in equipos_partido:
                                    if nombre in str(alineacion):
                                        if nombre not in stats:
                                            datos_jugador = obtener_datos_jugador(nombre, equipo)
                                            stats[nombre] = crear_registro(
                                                nombre,
                                                equipo,
                                                str(datos_jugador.get("pos", "JUG")).upper(),
                                                nombre_copa,
                                            )
                                        stats[nombre]["Asistencias"] += 1
                                        break


    if not stats:
        return pd.DataFrame()


    for datos in stats.values():
        if datos["Notas_contadas"] > 0:
            datos["Nota"] = round(
                datos["Nota"] / datos["Notas_contadas"],
                2,
            )
        else:
            datos["Nota"] = 0.0


    for datos in stats.values():
        if datos["Pos"] == "POR":
            jugador = obtener_datos_jugador(datos["Nombre"], datos["Equipo"])
            datos["Encajados"] = jugador.get("goles_encajados", 0)
        else:
            datos["Encajados"] = 0


    df = pd.DataFrame(list(stats.values()))


    columnas_numericas = [
        "Goles",
        "Asistencias",
        "PJ",
        "Minutos",
        "Nota",
        "Encajados",
        "ValorNum",
    ]


    for columna in columnas_numericas:
        if columna not in df.columns:
            df[columna] = 0


    df["ValorNum"] = df["Goles"] * 2 + df["Asistencias"]


    return df

def historial_jugador_df(jugador):
    hist = jugador.get("historial_temporadas", [])
    if not hist:
        return pd.DataFrame()

    df = pd.DataFrame(hist).copy()

    if "media_final" not in df.columns:
        df["media_final"] = None
    if "valor_final" not in df.columns:
        df["valor_final"] = None
    if "tipo_estancia" not in df.columns:
        df["tipo_estancia"] = "normal"
    if "division" not in df.columns:
        df["division"] = ""

    # AÑADIR: media actual del jugador en todas las filas
    df["media"] = jugador.get("media", 0)

    columnas_numericas = [
        "nota_total",
        "partidos",
        "partidos_titular",
        "minutos",
        "goles",
        "asistencias",
        "amarillas",
        "rojas",
        "goles_encajados",
    ]

    for columna in columnas_numericas:
        if columna not in df.columns:
            df[columna] = 0

        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce"
        ).fillna(0)

    if "media_partidos" not in df.columns:
        df["media_partidos"] = 0.0

    df["media_partidos"] = pd.to_numeric(
        df["media_partidos"],
        errors="coerce"
    ).fillna(0)

    df["media_partidos"] = df.apply(
        lambda fila: (
            fila["media_partidos"]
            if fila["media_partidos"] != 0
            else round(
                fila["nota_total"] / fila["partidos"],
                2
            )
            if fila["partidos"] > 0
            else 0
        ),
        axis=1
    )

    # Ocultar solamente los tramos técnicos vacíos...
    tipos_movimiento = {
        "traspaso",
        "cesion",
        "cesión",
        "fin cesion",
        "fin cesión",
        "promoción primer equipo",
    }

    tipo_es_movimiento = (
        df["tipo_estancia"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(tipos_movimiento)
    )

    fila_movimiento_vacia = (
        tipo_es_movimiento
        & (df["partidos"] == 0)
        & (df["partidos_titular"] == 0)
        & (df["minutos"] == 0)
        & (df["goles"] == 0)
        & (df["asistencias"] == 0)
        & (df["amarillas"] == 0)
        & (df["rojas"] == 0)
        & (df["goles_encajados"] == 0)
    )

    df = df.loc[~fila_movimiento_vacia].copy()

    if df.empty:
        return pd.DataFrame()

    if "temporada" in df.columns:
        df = df.sort_values("temporada", ascending=True)
        df["media_inicial"] = df["media_final"].shift(1)
        df["media_inicial"] = df["media_inicial"].fillna(df["media_final"])
        df = df.sort_values("temporada", ascending=False)

    orden = [
        "temporada",
        "equipo",
        "division",
        "tipo_estancia",
        "media",  # <-- AÑADIDA: media actual del jugador
        "media_partidos",
        "media_inicial",
        "valor_final",
        "partidos",
        "partidos_titular",
        "minutos",
        "goles",
        "asistencias",
        "amarillas",
        "rojas",
        "goles_encajados",
    ]

    columnas_mostrar = [
        columna for columna in orden
        if columna in df.columns
    ]

    return df[columnas_mostrar]

def descontar_salarios_temporada(db):
    """
    Descuenta del presupuesto de cada club el salario anual
    de sus jugadores al comenzar una nueva temporada.


    Los Sub-19 los paga el primer equipo mediante
    obtener_equipo_pagador().
    """
    db.setdefault("mercado_log", [])
    db.setdefault("movimientos_presupuesto", [])

    # Evita cobrar dos veces si se pulsa algo o se recarga.
    temporada_actual = db["config"]["temporada"]
    clave_cobro = f"salarios_pagados_temporada_{temporada_actual}"

    if db.get(clave_cobro, False):
        return []

    gastos_por_equipo = {}

    for equipo, datos_equipo in db["equipos_data"].items():
        for jugador in datos_equipo.get("jugadores", []):
            # Los cedidos los paga el club donde juegan actualmente.
            # Los demás, el equipo en el que están.
            equipo_pagador = obtener_equipo_pagador(equipo)

            salario = float(jugador.get("salario", 0))
            gastos_por_equipo[equipo_pagador] = (
                gastos_por_equipo.get(equipo_pagador, 0) + salario
            )

    movimientos = []

    for equipo_pagador, gasto_total in gastos_por_equipo.items():
        if equipo_pagador not in db["equipos_data"]:
            continue

        presupuesto_antes = float(
            db["equipos_data"][equipo_pagador].get("presupuesto", 0)
        )

        # Se descuenta lo que haya; el presupuesto nunca queda negativo.
        restar_presupuesto_equipo(equipo_pagador, gasto_total)

        presupuesto_despues = float(
            db["equipos_data"][equipo_pagador].get("presupuesto", 0)
        )

        texto = (
            f"💰 {equipo_pagador} paga "
            f"{formatear_valor(gasto_total)} en salarios "
            f"(presupuesto: {formatear_valor(presupuesto_antes)} → "
            f"{formatear_valor(presupuesto_despues)})"
        )

        # Registrar en movimientos de presupuesto
        db["movimientos_presupuesto"].append({
            "equipo": equipo_pagador,
            "temporada": temporada_actual,
            "tipo": "gasto",
            "concepto": "Salarios de la temporada",
            "importe": round(gasto_total, 3)
        })

        movimientos.append(texto)

    db["mercado_log"].extend(movimientos)
    db[clave_cobro] = True

    return movimientos

def panel_renovaciones_manuales(equipo, db):
    """
    Panel para renovar manualmente jugadores de un club del usuario
    cuyo contrato termina esta temporada.
    """
    temporada_actual = db["config"]["temporada"]
    datos_equipo = db["equipos_data"].get(equipo)

    if not datos_equipo:
        return

    plantilla = datos_equipo.get("jugadores", [])

    if not plantilla:
        return

    jugadores_vencidos = [
        j for j in plantilla
        if j.get("fin_contrato") == temporada_actual
    ]

    if not jugadores_vencidos:
        st.info(f"{equipo}: no hay jugadores con contrato vencido en T{temporada_actual}")
        return

    st.caption(f"{equipo}: {len(jugadores_vencidos)} jugadores con contrato vencido en T{temporada_actual}")

    for jugador in jugadores_vencidos:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

        with col1:
            st.write(
                f"**{jugador['nombre']}** "
                f"({jugador.get('pos', 'JUG')}, "
                f"media={jugador.get('media', 0)}, "
                f"edad={jugador.get('edad', 20)})"
            )

        with col2:
            salario_actual = jugador.get("salario", 0)
            st.write(f"Salario actual: {formatear_valor(salario_actual)}/temp.")

        with col3:
            nuevo_salario = st.number_input(
                "Nuevo salario (M€)",
                min_value=0.0,
                max_value=50.0,
                value=float(salario_actual),
                step=0.1,
                key=f"renov_sal_{equipo}_{jugador['nombre']}"
            )

        with col4:
            duracion = st.number_input(
                "Duración (temp.)",
                min_value=1,
                max_value=5,
                value=2,
                step=1,
                key=f"renov_dur_{equipo}_{jugador['nombre']}"
            )

        col_btn1, col_btn2 = st.columns([2, 1])

        with col_btn1:
            if st.button(
                "Renovar",
                key=f"btn_renovar_{equipo}_{jugador['nombre']}",
                type="primary"
            ):
                jugador["salario"] = nuevo_salario
                jugador["fin_contrato"] = temporada_actual + duracion - 1

                db.setdefault("mercado_log", []).append(
                    f"📝 {equipo} renueva manualmente a {jugador['nombre']} "
                    f"hasta T{jugador['fin_contrato']} "
                    f"({duracion} temp., "
                    f"{formatear_valor(nuevo_salario)}/temp.)"
                )
                st.success(f"{jugador['nombre']} renovado hasta T{jugador['fin_contrato']}")
                st.rerun()

        with col_btn2:
            if st.button(
                "Dejar libre",
                key=f"btn_liberar_{equipo}_{jugador['nombre']}"
            ):
                # No hace nada aquí: al cerrar temporada, liberar_jugadores_sin_contrato()
                # lo dejará libre automáticamente.
                st.info(f"{jugador['nombre']} quedará libre al cerrar la temporada.")
                
def renovar_contratos_ia():
    db = st.session_state.db
    temporada_actual = db["config"]["temporada"]

    clubes_usuario = {
        "CEREZAS",
        "CEREZAS B",
        "CEREZAS Sub-19",
        "RB Zerkas",
        "RB Zerkas B",
        "RB Zerkas Sub-19",
        "EKIPO",
        "EKIPO Sub-19",
    }

    db.setdefault("mercado_log", [])
    renovaciones = []

    num_equipos = 0
    num_jugadores_vencidos = 0

    for equipo, datos_equipo in db["equipos_data"].items():
        num_equipos += 1

        if equipo in clubes_usuario:
            continue

        plantilla = datos_equipo.get("jugadores", [])

        if not plantilla:
            continue

        es_sub19 = es_equipo_sub19(equipo)
        equipo_pagador = obtener_equipo_pagador(equipo)

        if equipo_pagador not in db["equipos_data"]:
            continue

        presupuesto = float(
            db["equipos_data"][equipo_pagador].get("presupuesto", 0)
        )

        jugadores_vencidos = [
            j["nombre"]
            for j in plantilla
            if j.get("fin_contrato") == temporada_actual
        ]

        num_jugadores_vencidos += len(jugadores_vencidos)

        jugadores_a_renovar = [
            j for j in plantilla
            if j.get("fin_contrato") == temporada_actual
        ]

        if not jugadores_a_renovar:
            continue

        # Calcula los 3 mejores del equipo por media (para renovación automática).
        plantilla_ordenada = sorted(
            plantilla,
            key=lambda j: j.get("media", 0),
            reverse=True
        )
        top3_media = {
            j["nombre"]
            for j in plantilla_ordenada[:3]
            if j.get("media", 0) > 0
        }

        # Primero decide por los más importantes.
        jugadores_a_renovar.sort(
            key=lambda j: (
                j.get("pos") == "POR",
                j.get("media", 0),
                -j.get("edad", 20),
            ),
            reverse=True
        )

        for jugador in jugadores_a_renovar:
            edad = jugador.get("edad", 20)
            media = jugador.get("media", 40)
            posicion = jugador.get("pos", "JUG")

            salario_nuevo = calcular_salario_por_temporada(
                media,
                edad,
                es_sub19
            )

            # Si no puede pagar ni su sueldo anual, no puede renovarlo.
            if salario_nuevo > presupuesto:
                continue

            # Si es uno de los 3 mejores del equipo, renovación automática.
            if jugador["nombre"] in top3_media:
                # Duración del nuevo contrato.
                if es_sub19:
                    duracion = random.choice([1, 2, 2, 3])
                elif edad >= 34:
                    duracion = random.choice([1, 1, 2])
                elif edad >= 30:
                    duracion = random.choice([1, 2, 2, 3])
                elif edad <= 21 and media >= 70:
                    duracion = random.choice([3, 3, 4, 4])
                elif media >= 80:
                    duracion = random.choice([3, 3, 4])
                else:
                    duracion = random.choice([2, 3, 3, 4])

                jugador["salario"] = salario_nuevo
                jugador["fin_contrato"] = temporada_actual + duracion - 1

                renovaciones.append(
                    f"📝 {equipo} renueva a {jugador['nombre']} "
                    f"hasta T{jugador['fin_contrato']} "
                    f"({duracion} temp., "
                    f"{formatear_valor(salario_nuevo)}/temp.)"
                )
                continue

            # Compañeros de la misma posición.
            companeros = [
                j for j in plantilla
                if j is not jugador and j.get("pos") == posicion
            ]

            media_posicion = (
                sum(j.get("media", 0) for j in companeros) / len(companeros)
                if companeros
                else media
            )

            diferencia = media - media_posicion

            # Base alta: las renovaciones deben ser habituales.
            prob_renovar = 0.72

            # Calidad del jugador comparada con sus compañeros.
            if diferencia >= 5:
                prob_renovar += 0.18
            elif diferencia >= 2:
                prob_renovar += 0.10
            elif diferencia <= -6:
                prob_renovar -= 0.30
            elif diferencia <= -3:
                prob_renovar -= 0.15

            # Calidad absoluta.
            if media >= 82:
                prob_renovar += 0.12
            elif media >= 74:
                prob_renovar += 0.06
            elif media < 55:
                prob_renovar -= 0.30
            elif media < 62:
                prob_renovar -= 0.15

            # Edad.
            if edad <= 21:
                prob_renovar += 0.10
            elif edad >= 35:
                prob_renovar -= 0.40
            elif edad >= 33:
                prob_renovar -= 0.25
            elif edad >= 31:
                prob_renovar -= 0.12

            # Necesidad de portero: si solo queda uno, se renueva seguro.
            if posicion == "POR":
                numero_porteros = sum(
                    1 for j in plantilla if j.get("pos") == "POR"
                )

                if numero_porteros <= 1:
                    prob_renovar = 1.0
                elif numero_porteros == 2:
                    prob_renovar += 0.12

            # En Sub-19 interesa mantener a casi todos los jóvenes.
            if es_sub19:
                if edad <= 18:
                    prob_renovar += 0.12
                elif edad >= 19 and diferencia <= -4:
                    prob_renovar -= 0.15

            prob_renovar = max(0.10, min(0.98, prob_renovar))

            # Jugadores importantes casi siempre renuevan.
            jugador_importante = (
                media >= 74
                or diferencia >= 2
                or (posicion == "POR" and len(companeros) <= 1)
            )

            roll = random.random()
            if not jugador_importante and roll > prob_renovar:
                continue

            roll2 = random.random()
            if jugador_importante and roll2 > prob_renovar:
                continue

            # Duración del nuevo contrato.
            if es_sub19:
                duracion = random.choice([1, 2, 2, 3])
            elif edad >= 34:
                duracion = random.choice([1, 1, 2])
            elif edad >= 30:
                duracion = random.choice([1, 2, 2, 3])
            elif edad <= 21 and media >= 70:
                duracion = random.choice([3, 3, 4, 4])
            elif media >= 80:
                duracion = random.choice([3, 3, 4])
            else:
                duracion = random.choice([2, 3, 3, 4])

            jugador["salario"] = salario_nuevo
            jugador["fin_contrato"] = temporada_actual + duracion - 1

            renovaciones.append(
                f"📝 {equipo} renueva a {jugador['nombre']} "
                f"hasta T{jugador['fin_contrato']} "
                f"({duracion} temp., "
                f"{formatear_valor(salario_nuevo)}/temp.)"
            )

    if renovaciones:
        db["mercado_log"].extend(renovaciones)

    return renovaciones

def cerrar_temporada_y_preparar_siguiente():
    db = st.session_state.db

    # Rellenar divisiones de tramos antiguos
    for eq, edata in db["equipos_data"].items():
        for j in edata["jugadores"]:
            for tramo in j.get("historial_temporadas", []):
                if not tramo.get("division"):
                    equipo_tramo = tramo.get("equipo", eq)
                    if equipo_tramo in db["equipos_data"]:
                        tramo["division"] = db["equipos_data"][equipo_tramo].get("liga", "")

    asegurar_2a_division_operativa()

    estado_vacio_playoff = {
        "activo": False,
        "equipos": [],
        "calendario": [],
        "resultados": [],
        "jornada": 0,
        "ganadores_semis": []
    }

    # -------------------------
    # PLAYOFFS SENIOR
    # -------------------------

    liga2 = db["ligas"]["2ª División"]
    df2_final = clasificacion_liga(liga2)
    playoff = db.get("playoff_2a", {})

    liga_regular_2a_terminada = (
        bool(liga2.get("calendario")) and
        liga2.get("jornada", 0) >= len(liga2.get("calendario", []))
    )

    if liga_regular_2a_terminada and not playoff.get("activo") and not playoff.get("resultados"):
        db["playoff_2a"] = crear_playoff_ascenso_2a(df2_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de 2ª División. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff = db.get("playoff_2a", {})
    if playoff.get("activo"):
        ganador_po = ganador_final_playoff(playoff)
        playoff_terminado = (
            playoff.get("jornada", 0) >= len(playoff.get("calendario", []))
            and ganador_po is not None
        )
        if not playoff_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de 2ª División. Debes completarlo en la pestaña Jornada.")
            return

    liga3a = db["ligas"]["3ª División Grupo A"]
    df3a_final = clasificacion_liga(liga3a)
    playoff_3a_a = db.get("playoff_3a_grupo_a", {})

    liga_regular_3a_a_terminada = (
        bool(liga3a.get("calendario")) and
        liga3a.get("jornada", 0) >= len(liga3a.get("calendario", []))
    )

    if liga_regular_3a_a_terminada and not playoff_3a_a.get("activo") and not playoff_3a_a.get("resultados"):
        db["playoff_3a_grupo_a"] = crear_playoff_ascenso_3a(df3a_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de 3ª División Grupo A. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff_3a_a = db.get("playoff_3a_grupo_a", {})
    if playoff_3a_a.get("activo"):
        ganador_po_3a_a = ganador_final_playoff(playoff_3a_a)
        playoff_3a_a_terminado = (
            playoff_3a_a.get("jornada", 0) >= len(playoff_3a_a.get("calendario", []))
            and ganador_po_3a_a is not None
        )
        if not playoff_3a_a_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de 3ª División Grupo A. Debes completarlo en la pestaña Jornada.")
            return

    liga3b = db["ligas"]["3ª División Grupo B"]
    df3b_final = clasificacion_liga(liga3b)
    playoff_3a_b = db.get("playoff_3a_grupo_b", {})

    liga_regular_3a_b_terminada = (
        bool(liga3b.get("calendario")) and
        liga3b.get("jornada", 0) >= len(liga3b.get("calendario", []))
    )

    if liga_regular_3a_b_terminada and not playoff_3a_b.get("activo") and not playoff_3a_b.get("resultados"):
        db["playoff_3a_grupo_b"] = crear_playoff_ascenso_3a(df3b_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de 3ª División Grupo B. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff_3a_b = db.get("playoff_3a_grupo_b", {})
    if playoff_3a_b.get("activo"):
        ganador_po_3a_b = ganador_final_playoff(playoff_3a_b)
        playoff_3a_b_terminado = (
            playoff_3a_b.get("jornada", 0) >= len(playoff_3a_b.get("calendario", []))
            and ganador_po_3a_b is not None
        )
        if not playoff_3a_b_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de 3ª División Grupo B. Debes completarlo en la pestaña Jornada.")
            return

    # -------------------------
    # PLAYOFFS SUB-19
    # -------------------------

    liga2_sub19 = db["ligas"]["Sub-19 2 División"]
    df2_sub19_final = clasificacion_liga(liga2_sub19)
    playoff_sub19_2a = db.get("playoff_sub19_2a", {})

    liga_regular_2a_sub19_terminada = (
        bool(liga2_sub19.get("calendario")) and
        liga2_sub19.get("jornada", 0) >= len(liga2_sub19.get("calendario", []))
    )

    if liga_regular_2a_sub19_terminada and not playoff_sub19_2a.get("activo") and not playoff_sub19_2a.get("resultados"):
        db["playoff_sub19_2a"] = crear_playoff_ascenso_2a(df2_sub19_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de Sub-19 2 División. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff_sub19_2a = db.get("playoff_sub19_2a", {})
    if playoff_sub19_2a.get("activo"):
        ganador_po_sub19_2a = ganador_final_playoff(playoff_sub19_2a)
        playoff_sub19_2a_terminado = (
            playoff_sub19_2a.get("jornada", 0) >= len(playoff_sub19_2a.get("calendario", []))
            and ganador_po_sub19_2a is not None
        )
        if not playoff_sub19_2a_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de Sub-19 2 División. Debes completarlo en la pestaña Jornada.")
            return

    liga3a_sub19 = db["ligas"]["Sub-19 3 División Grupo A"]
    df3a_sub19_final = clasificacion_liga(liga3a_sub19)
    playoff_sub19_3a_a = db.get("playoff_sub19_3agrupoa", {})

    liga_regular_3a_sub19_a_terminada = (
        bool(liga3a_sub19.get("calendario")) and
        liga3a_sub19.get("jornada", 0) >= len(liga3a_sub19.get("calendario", []))
    )

    if liga_regular_3a_sub19_a_terminada and not playoff_sub19_3a_a.get("activo") and not playoff_sub19_3a_a.get("resultados"):
        db["playoff_sub19_3agrupoa"] = crear_playoff_ascenso_3a(df3a_sub19_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de Sub-19 3 División Grupo A. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff_sub19_3a_a = db.get("playoff_sub19_3agrupoa", {})
    if playoff_sub19_3a_a.get("activo"):
        ganador_po_sub19_3a_a = ganador_final_playoff(playoff_sub19_3a_a)
        playoff_sub19_3a_a_terminado = (
            playoff_sub19_3a_a.get("jornada", 0) >= len(playoff_sub19_3a_a.get("calendario", []))
            and ganador_po_sub19_3a_a is not None
        )
        if not playoff_sub19_3a_a_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de Sub-19 3 División Grupo A. Debes completarlo en la pestaña Jornada.")
            return

    liga3b_sub19 = db["ligas"]["Sub-19 3 División Grupo B"]
    df3b_sub19_final = clasificacion_liga(liga3b_sub19)
    playoff_sub19_3a_b = db.get("playoff_sub19_3agrupob", {})

    liga_regular_3a_sub19_b_terminada = (
        bool(liga3b_sub19.get("calendario")) and
        liga3b_sub19.get("jornada", 0) >= len(liga3b_sub19.get("calendario", []))
    )

    if liga_regular_3a_sub19_b_terminada and not playoff_sub19_3a_b.get("activo") and not playoff_sub19_3a_b.get("resultados"):
        db["playoff_sub19_3agrupob"] = crear_playoff_ascenso_3a(df3b_sub19_final) or copy.deepcopy(estado_vacio_playoff)
        st.warning("Se ha creado el playoff de ascenso de Sub-19 3 División Grupo B. Debes jugarlo en la pestaña Jornada antes de iniciar la nueva temporada.")
        return

    playoff_sub19_3a_b = db.get("playoff_sub19_3agrupob", {})
    if playoff_sub19_3a_b.get("activo"):
        ganador_po_sub19_3a_b = ganador_final_playoff(playoff_sub19_3a_b)
        playoff_sub19_3a_b_terminado = (
            playoff_sub19_3a_b.get("jornada", 0) >= len(playoff_sub19_3a_b.get("calendario", []))
            and ganador_po_sub19_3a_b is not None
        )
        if not playoff_sub19_3a_b_terminado:
            st.warning("Aún no ha terminado el playoff de ascenso de Sub-19 3 División Grupo B. Debes completarlo en la pestaña Jornada.")
            return

    temporada_cerrada = db["config"]["temporada"]

    # Registrar campeones e historial de clubes
    for nombre_liga, liga in db["ligas"].items():
        df = clasificacion_liga(liga)
        if not df.empty:
            campeon = df.index[0]
            db["historial_campeones"].append({
                "temporada": temporada_cerrada,
                "liga": nombre_liga,
                "campeon": campeon
            })
            registrar_historial_clubes_temporada(nombre_liga, df)

            repartir_premios_clasificacion(nombre_liga, df)

    # Ascensos y descensos senior + sub-19
    movimientos_divisiones = aplicar_ascensos_descensos()
    movimientos_divisiones_sub19 = aplicar_ascensos_descensos_sub19()

    # Guardar en mercado_log (por si lo usas en otro lado)
    db["mercado_log"].extend(movimientos_divisiones)
    db["mercado_log"].extend(movimientos_divisiones_sub19)

    # Guardar en historial_movimientos (para que se acumulen año a año)
    historial_mov = db.setdefault("historial_movimientos", [])
    for m in movimientos_divisiones + movimientos_divisiones_sub19:
        historial_mov.append(f"Temporada {temporada_cerrada}: {m}")

    # Ascensos y descensos nacionales (Com, Tengu, Folimón) senior + sub-19
    movimientos_nacionales = aplicar_ascensos_descensos_nacionales()
    movimientos_nacionales_sub19 = aplicar_ascensos_descensos_nacionales_sub19()
    db["mercado_log"].extend(movimientos_nacionales)
    db["mercado_log"].extend(movimientos_nacionales_sub19)

    db["playoff_2a"] = resetear_playoff()
    db["playoff_3a_grupo_a"] = resetear_playoff()
    db["playoff_3a_grupo_b"] = resetear_playoff()
    db["playoff_sub19_2a"] = resetear_playoff()
    db["playoff_sub19_3agrupoa"] = resetear_playoff()
    db["playoff_sub19_3agrupob"] = resetear_playoff()

    # Actualizar jugadores y guardar historial de la temporada
    for eq, edata in db["equipos_data"].items():
        for j in edata["jugadores"]:
            media_temp = round(j["nota_total"] / j["partidos"], 2) if j["partidos"] > 0 else 0


            equipo_hist = j.get("equipo_actual", eq)
            division_hist = db["equipos_data"][equipo_hist].get("liga", "")


            entrada = abrir_tramo_temporada(j, equipo_hist)
            # Solo asignar división si no la tiene ya (para no sobreescribir la histórica)
            if not entrada.get("division"):
                entrada["division"] = division_hist

            partidos_tramo = entrada.get("partidos", 0)
            nota_tramo = entrada.get("nota_total", 0)
            entrada["media_partidos"] = round(nota_tramo / partidos_tramo, 2) if partidos_tramo > 0 else 0


            entrada["media_final"] = j["media"]
            entrada["valor_final"] = j["valor"]


            edad = j.get("edad", 24)


            # ─────────────────────────────────────────────────────
            # BONUS POR RENDIMIENTO EN LA TEMPORADA
            # ─────────────────────────────────────────────────────
            if media_temp >= 8.5:
                j["media"] = min(99, j["media"] + random.randint(2, 4))
                j["valor"] += random.randint(2, 4)
            elif media_temp >= 7.8:
                j["media"] = min(99, j["media"] + random.randint(1, 3))
                j["valor"] += random.randint(1, 3)
            elif media_temp >= 7.3:
                j["media"] = min(99, j["media"] + random.randint(1, 2))
                j["valor"] += random.randint(1, 2)
            elif media_temp <= 5.5 and j["partidos"] > 0:
                j["media"] = max(40, j["media"] - random.randint(1, 2))
                j["valor"] = max(1, j["valor"] - random.randint(1, 2))
            elif media_temp <= 6.0 and j["partidos"] > 0:
                j["media"] = max(40, j["media"] - 1)
                j["valor"] = max(1, j["valor"] - 1)

            # ─────────────────────────────────────────────────────
            # BONUS POR MINUTOS JUGADOS Y DIVISIÓN
            # ─────────────────────────────────────────────────────
            minutos_jugador = j.get("minutos_totales", 0)
            bonus_minutos = bonus_por_minutos_y_liga(
                equipo_hist,
                minutos_jugador
            )

            j["media"] = min(
                99,
                round(j["media"] + bonus_minutos, 2)
            )

            # ─────────────────────────────────────────────────────
            # CRECIMIENTO BASE POR EDAD Y MEDIA
            # ─────────────────────────────────────────────────────
            if edad <= 21:
                if j["media"] < 65:
                    delta_media = random.choices([2, 3, 4, 5], weights=[2, 4, 3, 1])[0]
                elif j["media"] < 70:
                    delta_media = random.choices([1, 2, 3, 4], weights=[2, 4, 3, 1])[0]
                elif j["media"] < 74:
                    delta_media = random.choices([1, 2, 3], weights=[3, 4, 2])[0]
                elif j["media"] < 77:
                    delta_media = random.choices([0, 1, 2], weights=[2, 5, 2])[0]
                elif j["media"] < 80:
                    delta_media = random.choices([0, 1, 2], weights=[3, 4, 2])[0]
                else:
                    delta_media = random.choices([0, 1], weights=[6, 3])[0]
            elif 22 <= edad <= 25:
                if j["media"] < 65:
                    delta_media = random.choices([1, 2, 3, 4], weights=[2, 4, 3, 1])[0]
                elif j["media"] < 70:
                    delta_media = random.choices([1, 2, 3], weights=[3, 4, 2])[0]
                elif j["media"] < 74:
                    delta_media = random.choices([0, 1, 2], weights=[2, 5, 2])[0]
                elif j["media"] < 77:
                    delta_media = random.choices([0, 1], weights=[5, 4])[0]
                elif j["media"] < 80:
                    delta_media = random.choices([-1, 0, 1], weights=[2, 5, 2])[0]
                else:
                    delta_media = random.choices([-1, 0], weights=[5, 4])[0]
            elif 26 <= edad <= 28:
                if j["media"] < 65:
                    delta_media = random.choices([1, 2, 3], weights=[2, 4, 3])[0]
                elif j["media"] < 70:
                    delta_media = random.choices([0, 1, 2], weights=[2, 5, 2])[0]
                elif j["media"] < 74:
                    delta_media = random.choices([0, 1], weights=[5, 4])[0]
                elif j["media"] < 77:
                    delta_media = random.choices([-1, 0, 1], weights=[3, 4, 2])[0]
                else:
                    delta_media = random.choices([-2, -1, 0], weights=[2, 4, 3])[0]
            elif 29 <= edad <= 31:
                if j["media"] < 65:
                    delta_media = random.choices([0, 1, 2], weights=[2, 4, 3])[0]
                elif j["media"] < 70:
                    delta_media = random.choices([0, 1], weights=[5, 4])[0]
                elif j["media"] < 74:
                    delta_media = random.choices([-1, 0, 1], weights=[3, 4, 2])[0]
                else:
                    delta_media = random.choices([-2, -1, 0], weights=[3, 4, 2])[0]
            else:
                if j["media"] < 65:
                    delta_media = random.choices([0, 1, 2], weights=[2, 4, 3])[0]
                elif j["media"] < 70:
                    delta_media = random.choices([0, 1], weights=[5, 4])[0]
                elif j["media"] < 74:
                    delta_media = random.choices([-1, 0], weights=[5, 4])[0]
                else:
                    delta_media = random.choices([-2, -1, 0], weights=[3, 4, 2])[0]



            # ─────────────────────────────────────────────────────
            # BONUS: Juveniles de filial que juegan en primer equipo
            # ─────────────────────────────────────────────────────
            if (es_equipo_sub19(eq) or eq.endswith(" B") or eq.endswith(" C")) and edad <= 21:
                if j.get("ficha_primer_equipo", False) or j.get("promocion_temporal", False):
                    # Bonus de crecimiento acelerado por jugar en primer equipo
                    if edad <= 19 and j["media"] < 75:
                        delta_media += 1
                    elif edad <= 21 and j["media"] < 73:
                        delta_media += 1



            # ─────────────────────────────────────────────────────
            # BONUS EXTRA: Jóvenes con media baja crecen más
            # ─────────────────────────────────────────────────────
            if edad <= 21 and j["media"] < 68:
                # Bonus adicional por ser joven y tener media baja
                if edad <= 19:
                    delta_media += random.randint(1, 2)
                elif edad <= 21:
                    delta_media += 1


            j["media"] = max(40, min(99, j["media"] + delta_media))

            factor_edad = 1.0
            if edad <= 21:
                factor_edad = 1.18
            elif edad <= 25:
                factor_edad = 1.08
            elif edad <= 28:
                factor_edad = 0.98
            elif edad <= 31:
                factor_edad = 0.88
            else:
                factor_edad = 0.75

            bonus_rendimiento = 0.0
            if media_temp >= 8.5:
                bonus_rendimiento = 3
            elif media_temp >= 7.5:
                bonus_rendimiento = 1.5
            elif media_temp <= 5.5 and j["partidos"] > 0:
                bonus_rendimiento = -2.5
            elif media_temp <= 6.2 and j["partidos"] > 0:
                bonus_rendimiento = -1

            valor_base = (j["media"] - 50) * 0.8
            nuevo_valor = valor_base * factor_edad + bonus_rendimiento

            if es_equipo_sub19(eq):
                nuevo_valor *= 0.05

            j["valor"] = round((j["valor"] * 0.75) + (nuevo_valor * 0.25), 1)
            j["valor"] = max(0.1, j["valor"])

            j["edad"] = edad + 1

            limitar_valor_por_liga(j, eq)

            j["historial_media"].append(j["media"])
            j["historial_valor"].append(j["valor"])

            entrada["media_final"] = j["media"]
            entrada["valor_final"] = j["valor"]

            if j["lesion_jornadas"] > 0:
                j["lesion_jornadas"] = max(0, j["lesion_jornadas"] - 1)

            j["cansancio"] = 0
            j["goles"] = 0
            j["asistencias"] = 0
            j["amarillas"] = 0
            j["rojas"] = 0
            j["partidos"] = 0
            j["partidos_titular"] = 0
            j["minutos_totales"] = 0
            j["nota_total"] = 0
            j["goles_encajados"] = 0

    # ─────────────────────────────────────────────────────
    # EVOLUCIÓN DE AGENTES LIBRES (crecimiento más lento)
    # ─────────────────────────────────────────────────────
    for libre in db.get("jugadores_libres", []):
        j = libre["jugador"]
        edad = j.get("edad", 24)

        # Crecimiento base reducido por no tener equipo
        if edad <= 21:
            delta_media = random.choices([0, 1, 2], weights=[4, 4, 1])[0]
        elif 22 <= edad <= 25:
            delta_media = random.choices([0, 1], weights=[7, 2])[0]
        elif 26 <= edad <= 28:
            delta_media = random.choices([-1, 0, 1], weights=[2, 6, 1])[0]
        elif 29 <= edad <= 31:
            delta_media = random.choices([-1, 0], weights=[4, 5])[0]
        else:
            delta_media = random.choices([-2, -1, 0], weights=[2, 4, 3])[0]

        j["media"] = max(40, min(99, j["media"] + delta_media))

        # Valor: pequeño ajuste según media y edad
        if edad <= 25 and j["media"] >= 70:
            j["valor"] = round(j["valor"] * 1.03, 1)
        elif edad <= 28 and j["media"] >= 65:
            j["valor"] = round(j["valor"] * 1.01, 1)
        else:
            j["valor"] = round(j["valor"] * 0.98, 1)

        j["valor"] = max(0.1, j["valor"])

        # Edad +1 como el resto
        j["edad"] = edad + 1

        j["historial_media"].append(j["media"])
        j["historial_valor"].append(j["valor"])

    playoff_final = db.get("playoff_2a", {})
    ascendido_playoff = ganador_final_playoff(playoff_final)

    if playoff_final.get("calendario") or playoff_final.get("resultados"):
        db.setdefault("historial_playoff", [])
        db["historial_playoff"].append({
            "temporada": temporada_cerrada,
            "liga": "2ª División",
            "equipos": playoff_final.get("equipos", [])[:],
            "resultados": copy.deepcopy(playoff_final.get("resultados", [])),
            "ascendido": ascendido_playoff,
            "eventos": movimientos_divisiones[:]
        })

    for clave, nombre_liga, eventos in [
        ("playoff_3a_grupo_a", "3ª División Grupo A", movimientos_divisiones),
        ("playoff_3a_grupo_b", "3ª División Grupo B", movimientos_divisiones),
        ("playoff_sub19_2a", "Sub-19 2 División", movimientos_divisiones_sub19),
        ("playoff_sub19_3agrupoa", "Sub-19 3 División Grupo A", movimientos_divisiones_sub19),
        ("playoff_sub19_3agrupob", "Sub-19 3 División Grupo B", movimientos_divisiones_sub19),
    ]:
        playoff_x = db.get(clave, {})
        ascendido_x = ganador_final_playoff(playoff_x)

        if playoff_x.get("calendario") or playoff_x.get("resultados"):
            db.setdefault("historial_playoff", [])
            db["historial_playoff"].append({
                "temporada": temporada_cerrada,
                "liga": nombre_liga,
                "equipos": playoff_x.get("equipos", [])[:],
                "resultados": copy.deepcopy(playoff_x.get("resultados", [])),
                "ascendido": ascendido_x,
                "eventos": eventos[:]
            })

    renovar_contratos_ia()

    db["config"]["temporada"] += 1

    descontar_salarios_temporada(db)

    liberar_jugadores_sin_contrato(db)

    # Añadir una fila por cada temporada que el jugador continúe libre
    temporada_actual = db["config"]["temporada"]

    for libre in db.get("jugadores_libres", []):
        jugador = libre["jugador"]
        historial = jugador.setdefault("historial_temporadas", [])

        ya_existe = any(
            tramo.get("temporada") == temporada_actual
            and tramo.get("equipo") == "Sin equipo"
            for tramo in historial
        )

        if not ya_existe:
            historial.append({
                "temporada": temporada_actual,
                "equipo": "Sin equipo",
                "division": "",
                "tipo_estancia": "agente libre",
                "nota_total": 0,
                "partidos": 0,
                "partidos_titular": 0,
                "minutos": 0,
                "goles": 0,
                "asistencias": 0,
                "amarillas": 0,
                "rojas": 0,
                "goles_encajados": 0,
                "media_partidos": 0,
                "media_final": jugador.get("media", 0),
                "valor_final": jugador.get("valor", 0),
            })

    devolver_cedidos()
    promocionar_sub19_por_edad()
    procesar_retiradas()
    crear_canteranos_temporada()
    mercado_automatico()
    reset_relaciones_primer_equipo_temporada()

    # ─────────────────────────────────────────────────────
    # INICIALIZAR TRAMOS PARA LA NUEVA TEMPORADA
    # (para que los jugadores con ficha tengan tramo desde la jornada 1)
    # ─────────────────────────────────────────────────────
    nueva_temporada = db["config"]["temporada"]

    for eq, edata in db["equipos_data"].items():
        for j in edata["jugadores"]:
            # Determinar equipo y tipo_estancia para este jugador
            if j.get("ficha_primer_equipo", False) and j.get("primer_equipo_asignado"):
                equipo_stats = j["primer_equipo_asignado"]
                tipo_estancia = "ficha_primer_equipo"
            elif j.get("ficha_filial", False) and j.get("filial_asignado"):
                equipo_stats = j["filial_asignado"]
                tipo_estancia = "ficha_filial"
            else:
                equipo_stats = eq
                tipo_estancia = "normal"

            # Crear tramo si no existe para esta temporada
            tramo_existente = None
            for t in j.get("historial_temporadas", []):
                if t.get("temporada") == nueva_temporada and t.get("equipo") == equipo_stats:
                    tramo_existente = t
                    break

            if tramo_existente is None:
                tramo_nuevo = {
                    "temporada": nueva_temporada,
                    "equipo": equipo_stats,
                    "tipo_estancia": tipo_estancia,
                    "partidos": 0,
                    "partidos_titular": 0,
                    "minutos": 0,
                    "goles": 0,
                    "asistencias": 0,
                    "amarillas": 0,
                    "rojas": 0,
                    "goles_encajados": 0,
                    "nota_total": 0,
                }
                j.setdefault("historial_temporadas", []).append(tramo_nuevo)

    # ============================================================
    # CLASIFICACIÓN EUROPEA DE LA TEMPORADA QUE SE CIERRA
    # Se guarda para la siguiente temporada.
    # ============================================================

    clasificados_europa = {
        "senior": {
            "champions": [],
            "europa_league": [],
            "conference": [],
        },
        "sub19": {
            "champions": [],
            "europa_league": [],
            "conference": [],
        },
    }

    # 1) Liga principal (sin prefijo)
    nombreliga_principal = "1ª División"
    if nombreliga_principal in db["ligas"]:
        df = clasificacion_liga(db["ligas"][nombreliga_principal])
        if len(df) >= 8:
            clasificados_europa["senior"]["champions"].extend(df.index[:4].tolist())
            clasificados_europa["senior"]["europa_league"].extend(df.index[4:6].tolist())
            clasificados_europa["senior"]["conference"].extend(df.index[6:8].tolist())

    # 2) Ligas de Com, Tengu y Folimón
    paises_europa = ["Com", "Tengu", "Folimón"]

    for pais in paises_europa:
        nombreliga = f"{pais} 1ª División"

        if nombreliga in db["ligas"]:
            df = clasificacion_liga(db["ligas"][nombreliga])
            if len(df) >= 8:
                clasificados_europa["senior"]["champions"].extend(df.index[:4].tolist())
                clasificados_europa["senior"]["europa_league"].extend(df.index[4:6].tolist())
                clasificados_europa["senior"]["conference"].extend(df.index[6:8].tolist())

    # 1) Liga principal Sub-19 (sin tilde)
    nombreliga_principal_sub19 = "Sub-19 1 División"
    if nombreliga_principal_sub19 in db["ligas"]:
        df = clasificacion_liga(db["ligas"][nombreliga_principal_sub19])
        if len(df) >= 8:
            clasificados_europa["sub19"]["champions"].extend(df.index[:4].tolist())
            clasificados_europa["sub19"]["europa_league"].extend(df.index[4:6].tolist())
            clasificados_europa["sub19"]["conference"].extend(df.index[6:8].tolist())

    # 2) Sub-19 de Com, Tengu y Folimón (sin tilde)
    for pais in paises_europa:
        nombreliga_sub19 = f"{pais} Sub-19 1 División"

        if nombreliga_sub19 in db["ligas"]:
            df = clasificacion_liga(db["ligas"][nombreliga_sub19])
            if len(df) >= 8:
                clasificados_europa["sub19"]["champions"].extend(df.index[:4].tolist())
                clasificados_europa["sub19"]["europa_league"].extend(df.index[4:6].tolist())
                clasificados_europa["sub19"]["conference"].extend(df.index[6:8].tolist())

    # No crear Europa al cerrar la temporada inicial.
    # Al cerrar la T1, se prepara Europa para la T2.
    nueva_temporada_europa = temporada_cerrada + 1

    db.setdefault("europa", {})
    db["europa"]["temporada"] = nueva_temporada_europa
    db["europa"]["senior"] = {}
    db["europa"]["sub19"] = {}

    nombres_europa = {
        "champions": "Champions",
        "europa_league": "Europa League",
        "conference": "Conference",
    }

    for categoria in ["senior", "sub19"]:
        sufijo = "Senior" if categoria == "senior" else "Sub-19"

        for clave, equipos in clasificados_europa[categoria].items():
            if not equipos:
                continue

            db["europa"][categoria][clave] = {
                "nombre": f"{nombres_europa[clave]} {sufijo}",
                "temporada": nueva_temporada_europa,
                "equipos": equipos,
                "ronda_inicio": (
                    "octavos"
                    if clave == "champions"
                    else "cuartos"
                ),
                "eliminatorias": [],
            }

    # ============================================================
    # COPAS NACIONALES PARA LA SIGUIENTE TEMPORADA
    # ============================================================

    crear_copas_temporada(
        db,
        nueva_temporada_europa,
    )

    # ─────────────────────────────────────────────────────
    # RESETEO DE PLAYOFFS
    # ─────────────────────────────────────────────────────
    for _, liga in db["ligas"].items():
        liga["calendario"] = generar_calendario(liga["equipos"]) if len(liga["equipos"]) >= 2 else []
        liga["resultados"] = []
        liga["jornada"] = 0

    db["playoff_2a"] = copy.deepcopy(estado_vacio_playoff)
    db["playoff_3a_grupo_a"] = copy.deepcopy(estado_vacio_playoff)
    db["playoff_3a_grupo_b"] = copy.deepcopy(estado_vacio_playoff)
    db["playoff_sub19_2a"] = copy.deepcopy(estado_vacio_playoff)
    db["playoff_sub19_3agrupoa"] = copy.deepcopy(estado_vacio_playoff)
    db["playoff_sub19_3agrupob"] = copy.deepcopy(estado_vacio_playoff)

# ============================================================
# EUROPA
# ============================================================

def _marcador_europa():
    goles_local = random.choices(
        [0, 1, 2, 3, 4],
        weights=[3, 5, 4, 2, 1]
    )[0]
    goles_visitante = random.choices(
        [0, 1, 2, 3, 4],
        weights=[3, 5, 4, 2, 1]
    )[0]
    return goles_local, goles_visitante


def _crear_cruce_europa(equipo1, equipo2, ida_vuelta=True):
    return {
        "local": equipo1,
        "visitante": equipo2,
        "ida_vuelta": ida_vuelta,
        "resultado_ida": None,
        "resultado_vuelta": None,
        "ganador": None,
    }


def generar_eliminatorias_europa(competicion):
    equipos = competicion.get("equipos", [])[:]
    random.shuffle(equipos)

    ronda_inicio = competicion.get("ronda_inicio", "cuartos")
    rondas = []

    if ronda_inicio == "octavos":
        numero_equipos = 16
        nombre_ronda = "octavos"
    else:
        numero_equipos = 8
        nombre_ronda = "cuartos"

    equipos = equipos[:numero_equipos]

    cruces = []
    for i in range(0, len(equipos) - 1, 2):
        cruces.append(
            _crear_cruce_europa(
                equipos[i],
                equipos[i + 1],
                ida_vuelta=True
            )
        )

    if cruces:
        rondas.append({
            "ronda": nombre_ronda,
            "cruces": cruces
        })

    return rondas

def _pintar_partido_europa(cruce, ronda, idx, categoria, competicion_key, es_final=False):
    """
    Pinta un partido de Europa con el mismo formato exacto que en Jornada, incluyendo notas.
    """
    local = cruce["local"]
    visitante = cruce["visitante"]

    if es_final:
        resultado = cruce.get("resultado_final")

        if resultado is None:
            titulo = f"{local} vs {visitante} (Final)"
        else:
            titulo = f"{local} {resultado[0]} - {resultado[1]} {visitante} (Final)"

        with st.expander(titulo):
            if resultado is None:
                st.write("Final a partido único")
                if st.button("Jugar final", key=f"final_{categoria}_{competicion_key}_{idx}"):
                    simular_final_europa(cruce)
                    st.rerun()
            else:
                c1, c2 = st.columns(2)
                c1.markdown(f"**{local}**")
                c1.caption(f"11: {cruce.get('alineacion_local_final', '-')}")
                c2.markdown(f"**{visitante}**")
                c2.caption(f"11: {cruce.get('alineacion_visitante_final', '-')}")
                st.divider()

                st.success(f"🏆 Campeón: {cruce['ganador']}")

                eventos = cruce.get("eventos_final", [])
                for ev in sorted(eventos, key=lambda x: x.get("min", 0)):
                    st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")

                st.divider()
                notas = cruce.get("notas_final", [])
                if notas:
                    st.dataframe(pd.DataFrame(notas), hide_index=True, use_container_width=True)

    else:
        ida = cruce.get("resultado_ida")
        vuelta = cruce.get("resultado_vuelta")

        if ida is None:
            titulo = f"{local} vs {visitante} (Ida)"
        elif vuelta is None:
            titulo = f"{local} {ida[0]} - {ida[1]} {visitante} (Ida jugada)"
        else:
            titulo = f"{local} {ida[0]} - {ida[1]} {visitante} / {visitante} {vuelta[0]} - {vuelta[1]} {local}"

        with st.expander(titulo):
            if ida is None:
                st.write(f"**Ida:** {local} (local) vs {visitante} (visitante)")
                if st.button("Jugar ida", key=f"ida_{categoria}_{competicion_key}_{idx}"):
                    simular_ida_europa(cruce)
                    st.rerun()

            elif vuelta is None:
                st.write(f"**Ida:** {local} {ida[0]} - {ida[1]} {visitante}")
                st.write(f"**Vuelta:** pendiente")

                c1, c2 = st.columns(2)
                c1.markdown(f"**{local}**")
                c1.caption(f"11: {', '.join(cruce.get('alineacion_local_ida', ['-']))}")
                c2.markdown(f"**{visitante}**")
                c2.caption(f"11: {', '.join(cruce.get('alineacion_visitante_ida', ['-']))}")
                st.divider()

                eventos_ida = cruce.get("eventos_ida", [])
                for ev in sorted(eventos_ida, key=lambda x: x.get("min", 0)):
                    st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")

                st.divider()
                notas_ida = cruce.get("notas_ida", [])
                if notas_ida:
                    st.dataframe(pd.DataFrame(notas_ida), hide_index=True, use_container_width=True)

                st.divider()
                st.write(f"**Vuelta:** {visitante} (local) vs {local} (visitante)")
                if st.button("Jugar vuelta", key=f"vuelta_{categoria}_{competicion_key}_{idx}"):
                    simular_vuelta_europa(cruce)
                    st.rerun()

            else:
                st.write(f"**Ida:** {local} {ida[0]} - {ida[1]} {visitante}")
                st.write(f"**Vuelta:** {visitante} {vuelta[0]} - {vuelta[1]} {local}")
                st.success(f"Clasificado: {cruce['ganador']}")

                # Ida
                c1, c2 = st.columns(2)
                c1.markdown(f"**{local} (Ida)**")
                c1.caption(f"11: {', '.join(cruce.get('alineacion_local_ida', ['-']))}")
                c2.markdown(f"**{visitante} (Ida)**")
                c2.caption(f"11: {', '.join(cruce.get('alineacion_visitante_ida', ['-']))}")
                st.divider()

                eventos_ida = cruce.get("eventos_ida", [])
                for ev in sorted(eventos_ida, key=lambda x: x.get("min", 0)):
                    st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")

                st.divider()
                notas_ida = cruce.get("notas_ida", [])
                if notas_ida:
                    st.dataframe(pd.DataFrame(notas_ida), hide_index=True, use_container_width=True)

                st.divider()

                # Vuelta
                c1, c2 = st.columns(2)
                c1.markdown(f"**{visitante} (Vuelta)**")
                c1.caption(f"11: {', '.join(cruce.get('alineacion_local_vuelta', ['-']))}")
                c2.markdown(f"**{local} (Vuelta)**")
                c2.caption(f"11: {', '.join(cruce.get('alineacion_visitante_vuelta', ['-']))}")
                st.divider()

                eventos_vuelta = cruce.get("eventos_vuelta", [])
                for ev in sorted(eventos_vuelta, key=lambda x: x.get("min", 0)):
                    st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")

                st.divider()
                notas_vuelta = cruce.get("notas_vuelta", [])
                if notas_vuelta:
                    st.dataframe(pd.DataFrame(notas_vuelta), hide_index=True, use_container_width=True)

# ============================================================
# EUROPA - USANDO simular_partido() DE JORNADA
# ============================================================

def simular_ida_europa(cruce):
    """Simula la ida de una eliminatoria europea usando simular_partido()."""
    if cruce.get("resultado_ida") is not None:
        return

    local = cruce["local"]
    visitante = cruce["visitante"]

    # Llamar a simular_partido() igual que en Jornada
    resultado = simular_partido(local, visitante, jornada_actual=None)

    cruce["resultado_ida"] = [resultado["goles1"], resultado["goles2"]]
    cruce["eventos_ida"] = resultado["eventos"]
    cruce["notas_ida"] = resultado.get("notas_partido", [])
    cruce["alineacion_local_ida"] = resultado["alineacion1"].split(", ") if resultado["alineacion1"] != "-" else []
    cruce["alineacion_visitante_ida"] = resultado["alineacion2"].split(", ") if resultado["alineacion2"] != "-" else []


def simular_vuelta_europa(cruce):
    """Simula la vuelta de una eliminatoria europea usando simular_partido()."""
    if cruce.get("resultado_ida") is None or cruce.get("resultado_vuelta") is not None:
        return

    local_ida = cruce["local"]
    visitante_ida = cruce["visitante"]

    # En la vuelta, el local de la ida es visitante
    resultado = simular_partido(visitante_ida, local_ida, jornada_actual=None)

    cruce["resultado_vuelta"] = [resultado["goles1"], resultado["goles2"]]
    cruce["eventos_vuelta"] = resultado["eventos"]
    cruce["notas_vuelta"] = resultado.get("notas_partido", [])
    cruce["alineacion_local_vuelta"] = resultado["alineacion1"].split(", ") if resultado["alineacion1"] != "-" else []
    cruce["alineacion_visitante_vuelta"] = resultado["alineacion2"].split(", ") if resultado["alineacion2"] != "-" else []

    # Decidir ganador por agregado
    ida_local, ida_visitante = cruce["resultado_ida"]
    vuelta_local, vuelta_visitante = resultado["goles1"], resultado["goles2"]

    total_local_ida = ida_local + vuelta_visitante
    total_visitante_ida = ida_visitante + vuelta_local

    if total_local_ida > total_visitante_ida:
        cruce["ganador"] = local_ida
    elif total_visitante_ida > total_local_ida:
        cruce["ganador"] = visitante_ida
    else:
        cruce["ganador"] = random.choice([local_ida, visitante_ida])


def simular_final_europa(cruce):
    """Simula la final (partido único) usando simular_partido()."""
    if cruce.get("resultado_final") is not None:
        return

    local = cruce["local"]
    visitante = cruce["visitante"]

    resultado = simular_partido(local, visitante, jornada_actual=None)

    cruce["resultado_final"] = [resultado["goles1"], resultado["goles2"]]
    cruce["eventos_final"] = resultado["eventos"]
    cruce["notas_final"] = resultado.get("notas_partido", [])
    cruce["alineacion_local_final"] = resultado["alineacion1"].split(", ") if resultado["alineacion1"] != "-" else []
    cruce["alineacion_visitante_final"] = resultado["alineacion2"].split(", ") if resultado["alineacion2"] != "-" else []

    if resultado["goles1"] > resultado["goles2"]:
        cruce["ganador"] = local
    elif resultado["goles2"] > resultado["goles1"]:
        cruce["ganador"] = visitante
    else:
        cruce["ganador"] = random.choice([local, visitante])

def todos_los_jugadores_de_europa():
    db = st.session_state.db
    europa = db.get("europa", {})
    equipos_data = db.get("equipos_data", {})

    stats = {}
    
    def crear_registro(nombre, equipo, posicion="JUG", competicion="-"):
        return {
            "Nombre": nombre,
            "Equipo": equipo,
            "Pos": posicion,
            "Goles": 0,
            "Asistencias": 0,
            "PJ": 0,
            "Minutos": 0,
            "Nota": 0.0,
            "Notas_contadas": 0,
            "Encajados": 0,
            "Competicion": competicion,
        }

    def obtener_datos_jugador(nombre, equipo):
        nombre_limpio = str(nombre).strip()

        # 1. Buscar en el equipo directo
        datos_equipo = equipos_data.get(equipo, {})
        jugadores = datos_equipo.get("jugadores", [])

        for jugador in jugadores:
            nombre_jugador = str(jugador.get("nombre", "")).strip()
            if nombre_jugador == nombre_limpio:
                return jugador

        # 2. Buscar en equipos vinculados del mismo club
        club_base = obtener_club_principal(equipo)

        for eq, edata in equipos_data.items():
            if obtener_club_principal(eq) != club_base:
                continue

            for jugador in edata.get("jugadores", []):
                nombre_jugador = str(jugador.get("nombre", "")).strip()
                if nombre_jugador == nombre_limpio:
                    return jugador

        return {}

    def normalizar_nombre(nombre):
        return str(nombre).strip()


    for categoria in ["senior", "sub19"]:
        categoria_europa = europa.get(categoria, {})


        for competicion_key in ["champions", "europa_league", "conference"]:
            competicion = categoria_europa.get(competicion_key, {})


            if not competicion:
                continue


            categoria_nombre = "Sub-19" if categoria == "sub19" else categoria.title()
            nombre_competicion = f"{competicion_key.replace('_', ' ').title()} {categoria_nombre}"

            for ronda in competicion.get("eliminatorias", []):
                for cruce in ronda.get("cruces", []):
                    # Procesar Ida, Vuelta y Final
                    partidos = [
                        (cruce.get("local"), cruce.get("visitante"), cruce.get("alineacion_local_ida", []), cruce.get("alineacion_visitante_ida", []), cruce.get("eventos_ida", []), cruce.get("notas_ida", [])),
                        (cruce.get("visitante"), cruce.get("local"), cruce.get("alineacion_local_vuelta", []), cruce.get("alineacion_visitante_vuelta", []), cruce.get("eventos_vuelta", []), cruce.get("notas_vuelta", [])),
                        (cruce.get("local"), cruce.get("visitante"), cruce.get("alineacion_local_final", []), cruce.get("alineacion_visitante_final", []), cruce.get("eventos_final", []), cruce.get("notas_final", [])),
                    ]

                    for local, visitante, alineacion_local, alineacion_visitante, eventos, notas in partidos:
                        if not eventos and not notas:
                            continue

                        equipos_partido = [
                            (local, alineacion_local),
                            (visitante, alineacion_visitante),
                        ]

                        # Registrar jugadores de la alineación
                        for equipo, alineacion in equipos_partido:
                            jugadores_partido = []

                            if isinstance(alineacion, str):
                                jugadores_partido = [parte.strip() for parte in alineacion.split(",") if parte.strip()]
                            elif isinstance(alineacion, list):
                                jugadores_partido = alineacion

                            for jugador_alineacion in jugadores_partido:
                                if isinstance(jugador_alineacion, dict):
                                    nombre = jugador_alineacion.get("nombre", "")
                                    posicion = jugador_alineacion.get("pos", "JUG")
                                else:
                                    texto_jugador = str(jugador_alineacion).strip()
                                    if "(" in texto_jugador and ")" in texto_jugador:
                                        nombre = texto_jugador.rsplit("(", 1)[0].strip()
                                        posicion = texto_jugador.rsplit("(", 1)[1].split(")", 1)[0].strip()
                                    else:
                                        nombre = texto_jugador
                                        posicion = "JUG"

                                nombre = normalizar_nombre(nombre)

                                if not nombre:
                                    continue

                                datos_jugador = obtener_datos_jugador(nombre, equipo)
                                posicion_real = str(datos_jugador.get("pos", posicion)).upper()

                                if nombre not in stats:
                                    stats[nombre] = crear_registro(
                                        nombre=nombre,
                                        equipo=equipo,
                                        posicion=posicion_real,
                                        competicion=nombre_competicion,
                                    )

                                stats[nombre]["Equipo"] = equipo
                                stats[nombre]["Pos"] = posicion_real
                                stats[nombre]["PJ"] += 1

                        # Leer estadísticas desde las notas
                        for nota in notas:
                            print("DEBUG NOTA:", nota)  # <-- AÑADE ESTO
                            nombre = nota.get("Jugador", "") or nota.get("jugador", "") or nota.get("nombre", "")
                            nombre = normalizar_nombre(nombre)

                            if not nombre:
                                continue

                            equipo_nota = nota.get("Equipo", "") or local

                            datos_jugador = obtener_datos_jugador(nombre, equipo_nota)
                            posicion = str(datos_jugador.get("pos", "JUG")).upper()

                            if nombre not in stats:
                                stats[nombre] = crear_registro(
                                    nombre=nombre,
                                    equipo=equipo_nota,
                                    posicion=posicion,
                                    competicion=nombre_competicion,
                                )

                            if stats[nombre]["PJ"] == 0:
                                stats[nombre]["PJ"] = 1

                            stats[nombre]["Minutos"] += nota.get("Minutos", 0) or 90
                            stats[nombre]["Nota"] += nota.get("Nota", 0) or nota.get("valoracion", 0)
                            stats[nombre]["Notas_contadas"] += 1
                            stats[nombre]["Goles"] += nota.get("Goles", 0)
                            stats[nombre]["Asistencias"] += nota.get("Asistencias", 0)
                            stats[nombre]["Encajados"] += nota.get("Encajados", 0) or nota.get("goles_encajados", 0)


    # Calcular encajados para porteros (FUERA del bucle for nota)
    for datos in stats.values():
        if datos["Pos"] == "POR":
            jugador = obtener_datos_jugador(datos["Nombre"], datos["Equipo"])
            datos["Encajados"] = jugador.get("goles_encajados", 0)
        else:
            datos["Encajados"] = 0


    if not stats:
        return pd.DataFrame()

    for datos in stats.values():
        if datos["Notas_contadas"] > 0:
            datos["Nota"] = round(datos["Nota"] / datos["Notas_contadas"], 2)
        else:
            datos["Nota"] = 0.0

    df = pd.DataFrame(list(stats.values()))

    columnas_numericas = ["Goles", "Asistencias", "PJ", "Minutos", "Nota", "Encajados"]
    for columna in columnas_numericas:
        if columna not in df.columns:
            df[columna] = 0

    df["ValorNum"] = df["Goles"] * 2 + df["Asistencias"]

    return df

def avanzar_ronda_europa(competicion):
    eliminatorias = competicion.get("eliminatorias", [])

    if not eliminatorias:
        return

    ronda_actual = eliminatorias[-1]
    ganadores = [
        cruce["ganador"]
        for cruce in ronda_actual["cruces"]
        if cruce.get("ganador")
    ]

    if len(ganadores) < 2:
        return

    nombre_ronda = ronda_actual["ronda"]

    siguientes = {
        "octavos": "cuartos",
        "cuartos": "semifinales",
        "semifinales": "final",
    }

    siguiente_ronda = siguientes.get(nombre_ronda)
    if siguiente_ronda is None:
        return

    cruces = []

    if siguiente_ronda == "final":
        if len(ganadores) == 2:
            cruces.append(
                _crear_cruce_europa(
                    ganadores[0],
                    ganadores[1],
                    ida_vuelta=False
                )
            )
    else:
        for i in range(0, len(ganadores) - 1, 2):
            cruces.append(
                _crear_cruce_europa(
                    ganadores[i],
                    ganadores[i + 1],
                    ida_vuelta=True
                )
            )

    if cruces:
        competicion["eliminatorias"].append({
            "ronda": siguiente_ronda,
            "cruces": cruces
        })


def _ronda_actual_europa(competicion):
    eliminatorias = competicion.get("eliminatorias", [])
    if not eliminatorias:
        return None
    return eliminatorias[-1]


def _ronda_completa_europa(competicion):
    ronda = _ronda_actual_europa(competicion)

    if not ronda:
        return False

    for cruce in ronda.get("cruces", []):
        if ronda["ronda"] == "final":
            if not cruce.get("ganador"):
                return False
        elif not cruce.get("ganador"):
            return False

    return True


def render_pestana_europa():
    db = st.session_state.db


    st.title("🏆 Europa")


    europa = db.get("europa", {})
    if not europa:
        st.info(
            "Todavía no hay competiciones europeas. "
            "Se crearán al pasar de la primera a la segunda temporada."
        )
        return


    categoria_visible = st.radio(
        "Categoría",
        ["Senior", "Sub-19"],
        horizontal=True,
        key="europa_categoria"
    )


    categoria = (
        "senior"
        if categoria_visible == "Senior"
        else "sub19"
    )


    competiciones = europa.get(categoria, {})


    if not competiciones:
        st.info(
            f"No hay competiciones europeas de {categoria_visible} "
            "para esta temporada."
        )
        return


    nombres = {
        "champions": "Champions",
        "europa_league": "Europa League",
        "conference": "Conference",
    }


    disponibles = [
        clave for clave in nombres
        if clave in competiciones
    ]


    if not disponibles:
        st.info("No hay competiciones disponibles.")
        return


    competicion_key = st.selectbox(
        "Competición",
        disponibles,
        format_func=lambda clave: nombres[clave],
        key=f"europa_comp_{categoria}"
    )


    competicion = competiciones[competicion_key]


    st.subheader(competicion.get("nombre", nombres[competicion_key]))


    st.write(
        f"Equipos clasificados: "
        f"{len(competicion.get('equipos', []))}"
    )


    with st.expander("Ver equipos clasificados"):
        for equipo in competicion.get("equipos", []):
            st.write(f"- {equipo}")


    if not competicion.get("eliminatorias"):
        if len(competicion.get("equipos", [])) < 4:
            st.warning(
                "No hay suficientes equipos para crear esta competición."
            )
            return


        if st.button(
            "Crear eliminatorias",
            key=f"crear_elim_{categoria}_{competicion_key}"
        ):
            competicion["eliminatorias"] = generar_eliminatorias_europa(competicion)
            st.rerun()


        return


    ronda = _ronda_actual_europa(competicion)


    for idx, cruce in enumerate(ronda.get("cruces", [])):
        es_final = ronda["ronda"] == "final"
        _pintar_partido_europa(cruce, ronda, idx, categoria, competicion_key, es_final=es_final)


    if _ronda_completa_europa(competicion):
        if ronda["ronda"] == "final":
            st.success(
                f"🏆 Campeón de la competición: {ronda['cruces'][0]['ganador']}"
            )
        else:
            if st.button(
                "Avanzar a la siguiente ronda",
                key=f"avanzar_{categoria}_{competicion_key}"
            ):
                avanzar_ronda_europa(competicion)
                st.rerun()


    # ============================================================
    # ESTADÍSTICAS EUROPA
    # ============================================================
    st.divider()
    st.subheader("📊 Estadísticas europeas")

    # Obtener categoría visible (Senior o Sub-19)
    categoria_visible = st.session_state.get("europa_categoria", "Senior")

    dfj = todos_los_jugadores_de_europa()

    if not dfj.empty:
        # Filtrar por la categoría visible
        dfj = dfj[dfj["Competicion"].str.contains(categoria_visible, case=False, na=False)]

        tabs_stats = st.tabs(["Champions", "Europa League", "Conference"])

        for tab, competicion in zip(tabs_stats, ["Champions", "Europa League", "Conference"]):
            with tab:
                df_comp = dfj[dfj["Competicion"].str.contains(competicion, case=False, na=False)]
                
                if df_comp.empty:
                    st.info(f"Aún no hay estadísticas de {competicion} {categoria_visible}.")
                else:
                    df_comp["Goles/Partido"] = df_comp.apply(lambda r: round(r["Goles"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
                    c1, c2, c3, c4 = st.columns(4)

                    with c1:
                        st.markdown("👟 Goles")
                        st.dataframe(
                            df_comp.sort_values(["Goles", "Goles/Partido", "PJ"], ascending=[False, False, True])[
                                ["Nombre", "Pos", "Equipo", "Goles", "Goles/Partido", "PJ", "Minutos", "Nota"]
                            ],
                            hide_index=True,
                            use_container_width=True,
                        )

                    with c2:
                        st.markdown("🎯 Asistencias")
                        st.dataframe(
                            df_comp.sort_values(["Asistencias", "PJ", "Minutos"], ascending=[False, True, True])[
                                ["Nombre", "Pos", "Equipo", "Asistencias", "PJ", "Minutos", "Nota"]
                            ],
                            hide_index=True,
                            use_container_width=True,
                        )

                    with c3:
                        st.markdown("⭐ Mejores notas")
                        st.dataframe(
                            df_comp.sort_values(["Nota", "PJ", "Minutos"], ascending=[False, False, False])[
                                ["Nombre", "Pos", "Equipo", "Nota", "PJ", "Minutos", "Goles", "Asistencias"]
                            ],
                            hide_index=True,
                            use_container_width=True,
                        )

                    with c4:
                        st.markdown("🧤 Porteros")
                        por = df_comp[df_comp["Pos"] == "POR"].copy()
                        if not por.empty:
                            por["Promedio Encajados"] = por.apply(lambda r: round(r["Encajados"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
                            por["Minuto/Goles"] = por.apply(lambda r: round(r["Minutos"] / r["Encajados"], 2) if r["Encajados"] > 0 else 0, axis=1)
                            st.dataframe(
                                por.sort_values(["Promedio Encajados", "PJ"], ascending=[True, False])[
                                    ["Nombre", "Equipo", "Encajados", "PJ", "Minutos", "Promedio Encajados", "Minuto/Goles", "Nota"]
                                ],
                                hide_index=True,
                                use_container_width=True,
                            )
                        else:
                            st.info("Sin porteros")

                    st.divider()
                    st.markdown("#### Todos los jugadores")
                    st.dataframe(
                        df_comp.sort_values(["Equipo", "ValorNum", "Nombre"], ascending=[True, False, True]),
                        hide_index=True,
                        use_container_width=True,
                    )
    else:
        st.info("Aún no hay estadísticas europeas.")

def main():
    init_db()
    db = st.session_state.db
    
    # Crear las Copas también en la Temporada 1.
    if (
        "copas" not in db
        or db["copas"].get("temporada") != db["config"]["temporada"]
        or "Principal" not in db["copas"]
    ):
        crear_copas_temporada(
            db,
            db["config"]["temporada"],
        )

    st.title("🏆 Manager Pro")
    st.caption(f"Temporada {db['config']['temporada']}")

    with st.sidebar:
        st.header("⚙️ Gestión")
        json_str = json.dumps(db, indent=2, ensure_ascii=False)
        st.download_button("💾 Guardar Partida", json_str, "manager_save.json", "application/json")

        st.file_uploader("📂 Cargar Partida", type=["json"], key="uploader_partida", on_change=cargar_partida_callback)

        if st.session_state.get("partida_cargada_ok"):
            st.success("✅ Partida cargada correctamente")
            st.session_state.partida_cargada_ok = False

        # 1) Selector de país
        pais_sel = st.selectbox(
            "País",
            list(PANELES_PAISES.keys()),
            key="selector_pais"
        )

        # 2) Ligas disponibles de ese país que existan en la DB
        ligas_pais = [l for l in PANELES_PAISES[pais_sel] if l in db["ligas"]]

        if not ligas_pais:
            st.warning("Este país  aún no tiene ligas definidas.")
            return

        liga_activa = st.selectbox(
            "Liga activa",
            ligas_pais,
            index=ligas_pais.index(db["config"]["liga_activa"]) if db["config"]["liga_activa"] in ligas_pais else 0,
            key="selector_liga"
        )

        db["config"]["liga_activa"] = liga_activa

        if st.button("📅 Generar Calendarios (Todas)"):
            for nombre_liga in mis_ligas:

                if nombre_liga in db["ligas"]:
                    eqs = db["ligas"][nombre_liga]["equipos"]
                    db["ligas"][nombre_liga]["calendario"] = generar_calendario(eqs)
                    db["ligas"][nombre_liga]["jornada"] = 0
                    db["ligas"][nombre_liga]["resultados"] = []

                    for e in eqs:
                        for p in db["equipos_data"][e]["jugadores"]:
                            p["goles"] = 0
                            p["asistencias"] = 0
                            p["amarillas"] = 0
                            p["rojas"] = 0
                            p["partidos"] = 0
                            p["partidos_titular"] = 0
                            p["minutos_totales"] = 0
                            p["nota_total"] = 0
                            p["goles_encajados"] = 0
                            p["cansancio"] = 0
                            p["equipo_actual"] = e

            recargar()

        if st.button("🆕 Nueva Partida"):
            st.session_state.db = copy.deepcopy(DATOS_INICIALES)
            preparar_db_cargada(st.session_state.db)
            asegurar_2a_division_operativa()
            inicializar_presupuestos()
            recargar()

        if st.button("🔄”„ Iniciar Nueva Temporada"):
            cerrar_temporada_y_preparar_siguiente()
            recargar()

    liga_activa = db["config"]["liga_activa"]

    # Convocatorias manuales para Cerezas (ahora en pestaña)
    # st.subheader("📋 Convocatorias manuales")
    # equipos_cerezas = ["CEREZAS", "CEREZAS B", "CEREZAS Sub-19"]
    # for eq in equipos_cerezas:
    #     if eq not in db["equipos_data"]:
    #         continue
    #     panel_convocatoria_manual(eq, db)

    dat_liga = obtener_liga_data(liga_activa)

    tabs = st.tabs([
        "📊 Clasificación", "📋 Convocatorias", "⚽ Jornada", "📈 Stats", "🛡️ Clubes",
        "👤 Perfil", "🏆 Historial", "💸 Mercado", "📜 Traspasos", "Europa", "Copas", "Stats Copa"
    ])

    with tabs[0]:
        st.subheader(f"Clasificación - {liga_activa}")
        df = clasificacion_liga(dat_liga)

        if not df.empty:
            def pintar_filas(row):
                nombre = row.name
                estilos = [""] * len(row)

                if liga_activa == "1ª División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(3).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "2ª División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[2:6].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(4).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "3ª División Grupo A":
                    if nombre in df.head(1).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[1:5].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "3ª División Grupo B":
                    if nombre in df.head(1).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[1:5].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "4ª División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                # === LIGAS NACIONALES SENIOR ===
                elif liga_activa == "Com 1ª División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Com 2ª División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                elif liga_activa == "Tengu 1ª División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Tengu 2ª División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                elif liga_activa == "Folimón 1ª División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Folimón 2ª División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                # === LIGAS NACIONALES SUB-19 ===
                elif liga_activa == "Com Sub-19 1 División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Com Sub-19 2 División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                elif liga_activa == "Tengu Sub-19 1 División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Tengu Sub-19 2 División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                elif liga_activa == "Folimón Sub-19 1 División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(2).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Folimón Sub-19 2 División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)

                elif liga_activa == "Sub-19 1 División":
                    if nombre in df.head(4).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[4:6].index.tolist():
                        estilos = ["background-color: #d1ecf1; color: #0c5460;"] * len(row)
                    elif nombre in df.iloc[6:8].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(3).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Sub-19 2 División":
                    if nombre in df.head(2).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[2:6].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)
                    elif nombre in df.tail(4).index.tolist():
                        estilos = ["background-color: #f8d7da; color: #721c24;"] * len(row)

                elif liga_activa == "Sub-19 3 División Grupo A":
                    if nombre in df.head(1).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[1:5].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)

                elif liga_activa == "Sub-19 3 División Grupo B":
                    if nombre in df.head(1).index.tolist():
                        estilos = ["background-color: #d4edda; color: #155724;"] * len(row)
                    elif nombre in df.iloc[1:5].index.tolist():
                        estilos = ["background-color: #fff3cd; color: #856404;"] * len(row)

                return estilos


            styled = (
                df.style
                .apply(pintar_filas, axis=1)
                .format({"Pts": "{:.0f}", "PJ": "{:.0f}", "PG": "{:.0f}", "PE": "{:.0f}", "PP": "{:.0f}",
                         "GF": "{:.0f}", "GC": "{:.0f}", "DG": "{:.0f}"})
            )
            st.dataframe(styled, use_container_width=True)
            
    with tabs[1]:  # Convocatorias
        st.subheader("📋 Convocatorias manuales")

        equipos_cerezas = [
            "CEREZAS",
            "CEREZAS B",
            "CEREZAS Sub-19",
            "RB Zerkas",
            "RB Zerkas B",
            "RB Zerkas Sub-19",
            "EKIPO",
            "EKIPO Sub-19",
        ]

        for eq in equipos_cerezas:
            if eq not in db["equipos_data"]:
                continue
            panel_convocatoria_manual(eq, db)

    with tabs[2]:
        st.subheader("⚽️ Jornada")

        if not dat_liga["calendario"]:
            st.info("No hay calendario generado para esta liga.")
        else:
            jor_max = len(dat_liga["calendario"])
            jornada_actual = int(dat_liga.get("jornada", 0))
            proxima_jornada = min(jornada_actual + 1, jor_max)
            if proxima_jornada <= 0:
                proxima_jornada = 1

            jor_view = st.slider(
                "Selecciona Jornada:",
                1,
                jor_max,
                proxima_jornada,
                key=f"slider_liga_{liga_activa}"
            )

            equipos_incumplen = set(equipos_incumpliendo_porteria(liga_activa))

            for equipo in dat_liga["equipos"]:
                alerta = db["equipos_data"][equipo].get("alerta_porteria", {})
                if alerta.get("activa"):
                    restantes = alerta["jornada_limite"] - int(
                        db["equipos_data"][equipo].get("control_jornada_porteros", 0)
                    )

                    if equipo in equipos_incumplen:
                        st.error(
                            f"🚨 {equipo} sigue con 1 solo portero y ya ha agotado el plazo. "
                            f"Debe fichar o ascender a otro inmediatamente."
                        )
                    else:
                        st.warning(
                            f"⚠️ {equipo} tiene 1 solo portero. "
                            f"Quedan {max(0, restantes)} jornadas para fichar o ascender a otro."
                        )

            with st.expander("DEBUG PORTEROS"):
                debug_porteros = []
                for equipo in dat_liga["equipos"]:
                    alerta = db["equipos_data"][equipo].get("alerta_porteria", {})
                    debug_porteros.append({
                        "equipo": equipo,
                        "porteros": contar_porteros(equipo),
                        "control_jornada_porteros": db["equipos_data"][equipo].get("control_jornada_porteros", 0),
                        "alerta_activa": alerta.get("activa", False),
                        "jornada_inicio": alerta.get("jornada_inicio"),
                        "jornada_limite": alerta.get("jornada_limite"),
                        "incumple": equipo_necesita_regularizar_porteria(equipo),
                    })
                st.dataframe(pd.DataFrame(debug_porteros), hide_index=True, use_container_width=True)

            # Mostrar info de la jornada seleccionada (solo visual)
            if jor_view > jornada_actual + 1:
                st.warning("Debes jugar las jornadas en orden.")

            elif jor_view <= jornada_actual:
                st.success(f"✅ Resultados Jornada {jor_view}")
                partidos = [r for r in dat_liga["resultados"] if r.get("jornada_num") == jor_view]

                if not partidos:
                    ppj = max(1, len(dat_liga["equipos"]) // 2)
                    ini = (jor_view - 1) * ppj
                    fin = ini + ppj
                    partidos = dat_liga["resultados"][ini:fin]

                for r in partidos:
                    with st.expander(f"{r['local']} {r['goles1']} - {r['goles2']} {r['visitante']}"):
                        c1, c2 = st.columns(2)
                        c1.markdown(f"**{r['local']}**")
                        c1.caption(f"11: {r.get('alineacion1', '-')}")
                        c2.markdown(f"**{r['visitante']}**")
                        c2.caption(f"11: {r.get('alineacion2', '-')}")
                        st.divider()

                        for ev in sorted(r.get("eventos", []), key=lambda x: x.get("min", 0)):
                            st.write(f"**{ev.get('min', 0)}'** {ev.get('texto', '')}")

                        st.divider()
                        notas = r.get("notas_partido", [])
                        if notas:
                            st.dataframe(pd.DataFrame(notas), hide_index=True, use_container_width=True)

            else:
                st.info(f"📄 Próxima Jornada: {jor_view}")
                partidos_jornada = dat_liga["calendario"][jor_view - 1]

                for p in partidos_jornada:
                    st.write(f"🔹 {p[0]} vs {p[1]}")

            # Botón que SIEMPRE simula la PRÓXIMA jornada (jornada_actual + 1)
            if st.button("▶️ SIMULAR ESTA JORNADA", type="primary", key=f"sim_jornada_{liga_activa}"):
                j_sim = st.session_state.db["ligas"][liga_activa]["jornada"] + 1

                # Actualizar lesiones una sola vez por jornada
                actualizar_lesiones_jornada(j_sim)

                if j_sim <= jor_max:
                    partidos_jornada = dat_liga["calendario"][j_sim - 1]
                    for local, visitante in partidos_jornada:
                        res = simular_partido(local, visitante, jornada_actual=j_sim)
                        res["jornada_num"] = j_sim
                        st.session_state.db["ligas"][liga_activa]["resultados"].append(res)

                    avanzar_control_porteros_liga(liga_activa)

                    for eq in equipos_incumpliendo_porteria(liga_activa):
                        ok, msg = intentar_regularizar_porteria_desde_cantera(eq)
                        if msg:
                            db["mercado_log"].append(msg)

                    st.session_state.db["ligas"][liga_activa]["jornada"] = j_sim

                    if mercado_abierto_en_jornada(j_sim):
                        mercado_automatico()

                    gestion_cantera_ia(j_sim)
                    promocion_automatica_por_media()

                st.rerun()

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "2ª División",
            "playoff_2a",
            "slider_playoff_2a",
            "sim_playoff_2a_"
        )

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "3ª División Grupo A",
            "playoff_3a_grupo_a",
            "slider_playoff_3a_a",
            "sim_playoff_3a_a_"
        )

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "3ª División Grupo B",
            "playoff_3a_grupo_b",
            "slider_playoff_3a_b",
            "sim_playoff_3a_b_"
        )

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "Sub-19 2 División",
            "playoff_sub19_2a",
            "slider_playoff_sub19_2a",
            "sim_playoff_sub19_2a_"
        )

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "Sub-19 3 División Grupo A",
            "playoff_sub19_3agrupoa",
            "slider_playoff_sub19_3a_a",
            "sim_playoff_sub19_3a_a_"
        )

        mostrar_playoff_streamlit(
            db,
            liga_activa,
            "Sub-19 3 División Grupo B",
            "playoff_sub19_3agrupob",
            "slider_playoff_sub19_3a_b",
            "sim_playoff_sub19_3a_b_"
        )

    with tabs[3]:
        st.subheader("📈 Estadí­sticas")
        dfj = todos_los_jugadores_de_liga(liga_activa)
        if not dfj.empty:
            dfj["Goles/Partido"] = dfj.apply(lambda r: round(r["Goles"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.markdown("👟 Goles")
                st.dataframe(
                    dfj.sort_values(["Goles", "Goles/Partido", "PJ"], ascending=[False, False, True])[
                        ["Nombre", "Nacionalidad", "Pos", "Equipo", "Goles", "Goles/Partido", "PJ", "Titular", "Minutos", "Nota"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c2:
                st.markdown("🎯 Asistencias")
                st.dataframe(
                    dfj.sort_values(["Asistencias", "PJ", "Minutos"], ascending=[False, True, True])[
                        ["Nombre", "Nacionalidad", "Pos", "Equipo", "Asistencias", "PJ", "Titular", "Minutos", "Nota"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c3:
                st.markdown("⭐️ Mejores notas")
                st.dataframe(
                    dfj.sort_values(["Nota", "PJ", "Minutos"], ascending=[False, False, False])[
                        ["Nombre", "Nacionalidad", "Pos", "Equipo", "Nota", "PJ", "Titular", "Minutos", "Goles", "Asistencias"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c4:
                st.markdown("🧤 Porteros")
                por = dfj[dfj["Pos"] == "POR"].copy()
                if not por.empty:
                    por["Promedio Encajados"] = por.apply(lambda r: round(r["Encajados"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
                    por["Minuto/Goles"] = por.apply(lambda r: round(r["Minutos"] / r["Encajados"], 2) if r["Encajados"] > 0 else 0, axis=1)
                    st.dataframe(
                        por.sort_values(["Promedio Encajados", "PJ"], ascending=[True, False])[
                            ["Nombre", "Nacionalidad", "Pos", "Equipo", "Encajados", "PJ", "Minutos", "Promedio Encajados", "Minuto/Goles", "Nota"]
                        ],
                        hide_index=True,
                        use_container_width=True
                    )

            st.divider()
            st.markdown("#### Todos los jugadores")
            st.dataframe(dfj.sort_values(["Equipo", "ValorNum", "Nombre"], ascending=[True, False, True]), hide_index=True, use_container_width=True)
        else:
            st.info("Sin datos.")

    with tabs[4]:
        st.subheader("🛡️ Clubes")
        eq = st.selectbox("Equipo", dat_liga["equipos"])

        datos_eq = obtener_equipo_data(eq)

        st.write(f"**Liga:** {datos_eq.get('liga', '-')}")
        st.write(f"**Presupuesto:** {formatear_valor(datos_eq.get('presupuesto', 0))}")

        dfeq = equipo_stats_tabla(eq)

        st.dataframe(
            dfeq.sort_values("ValorNum", ascending=False),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Valor": st.column_config.NumberColumn(
                    "Valor",
                    format="%.1f M€"
                )
            }
        )

        # ----------------------------------------------
        # GESTIÓN DE TRANSFERIBLES / CEDIBLES (TUS CLUBES)
        # ----------------------------------------------
        clubes_usuario = {
            "CEREZAS",
            "CEREZAS B",
            "CEREZAS Sub-19",
            "RB Zerkas",
            "RB Zerkas B",
            "RB Zerkas Sub-19",
            "EKIPO",
            "EKIPO Sub-19",
        }

        if eq in clubes_usuario:
            st.divider()
            st.markdown("#### 📤 Gestión de transferibles / cedibles")

            plantilla = datos_eq.get("jugadores", [])

            if plantilla:
                # Resumen rápido
                n_transferibles = sum(1 for j in plantilla if j.get("transferible", False))
                n_cedibles = sum(1 for j in plantilla if j.get("cedible", False))

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.metric("Jugadores transferibles", n_transferibles)
                with col_res2:
                    st.metric("Jugadores cedibles", n_cedibles)

                st.caption(
                    "Marca a los jugadores que quieras que reciban más ofertas de traspaso o cesión."
                )

                for j in plantilla:
                    cols = st.columns([3, 1, 1])

                    with cols[0]:
                        st.write(
                            f"**{j['nombre']}** "
                            f"({j.get('pos', 'JUG')}, "
                            f"media={j.get('media', 0)}, "
                            f"edad={j.get('edad', 20)})"
                        )

                    with cols[1]:
                        transferible = st.checkbox(
                            "Transferible",
                            value=j.get("transferible", False),
                            key=f"transferible_{eq}_{j['nombre']}"
                        )
                        if transferible != j.get("transferible", False):
                            j["transferible"] = transferible

                    with cols[2]:
                        cedible = st.checkbox(
                            "Cedible",
                            value=j.get("cedible", False),
                            key=f"cedible_{eq}_{j['nombre']}"
                        )
                        if cedible != j.get("cedible", False):
                            j["cedible"] = cedible
            else:
                st.info(f"{eq} no tiene jugadores en la plantilla.")

        # ----------------------------------------------
        # PRESUPUESTO Y MOVIMIENTOS DEL CLUB
        # ----------------------------------------------
        st.divider()
        render_presupuesto_club(eq)

        st.divider()
        # ----------------------------------------------
        # JUGADORES CEDIDOS A OTROS EQUIPOS
        # ----------------------------------------------
        st.markdown("#### 🔁 Jugadores cedidos a otros equipos")

        jugadores_cedidos = []

        # El propietario es el club que cede al jugador.
        # El jugador se encuentra físicamente en la plantilla del equipo destino.
        for equipo_actual, datos_equipo_actual in db["equipos_data"].items():
            for jugador in datos_equipo_actual.get("jugadores", []):
                if not jugador.get("cedido", False):
                    continue

                propietario = jugador.get("propietario")

                # Solo mostrar los jugadores cuyo propietario sea el equipo seleccionado.
                if propietario != eq:
                    continue

                # Evitar mostrar datos incoherentes o una cesión interna.
                if equipo_actual == eq:
                    continue

                partidos = jugador.get("partidos", 0)
                nota_total = jugador.get("nota_total", 0)

                nota_media = (
                    round(nota_total / partidos, 2)
                    if partidos > 0
                    else 0
                )

                jugadores_cedidos.append({
                    "Nombre": jugador.get("nombre", ""),
                    "Pos": jugador.get("pos", "JUG"),
                    "Edad": jugador.get("edad", 0),
                    "Media": jugador.get("media", 0),
                    "Valor": jugador.get("valor", 0),
                    "Cedido en": equipo_actual,
                    "Hasta": jugador.get("cedido_hasta", 0),
                    "Partidos": partidos,
                    "Titular": jugador.get("partidos_titular", 0),
                    "Minutos": jugador.get("minutos_totales", 0),
                    "Goles": jugador.get("goles", 0),
                    "Asistencias": jugador.get("asistencias", 0),
                    "Amarillas": jugador.get("amarillas", 0),
                    "Rojas": jugador.get("rojas", 0),
                    "Nota": nota_media,
                })

        if jugadores_cedidos:
            df_cedidos = pd.DataFrame(jugadores_cedidos)

            st.dataframe(
                df_cedidos.sort_values(
                    ["Media", "Nombre"],
                    ascending=[False, True]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Media": st.column_config.NumberColumn(
                        "Media",
                        format="%.0f"
                    ),
                    "Valor": st.column_config.NumberColumn(
                        "Valor",
                        format="%.1f M€"
                    ),
                    "Nota": st.column_config.NumberColumn(
                        "Nota",
                        format="%.2f"
                    ),
                }
            )
        else:
            st.info(f"{eq} no tiene jugadores cedidos actualmente.")

        st.divider()
        st.markdown("#### Historial del club")

        historial_club = []

        for nombre_liga, liga in db.get("ligas", {}).items():
            historial_club.extend(liga.get("historial_clubes", {}).get(eq, []))

        for nombre_liga, liga in db.get("ligas_data_sub19", {}).items():
            historial_club.extend(liga.get("historial_clubes", {}).get(eq, []))

        if historial_club:
            st.dataframe(
                pd.DataFrame(historial_club).sort_values("temporada", ascending=False),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Este club aún no tiene historial guardado.")

        st.divider()
        st.markdown("#### Historial de traspasos")

        ht = db.get("historial_traspasos", [])

        if ht:
            df_ht = pd.DataFrame(ht)

            col_origen = next((c for c in ["origen", "equipo_origen", "from", "club_origen"] if c in df_ht.columns), None)
            col_destino = next((c for c in ["destino", "equipo_destino", "to", "club_destino"] if c in df_ht.columns), None)
            col_temporada = next((c for c in ["temporada", "season"] if c in df_ht.columns), None)
            col_jugador = next((c for c in ["jugador", "nombre", "player"] if c in df_ht.columns), None)
            col_tipo = next((c for c in ["tipo", "movimiento"] if c in df_ht.columns), None)
            col_monto = next((c for c in ["monto", "importe", "precio", "valor"] if c in df_ht.columns), None)

            if col_origen or col_destino:
                # Obtener equipos vinculados del club seleccionado
                equipos_a_mostrar = [eq]
                if es_equipo_principal(eq):
                    # Si es primer equipo, añadir también sus filiales y Sub-19
                    for eq_vinc in db["equipos_data"].keys():
                        if obtener_club_principal(eq_vinc) == eq and eq_vinc != eq:
                            equipos_a_mostrar.append(eq_vinc)

                filtro = pd.Series(False, index=df_ht.index)
                if col_origen:
                    for equipo in equipos_a_mostrar:
                        filtro = filtro | (df_ht[col_origen] == equipo)
                if col_destino:
                    for equipo in equipos_a_mostrar:
                        filtro = filtro | (df_ht[col_destino] == equipo)

                df_club = df_ht[filtro].copy()

                if not df_club.empty:
                    columnas_mostrar = []
                    renombrar = {}

                    if col_temporada:
                        columnas_mostrar.append(col_temporada)
                        renombrar[col_temporada] = "Temporada"
                    if col_jugador:
                        columnas_mostrar.append(col_jugador)
                        renombrar[col_jugador] = "Jugador"
                    if col_tipo:
                        columnas_mostrar.append(col_tipo)
                        renombrar[col_tipo] = "Tipo"
                    if col_origen:
                        columnas_mostrar.append(col_origen)
                        renombrar[col_origen] = "Origen"
                    if col_destino:
                        columnas_mostrar.append(col_destino)
                        renombrar[col_destino] = "Destino"
                    if col_monto:
                        columnas_mostrar.append(col_monto)
                        renombrar[col_monto] = "Importe"
                        df_club[col_monto] = df_club[col_monto].apply(
                            lambda x: formatear_valor(x) if pd.notna(x) and isinstance(x, (int, float)) else x
                        )

                    df_club = df_club[columnas_mostrar].rename(columns=renombrar)

                    if "Temporada" in df_club.columns:
                        df_club = df_club.sort_values("Temporada", ascending=False)

                    st.dataframe(df_club, hide_index=True, use_container_width=True)
                else:
                    st.info("Este club aún no tiene traspasos registrados.")
            else:
                st.info("No se han encontrado columnas de origen/destino en el historial de traspasos.")
        else:
            st.info("Todavía no hay traspasos registrados.")

        # ----------------------------------------------
        # RENOVACIONES MANUALES DE TUS CLUBES VINCULADOS
        # ----------------------------------------------
        st.divider()
        st.markdown("#### 🔄 Renovar jugadores (tus clubes)")

        if eq in clubes_usuario:
            temporada_actual = db["config"]["temporada"]
            plantilla = datos_eq.get("jugadores", [])

            jugadores_vencidos = [
                j for j in plantilla
                if j.get("fin_contrato") == temporada_actual
            ]

            if not jugadores_vencidos:
                st.info(f"{eq}: no hay jugadores con contrato vencido en T{temporada_actual}")
            else:
                st.caption(
                    f"{eq}: {len(jugadores_vencidos)} jugadores con contrato vencido "
                    f"en T{temporada_actual}"
                )

                for jugador in jugadores_vencidos:
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

                    with col1:
                        st.write(
                            f"**{jugador['nombre']}** "
                            f"({jugador.get('pos', 'JUG')}, "
                            f"media={jugador.get('media', 0)}, "
                            f"edad={jugador.get('edad', 20)})"
                        )

                    with col2:
                        salario_actual = jugador.get("salario", 0)

                        # Calcular salario sugerido basado en la media ACTUAL del jugador
                        sub19 = es_equipo_sub19(eq)
                        edad = jugador.get("edad", 20)
                        media_actual = jugador.get("media", 40)
                        salario_sugerido = calcular_salario_por_temporada(
                            media_actual,
                            edad,
                            sub19
                        )

                        st.write(f"Salario actual: {formatear_valor(salario_actual)}/temp.")
                        st.caption(f"Salario sugerido (por media {media_actual}): {formatear_valor(salario_sugerido)}/temp.")

                    with col3:
                        nuevo_salario = st.number_input(
                            "Nuevo salario (M€)",
                            min_value=0.0,
                            max_value=50.0,
                            value=float(salario_sugerido),
                            step=0.1,
                            key=f"renov_sal_{eq}_{jugador['nombre']}"
                        )

                    with col4:
                        duracion = st.number_input(
                            "Duración (temp.)",
                            min_value=1,
                            max_value=5,
                            value=2,
                            step=1,
                            key=f"renov_dur_{eq}_{jugador['nombre']}"
                        )

                    col_btn1, col_btn2 = st.columns([2, 1])

                    with col_btn1:
                        if st.button(
                            "Renovar",
                            key=f"btn_renovar_{eq}_{jugador['nombre']}",
                            type="primary"
                        ):
                            jugador["salario"] = nuevo_salario
                            jugador["fin_contrato"] = temporada_actual + duracion - 1

                            db.setdefault("mercado_log", []).append(
                                f"📝 {eq} renueva manualmente a {jugador['nombre']} "
                                f"hasta T{jugador['fin_contrato']} "
                                f"({duracion} temp., "
                                f"{formatear_valor(nuevo_salario)}/temp.)"
                            )
                            st.success(f"{jugador['nombre']} renovado hasta T{jugador['fin_contrato']}")
                            st.rerun()

                    with col_btn2:
                        if st.button(
                            "Dejar libre",
                            key=f"btn_liberar_{eq}_{jugador['nombre']}"
                        ):
                            st.info(f"{jugador['nombre']} quedará libre al cerrar la temporada.")
        else:
            st.info("Las renovaciones manuales solo están disponibles para tus clubes (CEREZAS y RB Zerkas).")

    with tabs[5]:
        st.subheader("👤 Perfil de Jugador")

        jugadores_activos = sorted(set(
            j["nombre"]
            for base in [db["equipos_data"], db.get("equipos_data_sub19", {})]
            for eq, edata in base.items()
            for j in edata["jugadores"]
        ))

        # Añadir jugadores libres (agentes libres)
        jugadores_libres_nombres = sorted(set(
            l["jugador"]["nombre"]
            for l in db.get("jugadores_libres", [])
        ))

        jugadores_retirados = sorted(set(
            j["nombre"] for j in db.get("jugadores_retirados", [])
        ))

        jugadores = sorted(set(jugadores_activos + jugadores_libres_nombres + jugadores_retirados))

        if not jugadores:
            st.info("No hay jugadores disponibles.")
        else:
            sel = st.selectbox("Selecciona jugador", jugadores)
            jugador, actual = perfil_jugador(sel)

            if jugador:
                c1, c2 = st.columns(2)

                with c1:
                    st.write(f"**Equipo actual:** {actual['equipo_actual']}")
                    st.write(f"**Posición:** {actual['posicion']}")
                    st.write(f"**Edad:** {actual['edad']}")
                    st.write(f"**Nacionalidad:** {jugador.get('banderas', '🏳️')} {jugador.get('nacionalidades', '-')}")
                    st.write(f"**Media global:** {actual['media_global']}")
                    st.write(f"**Valor:** {formatear_valor(actual['valor'])}")
                    st.write(f"**Salario anual:** {formatear_valor(jugador.get('salario', 0))}")
                    st.write(f"**Fin de contrato:** Temporada {jugador.get('fin_contrato', '-')}")
                    st.write(f"**Partidos:** {actual['partidos']}")
                    st.write(f"**Partidos titular:** {actual['partidos_titular']}")
                    st.write(f"**Minutos totales:** {actual['minutos_totales']}")

                with c2:
                    st.write(f"**Goles:** {actual['goles']}")
                    st.write(f"**Asistencias:** {actual['asistencias']}")
                    st.write(f"**Amarillas:** {actual['amarillas']}")
                    st.write(f"**Rojas:** {actual['rojas']}")
                    st.write(f"**Goles encajados:** {actual['encajados']}")
                    st.write(f"**Nota media temporada:** {actual['media_actual']}")

                if actual.get("retirado"):
                    st.warning("Este jugador está retirado.")

                st.divider()

                if not actual.get("retirado"):
                    equipo_actual_jugador = actual["equipo_actual"]

                    if st.button("🛑 Retirar jugador"):
                        ok, msg = retirar_jugador_manual(jugador["nombre"], actual["equipo_actual"])
                        if ok:
                            st.success(msg)
                            recargar()
                        else:
                            st.error(msg)

                    # Clubs que gestionamos manualmente (CEREZAS y RB Zerkas)
                    clubes_gestionables = ["CEREZAS", "RB Zerkas", "EKIPO"]
                    club_principal = obtener_club_principal(equipo_actual_jugador)

                    if club_principal in clubes_gestionables:
                        # Determinar nombres dinámicos
                        primer_equipo = club_principal
                        filial = f"{club_principal} B"
                        sub19 = f"{club_principal} Sub-19"

                        st.markdown(f"#### Relación con estructura {club_principal}")
                        st.write(f"**Club principal asociado:** {club_principal}")
                        st.write(
                            f"**Promoción al primer equipo:** "
                            f"{'Sí' if jugador.get('promocion_temporal', False) else 'No'}"
                        )
                        st.write(
                            f"**Ficha del primer equipo:** "
                            f"{'Sí' if jugador.get('ficha_primer_equipo', False) else 'No'}"
                        )

                        if equipo_actual_jugador == sub19:
                            st.write(
                                f"**Ficha de {filial}:** "
                                f"{'Sí' if jugador.get('ficha_filial', False) else 'No'}"
                            )
                            siguiente_equipo = obtener_siguiente_equipo_por_edad(equipo_actual_jugador)
                            st.write(f"**Siguiente equipo natural:** {siguiente_equipo if siguiente_equipo else '-'}")

                        puede_prom = (
                            not jugador.get("cedido", False)
                            and not jugador.get("ficha_primer_equipo", False)
                            and not jugador.get("promocion_temporal", False)
                        )

                        puede_ficha = (
                            not jugador.get("cedido", False)
                            and not jugador.get("ficha_primer_equipo", False)
                            and not jugador.get("promocion_temporal", False)
                        )

                        puede_ascenso_filial = (
                            equipo_actual_jugador == sub19
                            and not jugador.get("cedido", False)
                            and obtener_siguiente_equipo_por_edad(equipo_actual_jugador) == filial
                        )

                        puede_ficha_filial = (
                            equipo_actual_jugador == sub19
                            and not jugador.get("cedido", False)
                            and not jugador.get("promocion_temporal", False)
                            and not jugador.get("ficha_filial", False)
                        )

                        puede_descender_a_b = (
                            equipo_actual_jugador == primer_equipo
                            and not jugador.get("cedido", False)
                            and jugador.get("equipo_actual") == primer_equipo
                            and filial in db["equipos_data"]
                        )

                        puede_descender_a_sub19 = (
                            equipo_actual_jugador == filial
                            and not jugador.get("cedido", False)
                            and jugador.get("equipo_actual") == filial
                        )

                        # Descensos
                        if equipo_actual_jugador == primer_equipo and puede_descender_a_b:
                            if st.button(
                                f"⬇️ Descender a {filial}",
                                key=f"descender_b_{club_principal}_{jugador['nombre']}"
                            ):
                                ok, msg = descender_jugador_a_filial(jugador["nombre"], primer_equipo, filial)
                                if ok:
                                    st.success(msg)
                                    recargar()
                                else:
                                    st.error(msg)

                        elif equipo_actual_jugador == filial and puede_descender_a_sub19:
                            if st.button(
                                f"⬇️ Descender a {sub19}",
                                key=f"descender_sub19_{club_principal}_{jugador['nombre']}"
                            ):
                                ok, msg = descender_jugador_a_sub19(jugador["nombre"], filial)
                                if ok:
                                    st.success(msg)
                                    recargar()
                                else:
                                    st.error(msg)

                        # Botones de promoción/fichas
                        if equipo_actual_jugador == sub19:
                            cfp1, cfp2, cfp3, cfp4 = st.columns(4)

                            with cfp1:
                                if st.button(
                                    f"🔼 Ascender a {filial}",
                                    key=f"asc_filial_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_ascenso_filial
                                ):
                                    ok, msg = ascender_jugador_al_siguiente_equipo(
                                        jugador["nombre"],
                                        equipo_actual_jugador
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                            with cfp2:
                                if st.button(
                                    f"🪪 Dar ficha de {filial}",
                                    key=f"ficha_filial_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_ficha_filial
                                ):
                                    ok, msg = dar_ficha_filial_a_jugador(
                                        jugador["nombre"],
                                        equipo_actual_jugador,
                                        filial
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                            with cfp3:
                                if st.button(
                                    f"🔼 Promocionar a {primer_equipo}",
                                    key=f"prom_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_prom
                                ):
                                    ok, msg = promocionar_jugador_a_primer_equipo(
                                        jugador["nombre"],
                                        equipo_actual_jugador
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                            with cfp4:
                                if st.button(
                                    f"🪪 Dar ficha de {primer_equipo}",
                                    key=f"ficha_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_ficha
                                ):
                                    ok, msg = dar_ficha_primer_equipo_a_jugador(
                                        jugador["nombre"],
                                        equipo_actual_jugador
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                        else:
                            cfp1, cfp2 = st.columns(2)

                            with cfp1:
                                if st.button(
                                    f"🔼 Promocionar a {primer_equipo}",
                                    key=f"prom_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_prom
                                ):
                                    ok, msg = promocionar_jugador_a_primer_equipo(
                                        jugador["nombre"],
                                        equipo_actual_jugador
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                            with cfp2:
                                if st.button(
                                    f"🪪 Dar ficha de {primer_equipo}",
                                    key=f"ficha_{club_principal}_{jugador['nombre']}",
                                    disabled=not puede_ficha
                                ):
                                    ok, msg = dar_ficha_primer_equipo_a_jugador(
                                        jugador["nombre"],
                                        equipo_actual_jugador
                                    )
                                    if ok:
                                        st.success(msg)
                                        recargar()
                                    else:
                                        st.error(msg)

                        # Captions informativas
                        if equipo_actual_jugador == sub19 and not puede_ascenso_filial:
                            st.caption(
                                f"El ascenso al filial no está disponible si no existe {filial} "
                                "o si el jugador está cedido."
                            )

                        if equipo_actual_jugador == sub19 and not puede_ficha_filial:
                            st.caption(
                                f"La ficha de {filial} no está disponible si el jugador ya la tiene, "
                                "está cedido o ya está promocionado."
                            )

                        if not puede_prom:
                            st.caption(
                                "La promoción no está disponible si el jugador ya está promocionado, "
                                "ya tiene ficha o está cedido."
                            )

                        if not puede_ficha:
                            st.caption(
                                "La ficha no está disponible si el jugador ya tiene ficha, "
                                "ya está promocionado o está cedido."
                            )

                    elif equipo_actual_jugador == "CEREZAS":
                        # Mantienes la gestión específica de CEREZAS si la quieres separada
                        st.markdown("#### Gestión de plantilla CEREZAS")

                        puede_descender_a_b = (
                            not jugador.get("cedido", False)
                            and jugador.get("equipo_actual") == "CEREZAS"
                            and "CEREZAS B" in db["equipos_data"]
                        )

                        if puede_descender_a_b:
                            if st.button(
                                "⬇️ Descender a CEREZAS B",
                                key=f"descender_b_cerezas_{jugador['nombre']}"
                            ):
                                ok, msg = descender_jugador_a_filial(jugador["nombre"], "CEREZAS", "CEREZAS B")
                                if ok:
                                    st.success(msg)
                                    recargar()
                                else:
                                    st.error(msg)
                        else:
                            st.caption(
                                "El descenso a CEREZAS B no está disponible si el jugador está cedido, "
                                "no pertenece a CEREZAS o no existe CEREZAS B."
                            )

                st.markdown("#### Historial por temporadas")
                hist = jugador.get("historial_temporadas", [])

                if not hist:
                    st.info("Aún no hay historial de temporadas para este jugador.")
                else:
                    # Agrupar por temporada
                    por_temporada = {}
                    for tramo in hist:
                        temp = tramo.get("temporada")
                        if temp is None:
                            continue
                        por_temporada.setdefault(temp, []).append(tramo)

                    # Ordenar temporadas de más reciente a más antigua
                    temporadas_ordenadas = sorted(por_temporada.keys(), reverse=True)

                    for temp in temporadas_ordenadas:
                        tramos = por_temporada[temp]

                        # Calcular totales de la temporada
                        total_partidos = sum(t.get("partidos", 0) for t in tramos)
                        total_goles = sum(t.get("goles", 0) for t in tramos)
                        total_asistencias = sum(t.get("asistencias", 0) for t in tramos)
                        total_minutos = sum(t.get("minutos", 0) for t in tramos)
                        nota_total = sum(t.get("nota_total", 0) for t in tramos)
                        media_temp = round(nota_total / total_partidos, 2) if total_partidos > 0 else 0

                        titulo = (
                            f"Temporada {temp} — "
                            f"{total_partidos} partidos, {total_goles} goles, "
                            f"{total_asistencias} asistencias, {media_temp} de media"
                        )

                        with st.expander(titulo):
                            # Construir filas por competición
                            filas = []
                            for t in tramos:
                                comp = t.get("competicion", "Liga")
                                
                                # Media inicial: media_final de la temporada anterior (si existe)
                                temp_actual = t.get("temporada")
                                media_inicial = None
                                if temp_actual is not None:
                                    # Buscar el tramo de la temporada anterior
                                    for tramo_prev in hist:
                                        if tramo_prev.get("temporada") == temp_actual - 1:
                                            media_inicial = tramo_prev.get("media_final")
                                            break
                                
                                # Si no hay media_inicial, usar media_final de este tramo
                                if media_inicial is None:
                                    media_inicial = t.get("media_final", jugador.get("media", 0))

                                filas.append({
                                    "Competición": comp,
                                    "Equipo": t.get("equipo", "-"),
                                    "División": t.get("division", "-"),  # <-- AÑADIDA
                                    "Partidos": t.get("partidos", 0),
                                    "Titular": t.get("partidos_titular", 0),
                                    "Minutos": t.get("minutos", 0),
                                    "Goles": t.get("goles", 0),
                                    "Asistencias": t.get("asistencias", 0),
                                    "Amarillas": t.get("amarillas", 0),
                                    "Rojas": t.get("rojas", 0),
                                    "Encajados": t.get("goles_encajados", 0),
                                    "Media": round(t.get("nota_total", 0) / t.get("partidos", 1), 2) if t.get("partidos", 0) > 0 else 0,
                                    "Media inicial": round(media_inicial, 1),  # <-- AÑADIDA
                                })

                            if filas:
                                st.dataframe(
                                    pd.DataFrame(filas),
                                    hide_index=True,
                                    use_container_width=True
                                )
                            else:
                                st.info("No hay datos por competición para esta temporada.")

                st.markdown("#### Historial de traspasos")
                htj = [
                    movimiento
                    for movimiento in db.get("historial_traspasos", [])
                    if movimiento.get("jugador") == jugador["nombre"]
                ]
                if htj:
                    st.dataframe(
                        pd.DataFrame(htj).sort_values("temporada", ascending=False),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Este jugador aún no tiene movimientos registrados.")

    with tabs[6]:
        st.subheader("🏆 Historial")

        hc = db.get("historial_campeones", [])
        if hc:
            st.dataframe(
                pd.DataFrame(hc).sort_values("temporada", ascending=False),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Todavía no hay campeones registrados.")

        st.markdown("#### Retiradas")
        hr = db.get("historial_retiradas", [])
        if hr:
            st.dataframe(
                pd.DataFrame(hr).sort_values("temporada", ascending=False),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Todavía no hay retiradas registradas.")

        st.markdown("### Movimientos divisionales")

        historial_movimientos = db.get("historial_movimientos", [])

        if historial_movimientos:
            movimientos_divisionales = [
                ev for ev in reversed(historial_movimientos)
                if "Asciende" in ev or "Desciende" in ev
            ]

            if movimientos_divisionales:
                for ev in movimientos_divisionales:
                    st.write(f"• {ev}")
            else:
                st.info("Todavía no hay movimientos divisionales registrados.")
        else:
            st.info("Todavía no hay movimientos divisionales registrados.")
        
    with tabs[7]:
        st.subheader("💸 Mercado de fichajes")

        jornada_actual = dat_liga.get("jornada", 0)
        fin_temporada = jornada_actual >= len(dat_liga.get("calendario", [])) if dat_liga.get("calendario") else False
        mercado_disponible = mercado_abierto_en_jornada(jornada_actual) or fin_temporada

        if mercado_disponible:
            if fin_temporada and not mercado_abierto_en_jornada(jornada_actual):
                st.success("Mercado abierto por final de temporada.")
            else:
                st.success(f"Mercado abierto en jornada {jornada_actual}.")

            # Generar ofertas automáticas para CEREZAS, RB Zerkas y EKIPO
            generar_ofertas_para_cerezas()
            generar_ofertas_para_cerezas_b()
            generar_ofertas_para_cerezas_sub19()
            generar_ofertas_para_rb_zerkas()
            generar_ofertas_para_rb_zerkas_b()
            generar_ofertas_para_rb_zerkas_sub19()
            generar_ofertas_para_ekipo()
            generar_ofertas_para_ekipo_sub19()

            # NUEVO: Mercado global para todos los demás clubes
            mercado_automatico_global(st.session_state.db)
            ejecutar_ofertas_ia(st.session_state.db)
        else:
            st.warning("Mercado cerrado. Solo se puede fichar en jornadas 1-5, 17-22 o al final de temporada.")

        # ─────────────────────────────────────────────────────────────
        #  EJECUTAR OPCIONES DE COMPRA MANUALES (CEREZAS / RB Zerkas / EKIPO y sus filiales)
        # ─────────────────────────────────────────────────────────────

        def ui_ejecutar_opciones_compra_equipo(equipo_nombre: str):
            st.subheader(f"🧠 Ejecutar opciones de compra – {equipo_nombre}")

            pendientes = []
            for eq, edata in db["equipos_data"].items():
                for idx, j in enumerate(edata["jugadores"]):
                    if not j.get("cedido", False):
                        continue
                    if not j.get("opcion_compra", False):
                        continue
                    # Solo jugadores que estén actualmente en este equipo
                    if j.get("equipo_actual") != equipo_nombre:
                        continue
                    if j.get("temporada_opcion_compra") is None:
                        continue
                    if db["config"]["temporada"] <= j["temporada_opcion_compra"]:
                        pendientes.append((eq, j, idx))

            if not pendientes:
                st.info(f"No hay opciones de compra pendientes para {equipo_nombre}.")
                return

            st.write("Jugadores con OP disponible:")

            for eq, j, idx in pendientes:
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

                with col1:
                    st.write(f"**{j['nombre']}** ({j['pos']}) – cedido hasta {j.get('cedido_hasta', '–')}")
                    st.caption(f"Media: {j.get('media', 0):.2f} | Edad: {j.get('edad', 0)} | Min: {j.get('minutos_totales', 0)}")

                with col2:
                    precio = float(j.get("precio_opcion_compra", 0))
                    st.write(f"Precio opción: **{precio:,.0f}€**")

                with col3:
                    presupuesto = obtener_presupuesto_equipo(eq)
                    st.write(f"Presupuesto {eq}: {presupuesto:,.0f}€")

                with col4:
                    key = f"opcion_compra_manual_{equipo_nombre}_{eq}_{idx}_{j['nombre'].replace(' ', '_')}_{j['equipo_actual']}"
                    if st.button("✅ Ejecutar", key=key):
                        if presupuesto < precio:
                            st.error(f"{eq} no tiene presupuesto suficiente para ejecutar esta opción.")
                        else:
                            ok, msg = ejecutar_opcion_compra(j, eq)
                            if ok:
                                db["mercado_log"].append(
                                    f"✅ Opción ejecutada manualmente: {j['nombre']} a {eq} por {precio:,.0f}€"
                                )
                                st.success(f"Opción ejecutada: {j['nombre']} se queda en {eq}.")
                                st.rerun()
                            else:
                                st.error(f"Error al ejecutar la opción: {msg}")

        # Opciones de compra para CEREZAS
        ui_ejecutar_opciones_compra_equipo("CEREZAS")
        ui_ejecutar_opciones_compra_equipo("CEREZAS B")
        ui_ejecutar_opciones_compra_equipo("CEREZAS Sub-19")

        # Opciones de compra para RB Zerkas
        ui_ejecutar_opciones_compra_equipo("RB Zerkas")
        ui_ejecutar_opciones_compra_equipo("RB Zerkas B")
        ui_ejecutar_opciones_compra_equipo("RB Zerkas Sub-19")

        # Opciones de compra para EKIPO
        ui_ejecutar_opciones_compra_equipo("EKIPO")
        ui_ejecutar_opciones_compra_equipo("EKIPO Sub-19")

        st.divider()

        todos_equipos = list(db["equipos_data"].keys())
        eq_origen = st.selectbox("Equipo origen", todos_equipos, key="merc_origen")
        jugadores_origen = [j["nombre"] for j in db["equipos_data"][eq_origen]["jugadores"]]
        jug_sel = st.selectbox("Jugador", jugadores_origen, key="merc_jug")
        eq_destino = st.selectbox("Equipo destino", [e for e in todos_equipos if e != eq_origen], key="merc_destino")

        jugador_obj = next(j for j in db["equipos_data"][eq_origen]["jugadores"] if j["nombre"] == jug_sel)
        precio_sugerido = calcular_precio_traspaso(jugador_obj, eq_origen, eq_destino)

        st.write(f"**Posición:** {jugador_obj['pos']}")
        st.write(f"**Valor base actual:** {formatear_valor(jugador_obj['valor'])}")
        st.write(f"**Precio sugerido de traspaso:** {formatear_valor(precio_sugerido)}")

        precio_traspaso = st.number_input(
            "Cantidad del traspaso (M€)",
            min_value=0.1,
            value=float(precio_sugerido),
            step=0.1,
            key="precio_traspaso"
        )

        precio_cesion = st.number_input(
            "Cantidad de la cesión (M€)",
            min_value=0.0,
            value=float(max(0.1, round(precio_sugerido * 0.12, 1))),
            step=0.1,
            key="precio_cesion"
        )

        duracion_cesion = st.number_input(
            "Duración de la cesión (temporadas)",
            min_value=1,
            max_value=5,
            value=1,
            step=1,
            key="duracion_cesion"
        )

        tipo_operacion = st.radio(
            "Tipo de operación",
            ["Traspaso", "Cesión sin opción", "Cesión con opción"],
            key="tipo_operacion_mercado",
            horizontal=True
        )

        precio_final = precio_traspaso
        duracion_final = 1
        opcion_compra = False
        precio_opcion = 0.0

        if tipo_operacion == "Cesión sin opción":
            precio_final = precio_cesion
            duracion_final = int(duracion_cesion)
        elif tipo_operacion == "Cesión con opción":
            precio_final = precio_cesion
            duracion_final = int(duracion_cesion)
            opcion_compra = True
            precio_opcion = st.number_input(
                "Precio de opción de compra (M€)",
                min_value=0.1,
                value=float(max(0.1, round(calcular_precio_traspaso(jugador_obj, eq_origen, eq_destino) * 0.95, 1))),
                step=0.1,
                key="precio_opcion_mercado"
            )

        if mercado_disponible and st.button("✅ Confirmar operación"):
            if tipo_operacion == "Traspaso":
                ok, msg = hacer_traspaso(jug_sel, eq_origen, eq_destino, monto=precio_final)
            else:
                ok, msg = hacer_cesion(
                    jug_sel,
                    eq_origen,
                    eq_destino,
                    monto=precio_final,
                    duracion=duracion_final,
                    opcion_compra=opcion_compra,
                    precio_opcion_compra=precio_opcion
                )
            if ok:
                st.success(msg)
                recargar()
            else:
                st.error(msg)

        st.divider()
        st.markdown("## Ofertas")

        # Función auxiliar para mostrar ofertas de un equipo
        def mostrar_ofertas_recibidas(equipo_nombre):
            st.markdown(f"### 📥 Ofertas recibidas por {equipo_nombre}")
            ofertas = [
                o for o in db.get("ofertas_pendientes", [])
                if o["origen"] == equipo_nombre and o["estado"] == "pendiente"
            ]

            if ofertas:
                for oferta in ofertas:
                    tipo_txt = "Traspaso"
                    if oferta.get("tipo") == "cesion":
                        if oferta.get("opcion_compra", False):
                            tipo_txt = "Cesión con OP"
                        else:
                            tipo_txt = "Cesión"

                    st.write(
                        f"**{tipo_txt}** – {oferta['destino']} ofrece {formatear_valor(oferta['cantidad'])} "
                        f"por {oferta['jugador']}"
                    )
                    if oferta.get("tipo") == "cesion":
                        duracion = oferta.get("duracion", 1)
                        st.caption(f"Duración: {duracion} temporada(s)")
                        if oferta.get("opcion_compra", False):
                            st.caption(f"Precio opción de compra: {formatear_valor(oferta.get('precio_opcion_compra', 0))}")

                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button(f"✅ Aceptar oferta {equipo_nombre}", key=f"aceptar_{equipo_nombre}_{oferta['id']}"):
                            ok, msg = aceptar_oferta(
                                oferta["id"],
                                forzar_usuario=True
                            )
                            if ok:
                                st.success(msg)
                                recargar()
                            else:
                                st.error(msg)

                    with c2:
                        if st.button(f"❌ Rechazar oferta {equipo_nombre}", key=f"rechazar_{equipo_nombre}_{oferta['id']}"):
                            ok, msg = rechazar_oferta(oferta["id"])
                            if ok:
                                st.info(msg)
                                recargar()
                            else:
                                st.error(msg)
            else:
                st.info(f"{equipo_nombre} no tiene ofertas recibidas pendientes.")

        # Ofertas recibidas para CEREZAS
        mostrar_ofertas_recibidas("CEREZAS")
        st.divider()
        mostrar_ofertas_recibidas("CEREZAS B")
        st.divider()
        mostrar_ofertas_recibidas("CEREZAS Sub-19")

        # Ofertas recibidas para RB Zerkas
        st.divider()
        mostrar_ofertas_recibidas("RB Zerkas")
        st.divider()
        mostrar_ofertas_recibidas("RB Zerkas B")
        st.divider()
        mostrar_ofertas_recibidas("RB Zerkas Sub-19")

        # Ofertas recibidas para EKIPO
        st.divider()
        mostrar_ofertas_recibidas("EKIPO")
        st.divider()
        mostrar_ofertas_recibidas("EKIPO Sub-19")

        st.divider()

        # Función auxiliar para hacer ofertas desde un equipo
        def hacer_oferta_desde_equipo(equipo_comprador):
            st.markdown(f"### 📤 Hacer oferta desde {equipo_comprador}")

            clubes_objetivo = [
                e for e in todos_equipos
                if e != equipo_comprador and not son_clubes_vinculados(e, equipo_comprador)
            ]
            club_vendedor = st.selectbox(
                f"Club al que quiere comprar {equipo_comprador}",
                clubes_objetivo,
                key=f"oferta_club_vendedor_{equipo_comprador.replace(' ', '_')}"
            )

            jugadores_vendedor = [
                j["nombre"] for j in db["equipos_data"][club_vendedor]["jugadores"]
                if not j.get("cedido", False)
            ]

            if not jugadores_vendedor:
                st.info(f"Ese club no tiene jugadores disponibles para ofertar a {equipo_comprador}.")
                return

            jugador_ofertado = st.selectbox(
                f"Jugador que quiere fichar {equipo_comprador}",
                jugadores_vendedor,
                key=f"oferta_jugador_obj_{equipo_comprador.replace(' ', '_')}"
            )

            jugador_rival = next(
                j for j in db["equipos_data"][club_vendedor]["jugadores"]
                if j["nombre"] == jugador_ofertado
            )

            st.write(f"**Posición:** {jugador_rival['pos']}")
            st.write(f"**Valor actual:** {formatear_valor(jugador_rival['valor'])}")

            tipo_oferta = st.radio(
                f"Tipo de oferta {equipo_comprador}",
                ["Traspaso", "Cesión sin opción", "Cesión con opción"],
                key=f"tipo_oferta_{equipo_comprador.replace(' ', '_')}",
                horizontal=True
            )

            duracion_oferta = 1
            opcion_compra = False
            precio_opcion_compra = 0.0

            if tipo_oferta == "Traspaso":
                precio_oferta = st.number_input(
                    f"Oferta de {equipo_comprador} (M€)",
                    min_value=0.1,
                    value=float(jugador_rival["valor"]),
                    step=0.1,
                    key=f"precio_oferta_{equipo_comprador.replace(' ', '_')}"
                )
            else:
                precio_oferta = st.number_input(
                    f"Pago por cesión {equipo_comprador} (M€)",
                    min_value=0.0,
                    value=float(max(0.1, round(jugador_rival["valor"] * 0.12, 1))),
                    step=0.1,
                    key=f"precio_cesion_oferta_{equipo_comprador.replace(' ', '_')}"
                )

                duracion_oferta = st.number_input(
                    f"Duración de la cesión {equipo_comprador} (temporadas)",
                    min_value=1,
                    max_value=5,
                    value=1,
                    step=1,
                    key=f"duracion_oferta_{equipo_comprador.replace(' ', '_')}"
                )

                if tipo_oferta == "Cesión con opción":
                    opcion_compra = True
                    precio_opcion_compra = st.number_input(
                        f"Precio opción de compra {equipo_comprador} (M€)",
                        min_value=0.1,
                        value=float(max(0.1, round(calcular_precio_traspaso(jugador_rival, club_vendedor, equipo_comprador) * 0.95, 1))),
                        step=0.1,
                        key=f"precio_opcion_compra_{equipo_comprador.replace(' ', '_')}"
                    )

            if mercado_disponible:
                if st.button(f"📨 Enviar oferta desde {equipo_comprador}", key=f"btn_oferta_{equipo_comprador.replace(' ', '_')}"):
                    if tipo_oferta == "Traspaso":
                        ok, msg = crear_oferta_club(
                            club_vendedor,
                            equipo_comprador,
                            jugador_ofertado,
                            precio_oferta,
                            tipo="traspaso"
                        )
                    else:
                        ok, msg = crear_oferta_club(
                            club_vendedor,
                            equipo_comprador,
                            jugador_ofertado,
                            precio_oferta,
                            tipo="cesion",
                            duracion=int(duracion_oferta),
                            opcion_compra=opcion_compra,
                            precio_opcion_compra=precio_opcion_compra
                        )

                    if ok:
                        oferta_recien_creada = db["ofertas_pendientes"][-1]

                        clubes_usuario = {
                            "CEREZAS", "CEREZAS B", "CEREZAS Sub-19",
                            "RB Zerkas", "RB Zerkas B", "RB Zerkas Sub-19",
                            "EKIPO", "EKIPO Sub-19"
                        }

                        # Si el vendedor es un club IA, debe responder automáticamente
                        # Si el vendedor es un club tuyo, la oferta queda pendiente para que tú decidas
                        if club_vendedor not in clubes_usuario:
                            ok2, msg2 = responder_oferta_automatica(oferta_recien_creada["id"])
                            
                            # Mostrar resultado en Streamlit
                            if ok2:
                                if "rechaz" in msg2.lower():
                                    st.error(f"❌ {msg2}")
                                else:
                                    st.success(f"✅ {msg2}")
                            else:
                                st.info(f"ℹ️ {msg2}")
                        else:
                            st.success(f"✅ Oferta enviada a {club_vendedor}. Esperando su respuesta...")

                        # DEBUG: mostrar info detallada en Streamlit y consola
                        debug_msg = (
                            f"DEBUG OFERTA: id={oferta_recien_creada['id']} | "
                            f"origen={oferta_recien_creada['origen']} | destino={oferta_recien_creada['destino']} | "
                            f"jugador={oferta_recien_creada['jugador']} | cantidad={oferta_recien_creada['cantidad']} | "
                            f"tipo={oferta_recien_creada['tipo']} | estado={oferta_recien_creada['estado']}"
                        )
                        print(debug_msg)
                        st.caption(debug_msg)

                        recargar()
                    else:
                        st.error(msg)
            else:
                st.warning("El mercado está cerrado.")

        # Hacer ofertas desde CEREZAS y sus filiales
        hacer_oferta_desde_equipo("CEREZAS")
        st.divider()
        hacer_oferta_desde_equipo("CEREZAS B")
        st.divider()
        hacer_oferta_desde_equipo("CEREZAS Sub-19")

        # Hacer ofertas desde RB Zerkas y sus filiales
        st.divider()
        hacer_oferta_desde_equipo("RB Zerkas")
        st.divider()
        hacer_oferta_desde_equipo("RB Zerkas B")
        st.divider()
        hacer_oferta_desde_equipo("RB Zerkas Sub-19")

        # Hacer ofertas desde EKIPO
        st.divider()
        hacer_oferta_desde_equipo("EKIPO")
        st.divider()
        hacer_oferta_desde_equipo("EKIPO Sub-19")

        st.divider()

        # Función auxiliar para mostrar ofertas enviadas por un equipo
        def mostrar_ofertas_enviadas(equipo_comprador):
            st.markdown(f"### 🧾 Ofertas enviadas por {equipo_comprador}")

            ofertas_enviadas = [
                o for o in db.get("ofertas_pendientes", [])
                if o["destino"] == equipo_comprador
            ]

            if ofertas_enviadas:
                filas = []
                for o in ofertas_enviadas:
                    tipo_txt = "Traspaso"
                    if o.get("tipo") == "cesion":
                        tipo_txt = "Cesión con opción" if o.get("opcion_compra", False) else "Cesión"

                    filas.append({
                        "Temp.": o["temporada"],
                        "Tipo": tipo_txt,
                        "Club vendedor": o["origen"],
                        "Club comprador": o["destino"],
                        "Jugador": o["jugador"],
                        "Oferta": formatear_valor(o["cantidad"]),
                        "Duración": o.get("duracion", "-") if o.get("tipo") == "cesion" else "-",
                        "Opción compra": formatear_valor(o.get("precio_opcion_compra", 0)) if o.get("opcion_compra", False) else "-",
                        "Estado": o["estado"]
                    })

                st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)
            else:
                st.info(f"{equipo_comprador} todavía no ha enviado ofertas.")

        # Ofertas enviadas por CEREZAS y sus filiales
        mostrar_ofertas_enviadas("CEREZAS")
        st.divider()
        mostrar_ofertas_enviadas("CEREZAS B")
        st.divider()
        mostrar_ofertas_enviadas("CEREZAS Sub-19")

        # Ofertas enviadas por RB Zerkas y sus filiales
        st.divider()
        mostrar_ofertas_enviadas("RB Zerkas")
        st.divider()
        mostrar_ofertas_enviadas("RB Zerkas B")
        st.divider()
        mostrar_ofertas_enviadas("RB Zerkas Sub-19")

        # Ofertas enviadas por EKIPO
        st.divider()
        mostrar_ofertas_enviadas("EKIPO")
        st.divider()
        mostrar_ofertas_enviadas("EKIPO Sub-19")

        st.divider()
        st.markdown("#### Log de mercado")
        if db.get("mercado_log"):
            for x in reversed(db["mercado_log"][-30:]):
                st.write(x)
        else:
            st.info("Todavía no hay movimientos.")

    with tabs[8]:
        st.subheader("🆓 Jugadores libres")



        libres = db.get("jugadores_libres", [])



        if libres:
            filas = []



            for libre in libres:
                j = libre["jugador"]



                filas.append({
                    "Nombre": j["nombre"],
                    "Pos": j["pos"],
                    "Media": j["media"],
                    "Edad": j["edad"],
                    "Valor": formatear_valor(j["valor"]),
                    "Salario": formatear_valor(j.get("salario", 0)),
                    "Último equipo": libre["equipo_origen"],
                    "Libre desde": libre["temporada_libre"]
                })



            df_libres = pd.DataFrame(filas)



            st.dataframe(
                df_libres.sort_values("Media", ascending=False),
                hide_index=True,
                use_container_width=True
            )



            st.divider()
            st.subheader("Fichar jugador libre")



            opciones_libres = [
                f"{l['jugador']['nombre']} "
                f"({l['jugador']['pos']}, {l['jugador']['media']})"
                for l in libres
            ]



            sel_libre = st.selectbox(
                "Jugador a fichar",
                opciones_libres,
                key="selector_jugador_libre"
            )



            indice = opciones_libres.index(sel_libre)
            libre_sel = libres[indice]
            j = libre_sel["jugador"]



            st.write(f"**Último equipo:** {libre_sel['equipo_origen']}")
            st.write(
                f"**Salario sugerido:** "
                f"{formatear_valor(j.get('salario', 0))} / temporada"
            )



            equipo_fichador = st.selectbox(
                "Equipo que lo ficha",
                list(db["equipos_data"].keys()),
                key="equipo_ficha_libre"
            )



            if st.button("✅ Fichar como libre", key="btn_fichar_libre"):
                if len(db["equipos_data"][equipo_fichador]["jugadores"]) >= 8:
                    st.error(f"{equipo_fichador} ya tiene demasiados jugadores.")
                else:
                    db["equipos_data"][equipo_fichador]["jugadores"].append(j)



                    j["equipo_actual"] = equipo_fichador
                    j["propietario"] = equipo_fichador



                    # Nuevo salario y nuevo fin de contrato
                    renovar_contrato_jugador(j, equipo_fichador, db)



                    db["historial_traspasos"].append({
                        "temporada": db["config"]["temporada"],
                        "jugador": j["nombre"],
                        "origen": libre_sel["equipo_origen"],
                        "destino": equipo_fichador,
                        "tipo": "libre",
                        "valor": 0
                    })



                    db["jugadores_libres"].pop(indice)



                    db["mercado_log"].append(
                        f"🆓 {j['nombre']} ficha libre por {equipo_fichador}"
                    )



                    st.success(
                        f"{j['nombre']} ficha por {equipo_fichador} como agente libre."
                    )



                    st.rerun()



        else:
            st.info("No hay jugadores libres en este momento.")



        st.divider()
        st.subheader("📜 Historial de traspasos")



        ht = db.get("historial_traspasos", [])



        ht_filtrado = [
            t for t in ht
            if t.get("tipo") != "Canterano"
            and t.get("origen") != "Cantera"
        ]



        if ht_filtrado:
            # ========== FILTRO POR DIVISIÓN ==========
            # Ahora se tiene en cuenta tanto la división de origen como la de destino
            divisiones = set()

            for t in ht_filtrado:
                div_origen = (
                    db["equipos_data"]
                    .get(t.get("origen", ""), {})
                    .get("liga", "Desconocida")
                )
                div_destino = (
                    db["equipos_data"]
                    .get(t.get("destino", ""), {})
                    .get("liga", "Desconocida")
                )
                divisiones.add(div_origen)
                divisiones.add(div_destino)

            divisiones = sorted(divisiones)



            division_sel = st.selectbox(
                "Filtrar por división",
                ["Todas"] + list(divisiones),
                key="filtro_division_traspasos"
            )



            # ========== FILTRO POR TIPO (CATEGORÍAS) ==========
            # Opciones fijas para que no dependan de los detalles exactos
            opciones_tipo = [
                "Todos",
                "Traspaso",
                "Cesión",
                "Cesión con opción",
                "Fin cesión",
                "Libre",
                "Promoción primer equipo",
                "Ascenso interno",
                "Descenso interno",
                "Ascenso portero interno",
                "Opción de compra ejecutada",
            ]



            tipo_sel = st.selectbox(
                "Filtrar por tipo",
                opciones_tipo,
                key="filtro_tipo_traspasos"
            )



            # Función que decide si un tipo guardado coincide con la categoría elegida
            def coincide_tipo(tipo_guardado: str, tipo_sel: str) -> bool:
                if tipo_sel == "Todos":
                    return True
                if tipo_sel == "Traspaso":
                    return tipo_guardado == "traspaso"
                if tipo_sel == "Fin cesión":
                    return tipo_guardado == "fin cesión"
                if tipo_sel == "Libre":
                    return tipo_guardado in {
        "libre",
        "agente libre",
        "fin de contrato",
    }
                if tipo_sel == "Promoción primer equipo":
                    return tipo_guardado == "promoción primer equipo"
                if tipo_sel == "Ascenso interno":
                    return tipo_guardado == "ascenso interno"
                if tipo_sel == "Descenso interno":
                    return tipo_guardado == "descenso interno"
                if tipo_sel == "Ascenso portero interno":
                    return tipo_guardado == "ascenso portero interno"
                if tipo_sel == "Opción de compra ejecutada":
                    return tipo_guardado == "opción de compra ejecutada"
                if tipo_sel == "Cesión con opción":
                    # Cualquier tipo que empiece por "cesión" y mencione opción u OP
                    tipo_lower = tipo_guardado.lower()
                    return (
                        tipo_lower.startswith("cesión")
                        and ("con opción" in tipo_lower or "con op" in tipo_lower)
                    )
                if tipo_sel == "Cesión":
                    # Todas las cesiones, con o sin opción
                    return tipo_guardado.startswith("cesión")
                return False



            df_ht = pd.DataFrame(ht_filtrado)



            # Aplicar filtro por división (origen O destino)
            if division_sel != "Todas":
                df_ht["division_origen"] = df_ht["origen"].apply(
                    lambda x: db["equipos_data"]
                    .get(x, {})
                    .get("liga", "Desconocida")
                )

                df_ht["division_destino"] = df_ht["destino"].apply(
                    lambda x: db["equipos_data"]
                    .get(x, {})
                    .get("liga", "Desconocida")
                )

                df_ht = df_ht[
                    (df_ht["division_origen"] == division_sel)
                    | (df_ht["division_destino"] == division_sel)
                ]



            # Aplicar filtro por tipo (categoría)
            if tipo_sel != "Todos":
                df_ht = df_ht[
                    df_ht["tipo"].apply(lambda t: coincide_tipo(t, tipo_sel))
                ]



            st.dataframe(
                df_ht.sort_values("temporada", ascending=False),
                hide_index=True,
                use_container_width=True
            )



            st.caption(
                f"Mostrando {len(df_ht)} movimientos "
                f"(división: {division_sel}, tipo: {tipo_sel})"
            )



        else:
            st.info("Todavía no hay traspasos registrados.")

    with tabs[9]:
        render_pestana_europa()

    with tabs[10]:
        render_pestana_copas()

    # Estadísticas de Copa (nueva pestaña)
    with tabs[11]:  # Índice 11 = Copas (ajusta si tienes más/menos pestañas)
        st.subheader("🏆 Estadísticas de Copa")

        modo = st.radio(
            "Mostrar",
            ["Una copa", "Todas las copas"],
            horizontal=True,
            key="copa_modo_stats",
        )

        if modo == "Una copa":
            pais_copa = st.selectbox(
                "País",
                ["Principal", "Com", "Tengu", "Folimón"],
                key="copa_pais_stats",
            )

            categoria_visible_copa = st.radio(
                "Categoría",
                ["Senior", "Sub-19"],
                horizontal=True,
                key="copa_categoria_stats",
            )

            categoria_copa = "senior" if categoria_visible_copa == "Senior" else "sub19"

            dfj = todos_los_jugadores_de_copa(pais_copa, categoria_copa, todas=False)
            st.subheader(f"🏆 Estadísticas - Copa {pais_copa} {categoria_visible_copa}")
        else:
            dfj = todos_los_jugadores_de_copa(todas=True)
            st.subheader("🏆🏆🏆🏆 Estadísticas - Todas las Copas")

        if not dfj.empty:
            dfj["Goles/Partido"] = dfj.apply(lambda r: round(r["Goles"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.markdown("👟 Goles")
                st.dataframe(
                    dfj.sort_values(["Goles", "Goles/Partido", "PJ"], ascending=[False, False, True])[
                        ["Nombre", "Pos", "Equipo", "Goles", "Goles/Partido", "PJ", "Minutos", "Nota"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c2:
                st.markdown("🎯 Asistencias")
                st.dataframe(
                    dfj.sort_values(["Asistencias", "PJ", "Minutos"], ascending=[False, True, True])[
                        ["Nombre", "Pos", "Equipo", "Asistencias", "PJ", "Minutos", "Nota"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c3:
                st.markdown("⭐ Mejores notas")
                st.dataframe(
                    dfj.sort_values(["Nota", "PJ", "Minutos"], ascending=[False, False, False])[
                        ["Nombre", "Pos", "Equipo", "Nota", "PJ", "Minutos", "Goles", "Asistencias"]
                    ],
                    hide_index=True,
                    use_container_width=True
                )

            with c4:
                st.markdown("🧤 Porteros")
                por = dfj[dfj["Pos"] == "POR"].copy()
                if not por.empty:
                    por["Promedio Encajados"] = por.apply(lambda r: round(r["Encajados"] / r["PJ"], 2) if r["PJ"] > 0 else 0, axis=1)
                    por["Minuto/Goles"] = por.apply(lambda r: round(r["Minutos"] / r["Encajados"], 2) if r["Encajados"] > 0 else 0, axis=1)
                    st.dataframe(
                        por.sort_values(["Promedio Encajados", "PJ"], ascending=[True, False])[
                            ["Nombre", "Equipo", "Encajados", "PJ", "Minutos", "Promedio Encajados", "Minuto/Goles", "Nota"]
                        ],
                        hide_index=True,
                        use_container_width=True
                    )

            st.divider()
            st.markdown("#### Todos los jugadores")
            st.dataframe(
                dfj.sort_values(["Equipo", "ValorNum", "Nombre"], ascending=[True, False, True]),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Sin datos.")

if __name__ == "__main__":
    main()