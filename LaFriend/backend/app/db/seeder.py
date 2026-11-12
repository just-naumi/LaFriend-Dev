from sqlalchemy.orm import Session
from app.models.course import Course
from app.models.student import Student
from app.core.security import hash_password

INITIAL_COURSES = [
    {"course_code": "TC2043", "course_name": "Struktur Data", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC1023", "course_name": "Algoritma & Pemrograman", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC3053", "course_name": "Sistem Basis Data", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC2013", "course_name": "Matematika Diskrit", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC1013", "course_name": "Kalkulus", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC3073", "course_name": "Jaringan Komputer", "study_program": "S1 Teknik Komputer"},
    {"course_code": "TC4013", "course_name": "Kecerdasan Buatan", "study_program": "S1 Teknik Komputer"},
]

INITIAL_STUDENTS = [
    {
        "full_name": "Andi Pratama",
        "email": "andi@student.telkomuniversity.ac.id",
        "student_number": "1201250001",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Budi Santoso",
        "email": "budi@student.telkomuniversity.ac.id",
        "student_number": "1201250002",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Citra Dewi",
        "email": "citra@student.telkomuniversity.ac.id",
        "student_number": "1201250003",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Nadia Putri",
        "email": "nadia@student.telkomuniversity.ac.id",
        "student_number": "1201250004",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Fadly Rahman",
        "email": "fadly@student.telkomuniversity.ac.id",
        "student_number": "1201250005",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Raka Aditya",
        "email": "raka@student.telkomuniversity.ac.id",
        "student_number": "1201250006",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2024,
        "password": "password123",
    },
]

def seed_initial_data(db: Session) -> None:
    # 1. Seed courses
    for c_data in INITIAL_COURSES:
        existing = db.query(Course).filter(Course.course_code == c_data["course_code"]).first()
        if not existing:
            course = Course(**c_data)
            db.add(course)

    # 2. Seed students
    for s_data in INITIAL_STUDENTS:
        existing = db.query(Student).filter(Student.email == s_data["email"]).first()
        if not existing:
            student = Student(
                full_name=s_data["full_name"],
                email=s_data["email"],
                student_number=s_data["student_number"],
                study_program=s_data["study_program"],
                academic_year=s_data["academic_year"],
                password_hash=hash_password(s_data["password"]),
                verification_status="VERIFIED",
                account_status="ACTIVE",
                is_discoverable=True
            )
            db.add(student)

    db.commit()

