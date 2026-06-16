"""Vitamin Advisor POC — FastAPI app."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import interactions, plan, research

GLOBAL_FOOTER = ("This app provides general information only and is not medical advice. "
                 "It is not a substitute for professional guidance — consult your pharmacist "
                 "or physician, especially if you take prescription medications, are pregnant "
                 "or breastfeeding, or have a medical condition. The demo dataset is a curated, "
                 "illustrative set, not comprehensive coverage.")

app = FastAPI(title="Vitamin Advisor POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan.router)
app.include_router(interactions.router)
app.include_router(research.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/disclaimer")
def disclaimer():
    return {"footer": GLOBAL_FOOTER}
