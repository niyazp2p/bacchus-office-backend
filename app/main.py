import time
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError

from app.api.router import api_router
from app.core.database import AsyncSessionLocal
from app.models.office_audit import OfficeAuditLog
from app.core.security import decode_token

app = FastAPI(
    title="Bacchus Office Panel API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS Middleware (Must allow localhost frontend origins and credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://office.bacchusdistilleryindia.com",
        "https://www.bacchusdistilleryindia.com",
        "https://bacchusdistilleryindia.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def audit_interceptor_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    # 1. Safely extract actor identity without raising unhandled JWT exceptions
    actor_id = None
    actor_email = None
    actor_role = None

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_token(token)
            if isinstance(payload, dict):
                actor_id = payload.get("sub")
                actor_email = payload.get("email")
                actor_role = payload.get("role")
        except (JWTError, Exception):
            # Guard against invalid signature, malformed tokens, or expired JWTs
            pass

    # 2. Execute inner route handler
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # 3. Intercept mutating methods (POST, PUT, PATCH, DELETE) outside docs/openapi
    excluded_paths = ("/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json")
    if request.method in ["POST", "PUT", "PATCH", "DELETE"] and not request.url.path.startswith(excluded_paths):
        # Resolve client IP safely from proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (request.client.host if request.client else "127.0.0.1")
        )

        # Isolated DB persistence error boundary
        try:
            async with AsyncSessionLocal() as session:
                log_record = OfficeAuditLog(
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    method=request.method,
                    route_path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=duration_ms,
                    client_ip=client_ip,
                    action_description=f"Action on {request.url.path}",
                )
                session.add(log_record)
                await session.commit()
        except Exception as audit_err:
            # Audit failures must never crash client API responses
            print(f"[AUDIT_LOG_WARN] Failed to write audit record: {audit_err}")

    return response

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/api/v1/docs")

@app.get("/docs", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url="/api/v1/docs")

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "Bacchus Spirits Office Suite"}

app.include_router(api_router, prefix="/api/v1")