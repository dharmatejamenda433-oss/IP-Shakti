
from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(
    title="IP-SAKTI API",
    description="Evidence-grounded domain-specific RAG system",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ip-sakti-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }