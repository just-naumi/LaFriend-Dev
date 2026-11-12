from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.student import Student
from app.schemas.outcome import (
    RecommendationViewed, RecommendationFeedbackIn, SessionFeedbackIn, FeedbackResponse,
    MetricsResponse, AnalysisResponse, WeightEvaluateIn, WeightEvaluateResponse
)
from app.services.outcome import OutcomeService
from app.api.v1.auth import get_current_student

router = APIRouter(prefix="/outcomes", tags=["Outcome & Feedback"])

@router.post("/events/viewed", status_code=status.HTTP_201_CREATED)
def record_recommendation_viewed(
    data: RecommendationViewed,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Mencatat bahwa sebuah rekomendasi ditampilkan kepada mahasiswa yang sedang login."""
    event = OutcomeService.record_viewed(db, current_student.student_id, data.match_id)
    return {"event_id": event.event_id}

@router.put("/matches/{match_id}/feedback", response_model=FeedbackResponse)
def save_recommendation_feedback(
    match_id: str,
    data: RecommendationFeedbackIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Menyimpan atau memperbarui Recommendation Feedback untuk satu rekomendasi."""
    return OutcomeService.save_recommendation_feedback(db, current_student.student_id, match_id, data)

@router.put("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
def save_session_feedback(
    session_id: str,
    data: SessionFeedbackIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Menyimpan atau memperbarui Session Feedback, termasuk konfirmasi sesi terlaksana."""
    return OutcomeService.save_session_feedback(db, current_student.student_id, session_id, data)

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Lima metrik evaluasi: RAR, GFR, SCR, MSS, dan RSI."""
    return OutcomeService.compute_metrics(db)

@router.get("/analysis", response_model=AnalysisResponse)
def get_score_analysis(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Hasil sesi dan kepuasan per rentang skor kecocokan."""
    return OutcomeService.score_analysis(db)

@router.post("/weights/evaluate", response_model=WeightEvaluateResponse)
def evaluate_weights(
    data: WeightEvaluateIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Membandingkan bobot calon dengan bobot berlaku pada data uji. Tidak mengubah bobot."""
    return OutcomeService.evaluate_weights(db, data.candidate, data.test_from)
