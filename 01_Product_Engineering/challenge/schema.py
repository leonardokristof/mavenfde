"""The contract for Fibery: what an operator sends in and what comes back.

The operator types free text. The model only turns it into lookups (ADM ID,
AAMS ID or an address) and writes the final answer; code fetches the data from
the source systems and computes the facts (stopwatch, deadlines, contacts).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    """One earlier message in the same conversation."""

    role: Literal["user", "assistant"]
    content: str


class Request(BaseModel):
    """What the operator sends."""

    message: str = Field(
        description="The operator's question as typed: an address, an ADM ID, a "
        "AAMS number or a follow-up, often with typos and no diacritics"
    )
    history: list[Turn] = Field(
        default_factory=list,
        description="Earlier turns, so a follow-up without an ID or a missing city "
        "can be merged with what was already said",
    )
    session_id: str | None = Field(
        default=None, description="Added by the app, not typed by the operator"
    )


class OpenRequest(BaseModel):
    """An open AAMS request on the building."""

    aams_id: int
    task: str = Field(description="Current task, e.g. Završetak FTTH privoda")
    task_status: str = Field(description="e.g. Novo, Dodijeljen, Parkirano")


class Building(BaseModel):
    """Everything the answer says about one building."""

    adm_id: int
    address: str = Field(description="Street, house number with suffix, settlement")
    fibre_status: (
        Literal["HOMES CONNECTED", "HOMES PASSED - STREET", "HOMES PASSED - HOUSE", "FTTA ROLLOUT"]
        | None
    ) = None
    complex_connection: bool = Field(
        default=False, description="SLOŽENO UKLJUČENJE, which shortens the timeline"
    )
    expected_timeline: str | None = Field(
        default=None, description="e.g. 'do 90 dana', or none when there is no timeline"
    )
    project_name: str | None = None
    stopwatch_active: bool | None = Field(
        default=None, description="HAKOM stopwatch; None when there is no forecast data"
    )
    stopwatch_expires: date | None = None
    open_request: OpenRequest | None = None
    days_past_deadline: int | None = Field(
        default=None, description="Set only when the current task is past its deadline"
    )
    escalation_contact: str | None = Field(
        default=None, description="Who to escalate to when the deadline is missed"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="e.g. another open request or a second record for the same address",
    )
    summary_line: str = Field(
        description="ADM ID: X | Status: Y | Naziv projekta: Z (| AAMS ID: W when open)"
    )


class Response(BaseModel):
    """What comes back to the operator."""

    outcome: Literal["answered", "needs_clarification", "not_found", "out_of_scope", "error"] = Field(
        description="How to read the answer. Only 'answered' carries facts. "
        "'not_found' means the address or ID is not in the system: say so and ask "
        "the operator to check what they typed, never guess. 'needs_clarification' "
        "means one question back (missing city, ADM or AAMS?). 'error' means a "
        "technical failure, never shown as an empty answer."
    )
    answer: str = Field(description="The Croatian text the operator reads, colleague tone")
    buildings: list[Building] = Field(
        default_factory=list, description="One per building resolved from the message"
    )
    next_step: str | None = Field(
        default=None, description="At most one suggested next step or question"
    )


def solve(request: Request) -> Response:
    """Answer one operator question about fibre at an address or a request."""
    raise NotImplementedError("implement against this signature")
