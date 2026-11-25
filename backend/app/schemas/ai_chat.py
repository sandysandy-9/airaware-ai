"""Schemas for Stage 3.2 Server-Grounded AI Air Quality Assistant (Deeply Immutable Snapshots)."""

from types import MappingProxyType
from typing import Annotated, Any, Dict, List, Literal, Mapping, Optional, Tuple
import unicodedata
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from app.core.config import settings
from app.engine.recommendation_rules import (
    ActivityType,
    ExposureDuration,
    VulnerabilityGroup,
)
from app.providers.factory import validate_city_input
from app.schemas.comparison import LocationComparisonQuery

MAX_CHAT_HISTORY_TURNS = 10
MAX_AGGREGATE_HISTORY_CHARS = 2500


def _validate_clean_text(raw: str, *, field_label: str, max_len: int) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"{field_label} must be a string.")
    for ch in raw:
        if ch in ("\n", "\r", "\t"):
            continue
        if ord(ch) < 32 or unicodedata.category(ch).startswith("C"):
            raise ValueError(f"{field_label} contains disallowed control or formatting characters.")
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError(f"{field_label} must not be blank.")
    if len(cleaned) > max_len:
        raise ValueError(f"{field_label} exceeds maximum limit ({max_len} characters).")
    return cleaned


class ChatMessage(BaseModel):
    """Sanitized prior conversation turn; optional server HMAC attestation marks unaltered backend summaries."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)
    attestation: Optional[str] = Field(None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @field_validator("content")
    @classmethod
    def _clean_content(cls, v: str) -> str:
        return _validate_clean_text(v, field_label="Chat message", max_len=1000)


class AIChatRequest(BaseModel):
    """Strict AI assistant request forbidding any client-supplied air quality or risk data."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=1000)
    city: Optional[str] = Field(None, min_length=1, max_length=64)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    compare_locations: Optional[List[LocationComparisonQuery]] = Field(
        None, min_length=2, max_length=6
    )
    activity: ActivityType = ActivityType.WALKING
    sensitivity_preference: VulnerabilityGroup = VulnerabilityGroup.GENERAL
    duration: ExposureDuration = ExposureDuration.THIRTY_TO_SIXTY_MIN
    chat_history: List[ChatMessage] = Field(default_factory=list, max_length=MAX_CHAT_HISTORY_TURNS)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, v: str) -> str:
        return _validate_clean_text(v, field_label="Question message", max_len=settings.llm_max_input_chars)

    @field_validator("city")
    @classmethod
    def _validate_city(cls, v: Optional[str]) -> Optional[str]:
        return validate_city_input(v) if v is not None else None

    @field_validator("chat_history")
    @classmethod
    def _validate_aggregate_history_size(cls, history: List[ChatMessage]) -> List[ChatMessage]:
        if len(history) > MAX_CHAT_HISTORY_TURNS:
            raise ValueError(f"chat_history cannot exceed {MAX_CHAT_HISTORY_TURNS} turns.")
        total_chars = sum(len(turn.content) for turn in history)
        if total_chars > MAX_AGGREGATE_HISTORY_CHARS:
            raise ValueError(
                f"Aggregate chat_history size ({total_chars} chars) exceeds maximum allowed limit "
                f"({MAX_AGGREGATE_HISTORY_CHARS} characters)."
            )
        return history


# --- Deeply Immutable Snapshot Models (MEDIUM-01) ---


class PollutantSnapshot(BaseModel):
    """Deeply immutable snapshot of a single pollutant assessment."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["SUFFICIENT", "INSUFFICIENT_DATA", "UNAVAILABLE"]
    concentration: Optional[float] = None
    unit: str
    sub_index: Optional[int] = None
    category: Optional[str] = None
    averaging_period: str
    unavailable_reason: Optional[str] = None


class TemporalSnapshot(BaseModel):
    """Deeply immutable snapshot of Stage 2.1 separated temporal governance."""

    model_config = ConfigDict(frozen=True)

    model_issue_time: Optional[str] = None
    valid_time: str
    retrieval_time: str
    valid_time_vs_retrieval: Literal["PAST", "CURRENT", "FUTURE"]
    model_run_relation: Literal["ANALYSIS", "FORECAST", "UNKNOWN"]
    data_source_type: Literal["MODEL_DERIVED"] = "MODEL_DERIVED"


class ComparisonItemSnapshot(BaseModel):
    """Deeply immutable single-location entry in a server-assessed comparison."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    indicative_index: Optional[int] = None
    category: Optional[str] = None
    dominant_pollutant: Optional[str] = None
    valid_time: Optional[str] = None
    error: Optional[str] = None


class ComparisonSummarySnapshot(BaseModel):
    """Deeply immutable multi-location comparison summary."""

    model_config = ConfigDict(frozen=True)

    items: Tuple[ComparisonItemSnapshot, ...] = ()
    cleanest_location: Optional[str] = None
    most_polluted_location: Optional[str] = None


def _freeze_pollutant_map(v: Mapping[str, PollutantSnapshot]) -> Mapping[str, PollutantSnapshot]:
    return v if isinstance(v, MappingProxyType) else MappingProxyType(dict(v))


