"""Los «sobrantes» de un extracto (movimientos tuyos que el banco no trae) se calculan UNA vez, el día que se procesa
el extracto, y se guardan en su revisión. Después la realidad cambia: el movimiento se pasa a otra cuenta, se borra o ya
se concilia con otro extracto, y la lista seguía diciendo «no aparece en el extracto» para siempre. Aquí se revalida
contra lo que hay hoy."""
import json

from sqlalchemy.orm import Session

from app.models import Movimiento


def revalidar(db: Session, historial, review: list[dict]) -> bool:
    """Marca como `sobrante_resuelto` (resuelto = «ya_no_aplica») los sobrantes cuyo movimiento ya no existe, ya está
    en otra cuenta o ya se concilió. Modifica `review` y `historial.review_json`; NO hace commit. True si cambió algo."""
    ids = [i.get("match_id") for i in review if i.get("estado") == "sobrante" and i.get("match_id")]
    if not ids:
        return False
    vivos = {
        m.id: (m.cuenta_id, m.conciliado_en)
        for m in db.query(Movimiento.id, Movimiento.cuenta_id, Movimiento.conciliado_en).filter(Movimiento.id.in_(ids))
    }
    cambio = False
    for i in review:
        if i.get("estado") != "sobrante" or not i.get("match_id"):
            continue
        v = vivos.get(i["match_id"])
        if v is None or v[0] != historial.cuenta_id or v[1] is not None:
            i["estado"] = "sobrante_resuelto"
            i["resuelto"] = "ya_no_aplica"
            cambio = True
    if cambio:
        historial.review_json = json.dumps(review, default=str)
    return cambio
