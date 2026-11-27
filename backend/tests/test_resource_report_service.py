from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import User, Agent, AgentMetric
from app.services.resource_report_service import get_resource_report


@pytest.fixture
def db_session():
    """Create an isolated in-memory database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_test_agent(db):
    user = User(
        email="report@example.com",
        full_name="Report Test User",
        hashed_password="test-password-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    agent = Agent(
        name="Report Test Desktop",
        hostname="REPORT-PC-001",
        operating_system="Windows 11",
        agent_version="1.0.0",
        registered_by=user.id,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


def create_test_metric(db, agent_id, cpu, memory, disk, uptime, recorded_at):
    metric = AgentMetric(
        agent_id=agent_id,
        cpu_usage=cpu,
        memory_usage=memory,
        memory_total=16_000_000_000,
        memory_available=5_000_000_000,
        disk_usage=disk,
        disk_total=512_000_000_000,
        disk_free=150_000_000_000,
        uptime_seconds=uptime,
        recorded_at=recorded_at,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def test_resource_report_calculates_average_and_maximum(db_session):
    agent = create_test_agent(db_session)

    first_time = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 11, 27, 11, 0, tzinfo=timezone.utc)

    create_test_metric(
        db_session, agent.id, 20, 40, 50, 1000, first_time
    )
    create_test_metric(
        db_session, agent.id, 60, 80, 90, 2000, second_time
    )

    report = get_resource_report(db_session, agent.id)

    assert report is not None
    assert report["agent_id"] == agent.id
    assert report["sample_count"] == 2

    assert report["cpu_usage"] == {
        "average": 40.0,
        "maximum": 60.0,
    }
    assert report["memory_usage"] == {
        "average": 60.0,
        "maximum": 80.0,
    }
    assert report["disk_usage"] == {
        "average": 70.0,
        "maximum": 90.0,
    }

    assert report["latest_uptime_seconds"] == 2000
    assert report["period_start"] == first_time.replace(tzinfo=None)
    assert report["period_end"] == second_time.replace(tzinfo=None)


def test_resource_report_returns_none_without_metrics(db_session):
    agent = create_test_agent(db_session)

    report = get_resource_report(db_session, agent.id)

    assert report is None


def test_resource_report_uses_only_requested_agent_metrics(db_session):
    first_agent = create_test_agent(db_session)

    second_agent = Agent(
        name="Other Desktop",
        hostname="OTHER-PC-001",
        operating_system="Windows 11",
        agent_version="1.0.0",
        registered_by=first_agent.registered_by,
    )
    db_session.add(second_agent)
    db_session.commit()
    db_session.refresh(second_agent)

    recorded_at = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)

    create_test_metric(
        db_session, first_agent.id, 25, 35, 45, 1000, recorded_at
    )
    create_test_metric(
        db_session, second_agent.id, 95, 95, 95, 9000, recorded_at
    )

    report = get_resource_report(db_session, first_agent.id)

    assert report is not None
    assert report["sample_count"] == 1
    assert report["cpu_usage"]["average"] == 25.0
    assert report["latest_uptime_seconds"] == 1000