from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    # Keep liveness checks lightweight; add a separate readiness check for dependencies.
    return {"status": "ok"}
