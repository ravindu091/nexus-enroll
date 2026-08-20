import csv
from datetime import time
from pathlib import Path

from core.facade import EnrolmentSystemFacade
from models.courses import CourseGrade, CourseSchedule, Enrolment
from models.users import Student, UserType
from patterns.state import ApprovedGrade, SubmittedGrade


class CsvStorage:
    """
    Data Persistence Tier (3-Tier Architecture)
    Adheres to the Single Responsibility Principle by completely isolating 
    file I/O serialization logic from the core business validation rules.
    """

    def __init__(self, data_directory: str = "data"):
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(exist_ok=True)

    def load(self) -> EnrolmentSystemFacade:
        system = EnrolmentSystemFacade()
        self._load_users(system)
        self._load_courses(system)
        self._load_enrolments(system)
        self._load_grades(system)
        self._load_course_change_requests(system)
        self._load_degree_programs(system)
        return system

    def save(self, system: EnrolmentSystemFacade) -> None:
        self._write_rows("users.csv", ["id", "role", "name", "email", "major", "department", "privilege_level", "active"], (
            {"id": user.user_id, "role": user.get_user_type(), "name": user.name, "email": user.email,
             "major": getattr(user, "major", ""), "department": getattr(user, "department", ""),
             "privilege_level": getattr(user, "privilege_level", ""), "active": user.active}
            for user in system.users.values()))
        self._write_rows("courses.csv", ["id", "name", "description", "instructor_id", "department", "capacity", "semester", "days", "start", "end", "location", "prerequisites"], (
            {"id": course.course_id, "name": course.name, "description": course.description, "instructor_id": course.instructor_id,
             "department": course.department, "capacity": course.capacity, "semester": course.semester, "days": ";".join(sorted(course.schedule.days)),
             "start": course.schedule.start_time.strftime("%H:%M"), "end": course.schedule.end_time.strftime("%H:%M"),
             "location": course.schedule.location, "prerequisites": ";".join(sorted(course.prerequisites))} for course in system.courses.values()))
        self._write_rows("enrolments.csv", ["id", "student_id", "course_id"], (
            {"id": enrolment.enrolment_id, "student_id": enrolment.student_id, "course_id": enrolment.course_id} for enrolment in system.enrolments.values()))
        self._write_rows("grades.csv", ["id", "student_id", "course_id", "grade", "status"], (
            {"id": grade.grade_id, "student_id": grade.student_id, "course_id": grade.course_id,
             "grade": grade.grade_value, "status": grade.state.get_status()} for grade in system.grades.values()))
        self._write_rows("course_change_requests.csv",
                         ["id", "faculty_id", "course_id", "request", "description", "prerequisites", "capacity", "status"],
                         ({"id": request["request_id"], "faculty_id": request["faculty_id"],
                           "course_id": request["course_id"], "request": request["request"],
                           "description": request["description"] or "",
                           "prerequisites": ";".join(request["prerequisites"] or []),
                           "capacity": request["capacity"] if request["capacity"] is not None else "",
                           "status": request["status"]} for request in system.course_change_requests))
        self._write_rows("degree_programs.csv", ["id", "name", "required_courses", "credits"], ({"id": program["program_id"], "name": program["name"], "required_courses": ";".join(f"{course}:{credits}" for course, credits in program["required_courses"].items()), "credits": program["credits"]} for program in system.degree_programs.values()))

    def _load_users(self, system):
        for row in self._read_rows("users.csv"):
            user = system.add_user(UserType(row["role"]), row["id"], row["name"], row["email"], major=row.get("major", "Undeclared"), department=row.get("department", "General"), privilege_level=int(row.get("privilege_level") or 1))
            user.active = row.get("active", "True").lower() == "true"

    def _load_courses(self, system):
        for row in self._read_rows("courses.csv"):
            start_hour, start_minute = map(int, row["start"].split(":")); end_hour, end_minute = map(int, row["end"].split(":"))
            schedule = CourseSchedule(row["id"], set(filter(None, row["days"].split(";"))), time(start_hour, start_minute), time(end_hour, end_minute), row["location"])
            system.create_course(row["id"], row["name"], row["description"], row["instructor_id"], row["department"], int(row["capacity"]), schedule, set(filter(None, row.get("prerequisites", "").split(";"))), row.get("semester") or "2026 Semester 2")

    def _load_enrolments(self, system):
        for row in self._read_rows("enrolments.csv"):
            student, course = system.get_user(row["student_id"]), system.get_course(row["course_id"])
            if isinstance(student, Student) and course:
                student.enrolled_courses.add(course.course_id)
                course.enrolled_students.add(student.user_id)
                course.available_seats -= 1
                system.enrolments[row["id"]] = Enrolment(row["id"], student.user_id, course.course_id)
                try:
                    system._enrolment_counter = max(system._enrolment_counter, int(row["id"].split("_")[-1]))
                except ValueError:
                    pass

    def _load_grades(self, system):
        for row in self._read_rows("grades.csv"):
            student = system.get_user(row["student_id"])
            if not isinstance(student, Student):
                continue
            grade_id = row.get("id") or f"GRD_{system._grade_counter + 1}"
            status = row.get("status") or "APPROVED"
            grade = CourseGrade(grade_id, student.user_id, row["course_id"], float(row["grade"]))
            grade.state = ApprovedGrade() if status == "APPROVED" else SubmittedGrade()
            system.grades[grade_id] = grade
            if status == "APPROVED":
                student.completed_courses[row["course_id"]] = float(row["grade"])
            try:
                system._grade_counter = max(system._grade_counter, int(grade_id.split("_")[-1]))
            except ValueError:
                pass

    def _load_course_change_requests(self, system):
        for row in self._read_rows("course_change_requests.csv"):
            request_id = row.get("id") or f"CR_{system._change_request_counter + 1}"
            raw_capacity = row.get("capacity", "")
            change_request = {
                "request_id": request_id,
                "faculty_id": row["faculty_id"],
                "course_id": row["course_id"],
                "request": row.get("request", ""),
                "description": row.get("description") or None,
                "prerequisites": ([item for item in row.get("prerequisites", "").split(";") if item]
                                   or None),
                "capacity": int(raw_capacity) if raw_capacity else None,
                "status": (row.get("status") or "PENDING").upper(),
            }
            system.course_change_requests.append(change_request)
            try:
                system._change_request_counter = max(system._change_request_counter, int(request_id.split("_")[-1]))
            except ValueError:
                pass

    def _load_degree_programs(self, system):
        for row in self._read_rows("degree_programs.csv"):
            required_courses = {}
            for item in filter(None, row.get("required_courses", "").split(";")):
                course_id, credits = item.split(":", 1)
                required_courses[course_id] = int(credits)
            system.degree_programs[row["id"]] = {
                "program_id": row["id"], "name": row["name"],
                "required_courses": required_courses, "credits": int(row["credits"]),
            }

    def _read_rows(self, filename):
        path = self.data_directory / filename
        if not path.exists(): return []
        with path.open(newline="", encoding="utf-8") as file: return list(csv.DictReader(file))

    def _write_rows(self, filename, fieldnames, rows):
        with (self.data_directory / filename).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames); writer.writeheader(); writer.writerows(rows)
