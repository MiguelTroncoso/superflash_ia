"""API protegida para preparar servidores mediante SSH."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.models.onboarding import OnboardingAuditEvent, ServerOnboarding
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.server_repository import ServerRepository
from app.schemas.onboarding import (
    MaintenanceAction,
    MaintenanceActionRead,
    MaintenanceRequest,
    OnboardingAuditRead,
    OnboardingDiagnosisRead,
    OnboardingDiscoveryRead,
    OnboardingDiscoveryRequest,
    OnboardingHealthRead,
    OnboardingRead,
    OnboardingRetryRequest,
    OnboardingStartRequest,
    OnboardingTestSSHRead,
    OnboardingTestSSHRequest,
)
from app.services.onboarding_service import TERMINAL_STATUSES, OnboardingService
from app.services.ssh_service import SSHCredentials

router = APIRouter(prefix="/onboarding", tags=["ssh onboarding"])


@router.post("", response_model=OnboardingRead, status_code=status.HTTP_202_ACCEPTED)
def start_onboarding(
    payload: OnboardingStartRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> OnboardingRead:
    """Crea el inventario local y encola operaciones SSH catalogadas."""
    if not settings.onboarding_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding SSH está deshabilitado por configuración",
        )
    actor = _actor(operator_id)
    try:
        onboarding = OnboardingService.create_server_and_onboarding(
            session, payload, actor, settings
        )
    except ValueError as error:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El servidor ya existe"
        ) from None
    credentials = SSHCredentials(
        host=payload.ip,
        port=payload.ssh_port,
        username=payload.ssh_username,
        password=payload.password,
        private_key=payload.private_key,
        expected_host_key_fingerprint=payload.host_key_fingerprint,
    )
    background_tasks.add_task(OnboardingService(settings).run, onboarding.id, credentials, actor)
    return OnboardingRead.model_validate(onboarding)


@router.post("/discover", response_model=OnboardingDiscoveryRead)
def discover_onboarding(
    payload: OnboardingDiscoveryRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OnboardingDiscoveryRead:
    """Descubre un host y exige confirmar una host key nueva antes de guardar."""
    if not settings.onboarding_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding SSH está deshabilitado por configuración",
        )
    return OnboardingDiscoveryRead.model_validate(OnboardingService(settings).discover(payload))


@router.post("/test-ssh", response_model=OnboardingTestSSHRead)
def test_ssh_connection(
    payload: OnboardingTestSSHRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OnboardingTestSSHRead:
    """Read-only SSH preflight; it never installs or changes the target host."""
    if not settings.onboarding_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding SSH está deshabilitado por configuración",
        )
    return OnboardingTestSSHRead.model_validate(OnboardingService(settings).test_ssh(payload))


@router.get("/{onboarding_id}", response_model=OnboardingRead)
def get_onboarding(
    onboarding_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> OnboardingRead:
    onboarding = OnboardingRepository(session).get(onboarding_id)
    if onboarding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    return OnboardingRead.model_validate(onboarding)


@router.get("/{onboarding_id}/audit", response_model=list[OnboardingAuditRead])
def get_onboarding_audit(
    onboarding_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> list[OnboardingAuditRead]:
    if OnboardingRepository(session).get(onboarding_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    return [
        OnboardingAuditRead.model_validate(item)
        for item in OnboardingRepository(session).audit_for(onboarding_id)
    ]


@router.post(
    "/{onboarding_id}/retry", response_model=OnboardingRead, status_code=status.HTTP_202_ACCEPTED
)
def retry_onboarding(
    onboarding_id: int,
    payload: OnboardingRetryRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> OnboardingRead:
    repository = OnboardingRepository(session)
    onboarding = repository.get(onboarding_id)
    if onboarding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    if onboarding.status not in TERMINAL_STATUSES and onboarding.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Onboarding ya está en curso"
        )
    actor = _actor(operator_id)
    onboarding.status = "pending"
    onboarding.current_step = onboarding.last_successful_step or "pending"
    onboarding.progress_percent = 0
    onboarding.cancel_requested = False
    onboarding.retry_count += 1
    onboarding.updated_at = _now()
    onboarding.last_error_code = None
    onboarding.last_error_message_sanitized = None
    session.commit()
    credentials = SSHCredentials(
        host=onboarding.server.hostname or "",
        port=onboarding.ssh_port,
        username=onboarding.ssh_username,
        password=payload.password,
        private_key=payload.private_key,
        expected_host_key_fingerprint=onboarding.server.ssh_host_key_fingerprint,
    )
    background_tasks.add_task(OnboardingService(settings).run, onboarding.id, credentials, actor)
    return OnboardingRead.model_validate(onboarding)


@router.post("/{onboarding_id}/cancel", response_model=OnboardingRead)
def cancel_onboarding(
    onboarding_id: int,
    session: Annotated[Session, Depends(get_db)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> OnboardingRead:
    repository = OnboardingRepository(session)
    onboarding = repository.get(onboarding_id)
    if onboarding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    if onboarding.status in TERMINAL_STATUSES:
        return OnboardingRead.model_validate(onboarding)
    onboarding.cancel_requested = True
    onboarding.status = "cancelled" if onboarding.status == "pending" else onboarding.status
    onboarding.last_error_code = "cancelled"
    onboarding.last_error_message_sanitized = "Onboarding cancelado por el operador."
    onboarding.updated_at = _now()
    repository.add_audit(
        _audit(onboarding, _actor(operator_id), "cancel_requested", False, "Cancelación solicitada")
    )
    session.commit()
    return OnboardingRead.model_validate(onboarding)


@router.post(
    "/{onboarding_id}/rollback", response_model=OnboardingRead, status_code=status.HTTP_202_ACCEPTED
)
def rollback_onboarding(
    onboarding_id: int,
    payload: OnboardingRetryRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> OnboardingRead:
    repository = OnboardingRepository(session)
    onboarding = repository.get(onboarding_id)
    if onboarding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    if onboarding.status not in {"failed", "rollback_required", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Rollback no disponible en este estado"
        )
    actor = _actor(operator_id)
    onboarding.status = "rollback_required"
    onboarding.current_step = "rollback"
    onboarding.updated_at = _now()
    session.commit()
    credentials = SSHCredentials(
        host=onboarding.server.hostname or "",
        port=onboarding.ssh_port,
        username=onboarding.ssh_username,
        password=payload.password,
        private_key=payload.private_key,
        expected_host_key_fingerprint=onboarding.server.ssh_host_key_fingerprint,
    )
    background_tasks.add_task(
        OnboardingService(settings).rollback, onboarding.id, credentials, actor
    )
    return OnboardingRead.model_validate(onboarding)


@router.post("/{onboarding_id}/diagnose", response_model=OnboardingDiagnosisRead)
def diagnose_onboarding(
    onboarding_id: int,
    payload: OnboardingRetryRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> OnboardingDiagnosisRead:
    if OnboardingRepository(session).get(onboarding_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    onboarding = OnboardingRepository(session).get(onboarding_id)
    server = ServerRepository(session).get(onboarding.server_id) if onboarding else None
    if onboarding is None or server is None or not server.hostname:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Servidor sin endpoint SSH configurado"
        )
    result = OnboardingService(settings).diagnose(
        onboarding_id,
        SSHCredentials(
            host=server.hostname,
            port=onboarding.ssh_port,
            username=onboarding.ssh_username,
            password=payload.password,
            private_key=payload.private_key,
            expected_host_key_fingerprint=server.ssh_host_key_fingerprint,
        ),
        _actor(operator_id),
    )
    return OnboardingDiagnosisRead.model_validate(result)


@router.get("/{onboarding_id}/health", response_model=OnboardingHealthRead)
def onboarding_health(
    onboarding_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OnboardingHealthRead:
    try:
        result = OnboardingService(settings).health(onboarding_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    return OnboardingHealthRead.model_validate(result)


@router.post(
    "/server/{server_id}/maintenance/{action}",
    response_model=MaintenanceActionRead,
)
def server_maintenance(
    server_id: int,
    action: MaintenanceAction,
    payload: MaintenanceRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> MaintenanceActionRead:
    server = ServerRepository(session).get(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    credentials = SSHCredentials(
        host=server.hostname or "",
        port=server.ssh_port,
        username=server.ssh_username or "root",
        password=payload.password,
        private_key=payload.private_key,
        expected_host_key_fingerprint=server.ssh_host_key_fingerprint,
    )
    result = OnboardingService(settings).maintenance(
        server_id,
        action,
        credentials,
        _actor(operator_id),
        payload.target_version,
    )
    return MaintenanceActionRead.model_validate(result)


@router.get("/server/{server_id}", response_model=OnboardingRead)
def get_server_onboarding(
    server_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> OnboardingRead:
    if ServerRepository(session).get(server_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor no encontrado")
    onboarding = OnboardingRepository(session).latest_for_server(server_id)
    if onboarding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding no encontrado"
        )
    return OnboardingRead.model_validate(onboarding)


def _actor(value: str | None) -> str:
    clean = "".join(
        character
        for character in (value or "api-key-operator")
        if character.isalnum() or character in "._@-"
    )
    return clean[:120] or "api-key-operator"


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(
    onboarding: ServerOnboarding, actor: str, event: str, success: bool, detail: str
) -> OnboardingAuditEvent:
    return OnboardingAuditEvent(
        onboarding_id=onboarding.id,
        server_id=onboarding.server_id,
        actor=actor,
        event=event,
        step=onboarding.current_step,
        success=success,
        detail_sanitized=detail,
        created_at=datetime.now(UTC),
    )
