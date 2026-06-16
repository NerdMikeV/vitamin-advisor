import json

from fastapi import APIRouter, Depends

from ..db import connect
from ..engine.evaluator import evaluate
from ..models import CheckRequest

router = APIRouter()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/check")
def check(req: CheckRequest, conn=Depends(get_conn)):
    return evaluate([a.model_dump() for a in req.agents], req.profile.model_dump(), conn)


@router.get("/entities")
def entities(conn=Depends(get_conn)):
    """Searchable catalog for the frontend (supplements, meds, foods)."""
    rows = conn.execute(
        "SELECT entity_id, canonical_name, entity_type, aka, category, dose_low, dose_high, dose_unit FROM entity ORDER BY canonical_name").fetchall()
    return [{**dict(r), "aka": json.loads(r["aka"] or "[]")} for r in rows]
