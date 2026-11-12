from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

ReasonCode = Literal[
    "SCHEDULE_MISMATCH", "TOPIC_MISMATCH", "GOAL_MISMATCH", "STYLE_MISMATCH",
    "GROUP_SIZE", "NO_RESPONSE", "USER_WITHDRAWAL", "OTHER",
]


class RecommendationViewed(BaseModel):
    match_id: str = Field(min_length=1, max_length=36)


class RecommendationFeedbackIn(BaseModel):
    relevance_rating: Optional[Literal["VERY_RELEVANT", "RELEVANT", "NEUTRAL", "NOT_RELEVANT"]] = None
    explanation_rating: Optional[Literal["VERY_CLEAR", "CLEAR", "UNCLEAR", "NOT_CLEAR"]] = None
    interest_level: Optional[Literal["INTERESTED", "UNSURE", "NOT_INTERESTED"]] = None
    comments: Optional[str] = Field(default=None, max_length=500)


class SessionFeedbackIn(BaseModel):
    session_held: bool
    participation_rating: Optional[int] = Field(default=None, ge=1, le=5)
    style_fit_rating: Optional[int] = Field(default=None, ge=1, le=5)
    learning_benefit_rating: Optional[int] = Field(default=None, ge=1, le=5)
    overall_satisfaction: Optional[int] = Field(default=None, ge=1, le=5)
    repeat_intention: Optional[bool] = None
    reason_code: Optional[ReasonCode] = None
    comments: Optional[str] = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    feedback_id: str
    student_id: str
    match_id: Optional[str] = None
    session_id: Optional[str] = None
    feedback_type: str
    relevance_rating: Optional[str] = None
    explanation_rating: Optional[str] = None
    interest_level: Optional[str] = None
    session_held: Optional[bool] = None
    participation_rating: Optional[int] = None
    style_fit_rating: Optional[int] = None
    learning_benefit_rating: Optional[int] = None
    overall_satisfaction: Optional[int] = None
    repeat_intention: Optional[bool] = None
    reason_code: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Metric(BaseModel):
    value: Optional[float] = None  # None berarti belum ada data, bukan nol
    numerator: float
    denominator: int


class MetricsResponse(BaseModel):
    rar: Metric
    gfr: Metric
    scr: Metric
    mss: Metric
    rsi: Metric
    failure_reasons: Dict[str, int]
    recommendation_feedback: Dict[str, Dict[str, int]]
    sessions_not_due: int
    sessions_disputed: int
    completed_with_feedback: int
    min_completed_for_weight_test: int
    data_sufficient: bool


class ScoreBand(BaseModel):
    score_from: int
    score_to: int
    sessions_due: int
    sessions_completed: int
    mean_satisfaction: Optional[float] = None


class Weights(BaseModel):
    t: float = Field(ge=0, le=1)
    g: float = Field(ge=0, le=1)
    s: float = Field(ge=0, le=1)
    d: float = Field(ge=0, le=1)
    m: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self):
        if abs(self.t + self.g + self.s + self.d + self.m - 1.0) > 1e-6:
            raise ValueError("Jumlah kelima bobot harus 1,00")
        return self


class WeightEvaluateIn(BaseModel):
    candidate: Weights
    test_from: datetime  # hanya sesi yang berakhir sejak waktu ini yang dipakai sebagai data uji


class WeightResult(BaseModel):
    weights: Weights
    correlation: Optional[float] = None


class WeightEvaluateResponse(BaseModel):
    data_sufficient: bool
    completed_with_feedback: int
    test_sessions: int
    current: WeightResult
    candidate: WeightResult
    candidate_better: Optional[bool] = None


AnalysisResponse = List[ScoreBand]
