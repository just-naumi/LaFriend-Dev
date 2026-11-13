# ==============================================================================
# test_extraction_day11.py - Test Suite 15 Kasus Uji Ekstraksi (Day 11)
# ==============================================================================
# Memverifikasi 15 kalimat uji mahasiswa dengan kriteria:
# - Parameter yang disebutkan terdeteksi dengan status EXTRACTED / NEEDS_REVIEW.
# - Parameter yang tidak disebutkan tetap bernilai NULL (status: MISSING).
# - Negasi & multi-mode terdeteksi dengan benar.
# - Mode belajar terpisah secara tegas dari lokasi fisik dan platform online.
# ==============================================================================

import os
import sys
import json
from pathlib import Path

# Tambahkan direktori backend ke sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.extraction import extract_study_intent

TEST_CASES = [
    {
        "id": 1,
        "input": "Saya ingin belajar Struktur Data",
        "focus": "Course",
        "assertions": lambda res: (
            res["course_name"] == "Struktur Data" and
            res["extraction_status"]["course"] == "EXTRACTED" and
            res["topics"] is None and
            res["learning_goal"] is None and
            res["learning_mode"] is None and
            res["availabilities"] == [] and
            res["min_group_size"] is None
        )
    },
    {
        "id": 2,
        "input": "Saya ingin memahami Binary Tree",
        "focus": "Topic & Goal",
        "assertions": lambda res: (
            res["topics"] is not None and "Binary Tree" in res["topics"] and
            res["extraction_status"]["topic"] == "EXTRACTED" and
            res["learning_goal"] == "UNDERSTAND" and
            res["extraction_status"]["learning_goal"] == "EXTRACTED" and
            res["course_id"] is None
        )
    },
    {
        "id": 3,
        "input": "Saya ingin latihan soal UTS",
        "focus": "Learning Goal (Exam Prep)",
        "assertions": lambda res: (
            res["learning_goal"] == "EXAM_PREP" and
            res["extraction_status"]["learning_goal"] == "EXTRACTED" and
            res["course_id"] is None and
            res["availabilities"] == []
        )
    },
    {
        "id": 4,
        "input": "Saya ingin belajar dengan diskusi",
        "focus": "Collaboration Style",
        "assertions": lambda res: (
            res["collaboration_style"] == "DISCUSSION" and
            res["extraction_status"]["collaboration_style"] == "EXTRACTED" and
            res["course_id"] is None and
            res["availabilities"] == []
        )
    },
    {
        "id": 5,
        "input": "Saya ingin belajar offline",
        "focus": "Learning Mode",
        "assertions": lambda res: (
            res["learning_mode"] == "OFFLINE" and
            res["extraction_status"]["learning_mode"] == "EXTRACTED" and
            res["physical_location"] is None and
            res["online_platform"] is None
        )
    },
    {
        "id": 6,
        "input": "Saya ingin belajar online melalui Google Meet",
        "focus": "Mode dan Platform",
        "assertions": lambda res: (
            res["learning_mode"] == "ONLINE" and
            res["online_platform"] == "Google Meet" and
            res["physical_location"] is None and
            res["extraction_status"]["online_platform"] == "EXTRACTED"
        )
    },
    {
        "id": 7,
        "input": "Saya ingin belajar di Open Library",
        "focus": "Lokasi Fisik",
        "assertions": lambda res: (
            res["learning_mode"] == "OFFLINE" and
            res["physical_location"] == "Open Library" and
            res["online_platform"] is None and
            res["extraction_status"]["physical_location"] == "EXTRACTED"
        )
    },
    {
        "id": 8,
        "input": "Saya tersedia hari Senin pukul 13.00–15.00",
        "focus": "Jadwal Lengkap",
        "assertions": lambda res: (
            len(res["availabilities"]) == 1 and
            res["availabilities"][0]["day_or_date"] == "Senin" and
            res["availabilities"][0]["start_time"] == "13:00" and
            res["availabilities"][0]["end_time"] == "15:00" and
            res["extraction_status"]["availability"] == "EXTRACTED"
        )
    },
    {
        "id": 9,
        "input": "Saya bisa Senin atau Rabu sore",
        "focus": "Jadwal Alternatif & Waktu Relatif",
        "assertions": lambda res: (
            len(res["availabilities"]) == 2 and
            res["availabilities"][0]["day_or_date"] in ["Senin", "Rabu"] and
            res["extraction_status"]["availability"] == "NEEDS_REVIEW"
        )
    },
    {
        "id": 10,
        "input": "Saya ingin kelompok berisi 4 orang",
        "focus": "Group Size",
        "assertions": lambda res: (
            res["min_group_size"] == 4 and
            res["max_group_size"] == 4 and
            res["extraction_status"]["group_size"] == "EXTRACTED"
        )
    },
    {
        "id": 11,
        "input": "Saya ingin belajar Kalkulus untuk UTS secara offline",
        "focus": "Multi-parameter Bersamaan",
        "assertions": lambda res: (
            res["course_name"] == "Kalkulus" and
            res["learning_goal"] == "EXAM_PREP" and
            res["learning_mode"] == "OFFLINE" and
            res["availabilities"] == [] and
            res["min_group_size"] is None
        )
    },
    {
        "id": 12,
        "input": "Saya ingin belajar, tetapi belum tahu jadwalnya",
        "focus": "Missing Availability Eksplisit",
        "assertions": lambda res: (
            res["availabilities"] == [] and
            res["extraction_status"]["availability"] == "MISSING" and
            res["extracted_parameters"]["availability"]["value"] is None
        )
    },
    {
        "id": 13,
        "input": "Saya tidak mau belajar online",
        "focus": "Negasi Mode Belajar",
        "assertions": lambda res: (
            res["learning_mode"] == "OFFLINE" and
            res["extraction_status"]["learning_mode"] == "EXTRACTED"
        )
    },
    {
        "id": 14,
        "input": "Saya bisa online maupun offline",
        "focus": "Multi-mode / Fleksibel",
        "assertions": lambda res: (
            res["learning_mode"] == "HYBRID" and
            "OFFLINE" in res["extracted_parameters"]["learning_mode"]["value"] and
            "ONLINE" in res["extracted_parameters"]["learning_mode"]["value"] and
            res["extraction_status"]["learning_mode"] == "EXTRACTED"
        )
    },
    {
        "id": 15,
        "input": "Saya ingin belajar di kampus atau Google Meet",
        "focus": "Ambiguitas Lokasi dan Platform",
        "assertions": lambda res: (
            res["physical_location"] == "Kampus" and
            res["extraction_status"]["physical_location"] == "NEEDS_REVIEW" and
            res["online_platform"] == "Google Meet" and
            res["extraction_status"]["online_platform"] == "EXTRACTED" and
            res["learning_mode"] == "HYBRID"
        )
    }
]

