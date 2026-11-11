from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CourseBase(BaseModel):
    course_code: str
    course_name: str
    study_program: str = "S1 Teknik Komputer"

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    course_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

