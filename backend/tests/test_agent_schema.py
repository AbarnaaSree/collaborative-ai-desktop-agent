import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentRegistrationRequest


def test_valid_agent_registration():
    data = AgentRegistrationRequest(
        name="Development PC",
        hostname="DEV-PC",
        operating_system="Windows 11",
        agent_version="0.1.0",
    )

    assert data.name == "Development PC"
    assert data.hostname == "DEV-PC"
    assert data.team_id is None


def test_agent_registration_with_team():
    data = AgentRegistrationRequest(
        name="Development PC",
        hostname="DEV-PC",
        operating_system="Windows 11",
        agent_version="0.1.0",
        team_id=1,
    )

    assert data.team_id == 1


def test_agent_registration_requires_name():
    with pytest.raises(ValidationError):
        AgentRegistrationRequest(
            hostname="DEV-PC",
            operating_system="Windows 11",
            agent_version="0.1.0",
        )