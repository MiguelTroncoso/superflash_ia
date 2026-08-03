"""Pruebas del motor de capacidad, costes y simulaciones locales."""

from datetime import UTC, date, datetime

from app.models import (
    BillingFrequency,
    PaymentStatus,
    Server,
    ServerCostProfile,
    ServerMetric,
    ServerRole,
)
from app.services.distribution_engine import DistributionLoad, DistributionTarget, distribute_load


def _server(session, external_id: str, name: str, capacity: float = 1_000) -> Server:
    server = Server(
        external_id=external_id,
        name=name,
        role=ServerRole.LIVE,
        network_capacity_mbps=capacity,
        operational_network_limit_mbps=700,
        recommended_network_limit_mbps=800,
        minimum_network_reserve_mbps=0,
        enabled=True,
    )
    session.add(server)
    session.flush()
    return server


def _metric(session, server: Server, output: float) -> None:
    session.add(
        ServerMetric(
            server_id=server.id,
            collected_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
            cpu_percent=20,
            memory_percent=30,
            disk_percent=40,
            input_mbps=output / 2,
            output_mbps=output,
            active_connections=1,
            active_streams=1,
            source="mock",
        )
    )


def _cost(session, server: Server, amount: float, next_payment: date) -> None:
    session.add(
        ServerCostProfile(
            server_id=server.id,
            monthly_cost=amount,
            currency="USD",
            billing_frequency=BillingFrequency.MONTHLY,
            next_payment_date=next_payment,
            provider="Example Provider",
            payment_status=PaymentStatus.PENDING,
        )
    )


def test_distribution_assigns_largest_units_with_configured_limits() -> None:
    targets = [
        DistributionTarget("a", "A", 1, 1_000, 700, 800),
        DistributionTarget("b", "B", 2, 1_000, 700, 800),
    ]
    result = distribute_load(
        targets,
        [DistributionLoad("large", 700), DistributionLoad("small", 100)],
    )

    assert result.feasible
    assert result.unassigned_load_mbps == 0
    assert result.assignments[0].load_mbps == 700
    assert {item.server_key for item in result.assignments} == {"a", "b"}


def test_distribution_reports_unassigned_load_without_exceeding_limits() -> None:
    result = distribute_load(
        [DistributionTarget("a", "A", 1, 1_000, 700, 800)],
        [DistributionLoad("large", 801)],
    )

    assert not result.feasible
    assert result.unassigned_load_mbps == 801
    assert result.assignments[0].assigned is False


def test_capacity_costs_and_payment_due_are_read_only(client, session) -> None:
    server = _server(session, "intel-1", "Intelligence 1")
    _metric(session, server, 750)
    _cost(session, server, 53, date(2026, 8, 5))
    session.commit()

    capacity = client.get("/api/v1/capacity/overview")
    costs = client.get("/api/v1/costs/summary")
    upcoming = client.get("/api/v1/costs/upcoming", params={"days": 365})

    assert capacity.status_code == 200
    assert capacity.json()["servers"][0]["state"] == "high"
    assert costs.json()["monthly_total"] == 53
    assert costs.json()["annual_projected"] == 636
    assert upcoming.json()[0]["payment_status"] == "due_soon"


def test_simulation_replacement_is_persisted_locally_and_reports_savings(client, session) -> None:
    first = _server(session, "intel-first", "First")
    second = _server(session, "intel-second", "Second")
    _metric(session, first, 700)
    _metric(session, second, 100)
    _cost(session, first, 185, date(2026, 12, 1))
    _cost(session, second, 35, date(2026, 12, 1))
    session.commit()

    response = client.post(
        "/api/v1/simulations",
        json={
            "name": "replace second",
            "removed_server_ids": [second.id],
            "virtual_servers": [
                {
                    "key": "replacement",
                    "name": "Replacement",
                    "physical_capacity_mbps": 1_000,
                    "operational_limit_mbps": 700,
                    "recommended_limit_mbps": 800,
                    "monthly_cost": 30,
                }
            ],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result"]["data_quality"] == "observed"
    assert body["result"]["feasible"] is True
    assert body["result"]["monthly_savings"] == 5
    assert body["result"]["unassigned_load_mbps"] == 0

    listed = client.get("/api/v1/simulations")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_intelligence_marks_missing_data_low_confidence(client, session) -> None:
    _server(session, "intel-no-data", "No data")
    session.commit()

    response = client.get("/api/v1/intelligence/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["data_quality"] == "insufficient_data"
    assert any(
        item["code"] == "insufficient_data" and item["confidence"] < 0.5
        for item in body["recommendations"]
    )
