
from multiprocessing.sharedctypes import Value

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.taxpayers import router as taxpayers_router
from app.routers.conversations import router as conversations_router
from app.routers.entry_flow import router as entry_flow_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.admin_dashboard import router as admin_dashboard_router
from app.routers.business_register import router as business_register_router

app = FastAPI(
    title="EIRS Taxpayer System",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "EIRS Taxpayer System API is running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


app.include_router(taxpayers_router)
app.include_router(conversations_router)
app.include_router(entry_flow_router)
app.include_router(whatsapp_router)
app.include_router(admin_dashboard_router)
app.include_router(business_register_router)
