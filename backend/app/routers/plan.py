from fastapi import APIRouter, Depends

from ..db import connect
from ..engine.recommend import build_plan
from ..models import SurveyRequest

router = APIRouter()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/plan")
def create_plan(survey: SurveyRequest, conn=Depends(get_conn)):
    payload = survey.model_dump()
    payload["meds"] = [m for m in payload["meds"]]
    return build_plan(payload, conn)
