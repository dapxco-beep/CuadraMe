from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ahorcado import estado_partida, palabra_aleatoria, progreso_palabra
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import PartidaAhorcado, RachaUsuario, VidaAhorcado
from app.rachas import vidas_disponibles
from app.schemas import AdivinarLetraRequest, PartidaAhorcadoOut, VidasAhorcadoResponse

router = APIRouter(prefix="/ahorcado", tags=["ahorcado"])


def _serializar(partida: PartidaAhorcado) -> PartidaAhorcadoOut:
    letras = partida.letras_intentadas.split(",") if partida.letras_intentadas else []
    return PartidaAhorcadoOut(
        id=partida.id,
        progreso=progreso_palabra(partida.palabra, letras),
        letras_intentadas=letras,
        intentos_restantes=partida.intentos_restantes,
        pista=partida.pista,
        estado=partida.estado,
        palabra=partida.palabra if partida.estado != "jugando" else None,
    )


@router.get("/vidas", response_model=VidasAhorcadoResponse)
def vidas(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    racha = db.query(RachaUsuario).filter(RachaUsuario.usuario_id == usuario.id).first()
    return VidasAhorcadoResponse(
        vidas_disponibles=vidas_disponibles(db, usuario.id),
        racha_actual=racha.dias_consecutivos if racha else 0,
        mejor_racha=racha.mejor_racha if racha else 0,
    )


@router.post("/nueva-partida", response_model=PartidaAhorcadoOut)
def nueva_partida(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    partida_activa = (
        db.query(PartidaAhorcado)
        .filter(PartidaAhorcado.usuario_id == usuario.id, PartidaAhorcado.estado == "jugando")
        .first()
    )
    if partida_activa:
        return _serializar(partida_activa)

    vida = (
        db.query(VidaAhorcado)
        .filter(VidaAhorcado.usuario_id == usuario.id, VidaAhorcado.usada == False)  # noqa: E712
        .first()
    )
    if not vida:
        raise HTTPException(
            status_code=400,
            detail="No tienes vidas disponibles. Gánalas cumpliendo presupuestos, metas, o manteniendo tu racha de registro.",
        )

    palabra, pista = palabra_aleatoria()
    partida = PartidaAhorcado(usuario_id=usuario.id, palabra=palabra, pista=pista, intentos_restantes=6)
    vida.usada = True
    db.add(partida)
    db.commit()
    db.refresh(partida)
    return _serializar(partida)


@router.post("/{partida_id}/adivinar", response_model=PartidaAhorcadoOut)
def adivinar_letra(
    partida_id: str,
    data: AdivinarLetraRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    partida = (
        db.query(PartidaAhorcado)
        .filter(PartidaAhorcado.id == partida_id, PartidaAhorcado.usuario_id == usuario.id)
        .first()
    )
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    if partida.estado != "jugando":
        return _serializar(partida)

    letra = data.letra.strip().upper()[:1]
    if not letra:
        raise HTTPException(status_code=400, detail="Letra inválida")

    letras = partida.letras_intentadas.split(",") if partida.letras_intentadas else []
    if letra in letras:
        return _serializar(partida)

    letras.append(letra)
    partida.letras_intentadas = ",".join(letras)

    if letra not in partida.palabra:
        partida.intentos_restantes -= 1

    partida.estado = estado_partida(partida.palabra, letras, partida.intentos_restantes)
    db.commit()
    db.refresh(partida)
    return _serializar(partida)
