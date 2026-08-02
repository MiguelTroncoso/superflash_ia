"""Endpoint de balance de infraestructura."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.balance import BalanceRead
from app.services.balance_service import BalanceService

router = APIRouter(tags=["balance"])


@router.get("/balance", response_model=BalanceRead)
def get_balance(session: Annotated[Session, Depends(get_db)]) -> BalanceRead:
    """Devuelve capacidad y utilización agregada de servidores habilitados."""
    return BalanceService(session).build()
