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
    epilepsy: bool = False            # seizure-threshold modifier
    long_qt: bool = False             # QT-prolonging modifier
    upcoming_bloodwork: bool = False  # biotin lab-assay-interference modifier


class CheckRequest(BaseModel):
    agents: list[AgentIn]
    profile: Profile = Field(default_factory=Profile)


class SurveyRequest(BaseModel):
    goals: list[str] = Field(default_factory=list)   # energy|sleep|heart|joint|immunity|...
    diet: str | None = None                          # vegan|vegetarian|omnivore
    alcohol: str | None = None                       # none|occasional|regular
    sun: str | None = None                           # low|moderate|high
    # lifestyle gate triggers (match survey_rule.trigger_field/value)
    smoking_status: str | None = None                # current_smoker
    uses_cbd: str | None = None                      # yes
    uses_cannabis: str | None = None                 # yes
    uses_glp1: str | None = None                     # yes
    upcoming_bloodwork: str | None = None            # yes
    meds: list[AgentIn] = Field(default_factory=list)
    profile: Profile = Field(default_factory=Profile)