def _freeze_str_map(v: Mapping[str, str]) -> Mapping[str, str]:
    return v if isinstance(v, MappingProxyType) else MappingProxyType(dict(v))


FrozenPollutantMap = Annotated[
    Dict[str, PollutantSnapshot],
    AfterValidator(_freeze_pollutant_map),
    PlainSerializer(lambda m: {k: v.model_dump() for k, v in m.items()}, return_type=dict),
]

FrozenFactRegistry = Annotated[
    Dict[str, str],
    AfterValidator(_freeze_str_map),
    PlainSerializer(lambda m: dict(m), return_type=dict),
]


class VerifiedContextSnapshot(BaseModel):
    """Deeply immutable server-authoritative context envelope with canonical serialization & integrity digest."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    location_name: str
    requested_latitude: float
    requested_longitude: float
    returned_latitude: Optional[float] = None
    returned_longitude: Optional[float] = None
    geodesic_snap_distance_km: Optional[float] = None
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    is_official_cpcb_station_aqi: Literal[False] = False
    assessment_status: Literal["SUCCESS", "INSUFFICIENT_DATA"]
    status_message: str
    indicative_index_value: Optional[int] = None
    indicative_index_category: Optional[str] = None
    dominant_pollutant: Optional[str] = None
    dominant_pollutant_name: Optional[str] = None
    pollutants: FrozenPollutantMap
    unavailable_pollutants: Tuple[str, ...] = ()
    temporal_governance: TemporalSnapshot
    freshness_status: str = "UNKNOWN_RUN_AGE"
    cache_hit: bool = False
    recommendation_status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    advisory_level: str
    recommendation_headline: Optional[str] = None
    triggered_rule_ids: Tuple[str, ...] = ()
    uncertainty_notes: Tuple[str, ...] = ()
    comparison_summary: Optional[ComparisonSummarySnapshot] = None
    fact_registry: FrozenFactRegistry
    canonical_snapshot_json: str
    integrity_sha256: str
    integrity_note: str = (
        "SHA-256 integrity digest computed over the canonical server-serialized snapshot to verify "
        "non-tampering between prompt assembly and verification; it does not certify external data scientific accuracy."
    )


class StructuredLLMExplanation(BaseModel):
    """Backend-controlled structured LLM selection schema.

    Gemini supplies only allowlisted explanation IDs, intent, fact references,
    location echo, and an optional non-factual conversational lead; the backend
    renders every environmental fact exclusively from VerifiedContextSnapshot.
    """

    model_config = ConfigDict(extra="forbid")

    response_intent: Literal[
        "OVERVIEW",
        "DOMINANT_POLLUTANT",
        "ACTIVITY_GUIDANCE",
        "PROVENANCE_AND_TEMPORAL",
        "COMPARISON",
        "INSUFFICIENT_EVIDENCE",
    ]
    approved_explanation_ids: List[
        Literal[
            "EXPLAIN_INDEX_OVERVIEW",
            "EXPLAIN_DOMINANT_DRIVER",
            "EXPLAIN_UNAVAILABLE_POLLUTANTS",
            "EXPLAIN_ACTIVITY_GUIDANCE",
            "EXPLAIN_MODEL_PROVENANCE",
            "EXPLAIN_TEMPORAL_POSTURE",
            "EXPLAIN_COMPARISON",
            "EXPLAIN_INSUFFICIENT_DATA",
            "EXPLAIN_EDUCATIONAL_PM25",
            "EXPLAIN_EDUCATIONAL_PM10",
            "EXPLAIN_EDUCATIONAL_O3",
            "EXPLAIN_EDUCATIONAL_NO2",
            "EXPLAIN_EDUCATIONAL_SO2",
            "EXPLAIN_EDUCATIONAL_CO",
        ]
    ] = Field(..., min_length=1, max_length=6)
    referenced_fact_ids: List[str] = Field(..., min_length=1, max_length=12)
    claimed_location: str = Field(..., min_length=2, max_length=100)
    claimed_is_official_station: bool
    conversational_lead: Optional[str] = Field(None, max_length=160)


class AIChatResponse(BaseModel):
    """Grounded assistant response separating server-verified facts from explanation output."""

    reply: str
    grounded_in_data: bool = True
    explanation_mode: Literal["llm_grounded", "deterministic_fallback"]
    model_used: str
    llm_fallback_used: bool = False
    llm_fallback_reason: Optional[str] = None
    prompt_injection_detected: bool = False
    verified_context: VerifiedContextSnapshot
    sources_cited: List[str]
    warnings: List[str] = Field(default_factory=list)
    history_summary: Optional[str] = None
    reply_attestation: Optional[str] = None
    disclaimer: str = (
        "All numeric metrics reflect INDICATIVE_MODEL_INDEX computed on Copernicus CAMS Global atmospheric grid data, "
        "not an official CPCB physical monitoring station (CAAQMS) reading. Guidance is informational and does not "
        "constitute medical diagnosis or prescription."
    )