def run_tests():
    db = SessionLocal()
    print("=" * 80)
    print("  RUNNING 15 TEST CASES - DAY 11 EXTRACTION STABILITY & DATA INTEGRITY")
    print("=" * 80)

    passed_count = 0
    results_summary = []

    for tc in TEST_CASES:
        t_id = tc["id"]
        t_input = tc["input"]
        t_focus = tc["focus"]

        res = extract_study_intent(t_input, db)
        is_passed = False
        try:
            is_passed = tc["assertions"](res)
        except Exception as e:
            print(f"Error pada kasus {t_id}: {e}")
            is_passed = False

        status_str = "PASS [OK]" if is_passed else "FAIL [X]"
        if is_passed:
            passed_count += 1

        results_summary.append({
            "id": t_id,
            "input": t_input,
            "focus": t_focus,
            "status": "PASS" if is_passed else "FAIL",
            "extracted": {
                "course": res.get("course_name"),
                "topics": res.get("topics"),
                "goal": res.get("learning_goal"),
                "style": res.get("collaboration_style"),
                "mode": res.get("learning_mode"),
                "location": res.get("physical_location"),
                "platform": res.get("online_platform"),
                "group": f"{res.get('min_group_size')}-{res.get('max_group_size')}" if res.get('min_group_size') else None,
                "slots": len(res.get("availabilities", [])),
                "avail_status": res.get("extraction_status", {}).get("availability")
            }
        })

        print(f"[{t_id:02d}/15] {status_str} | Fokus: {t_focus:<32} | Input: '{t_input}'")

    db.close()

    print("=" * 80)
    print(f"  TOTAL HASIL: {passed_count} DARI {len(TEST_CASES)} TEST CASES LULUS ({passed_count/len(TEST_CASES)*100:.1f}%)")
    print("=" * 80)

    # Simpan laporan hasil uji coba ke JSON
    report_path = backend_dir / "tests" / "test_results_day11.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)
    print(f"Detail laporan disimpan di: {report_path}")

    return passed_count == len(TEST_CASES)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
