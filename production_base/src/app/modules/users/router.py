from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

# Add user endpoints here; keep business rules in service.py.
