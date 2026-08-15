"""Consultas de perfiles de coste sin exponer secretos."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.intelligence import ServerCostProfile
from app.models.server import Server


class CostRepository:
    """Lecturas de perfiles financieros locales."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_enabled_profiles(self) -> list[tuple[ServerCostProfile, Server]]:
        """Devuelve perfiles de servidores habilitados en una sola consulta."""
        stmt = (
            select(ServerCostProfile, Server)
            .join(Server, Server.id == ServerCostProfile.server_id)
            .where(Server.enabled.is_(True))
            .order_by(ServerCostProfile.next_payment_date, Server.name)
        )
        return [(row[0], row[1]) for row in self._session.execute(stmt).all()]

    def list_for_servers(self, server_ids: list[int]) -> list[tuple[ServerCostProfile, Server]]:
        """Devuelve perfiles para un conjunto acotado de servidores."""
        if not server_ids:
            return []
        stmt = (
            select(ServerCostProfile, Server)
            .join(Server, Server.id == ServerCostProfile.server_id)
            .where(Server.id.in_(server_ids))
            .order_by(Server.name)
        )
        return [(row[0], row[1]) for row in self._session.execute(stmt).all()]

    def count_enabled_servers(self) -> int:
        """Cuenta servidores habilitados para detectar perfiles faltantes."""
        return int(
            self._session.scalar(select(func.count(Server.id)).where(Server.enabled.is_(True))) or 0
        )
