"""Vitamin Advisor POC — FastAPI app."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import interactions, plan, research

# Allowed browser origins. Dev origins are always allowed; production origins
# (e.g. the Vercel domain) are added via FRONTEND_ORIGIN — a comma-separated
# list — so the deployment can be pointed at a new frontend without a code change.
DEV_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]
ALLOWED_ORIGINS = DEV_ORIGINS + [
    o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "").split(",") if o.strip()
]

GLOBAL_FOOTER = ("This app provides general information only and is not medical advice. "
                 "It is not a substitute for professional guidance — consult your pharmacist "
                 "or physician, especially if you take prescription medications, are pregnant "
                 "or breastfeeding, or have a medical condition. The demo dataset is a curated, "
                 "illustrative set, not comprehensive coverage.")

app = FastAPI(title="Vitamin Advisor POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
