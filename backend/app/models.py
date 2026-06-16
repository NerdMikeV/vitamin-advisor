"""Pydantic request/response models."""
from pydantic import BaseModel, Field


class AgentIn(BaseModel):
    entity_id: str
    dose: float | None = None
    dose_unit: str | None = None
    source: str = "user"   # plan | med | cart | user


class Profile(BaseModel):
    pregnant: bool = False
    breastfeeding: bool = False
    renal_impaired: bool = False
    hepatic_impaired: bool = False
    hypertension: bool = False
    arrhythmia: bool = False
    pre_surgery: bool = False
    elderly: bool = False
    smoker: bool = False


class CheckRequest(BaseModel):
    agents: list[AgentIn]
    profile: Profile = Field(default_factory=Profile)


class SurveyRequest(BaseModel):
    goals: list[str] = Field(default_factory=list)   # energy|sleep|heart|joint|immunity|...
    diet: str | None = None                          # vegan|vegetarian|omnivore
    alcohol: str | None = None                       # none|occasional|regular
    sun: str | None = None                           # low|moderate|high
    meds: list[AgentIn] = Field(default_factory=list)
    profile: Profile = Field(default_factory=Profile)
