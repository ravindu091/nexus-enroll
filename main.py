import os
from datetime import time

from core.csv_storage import CsvStorage
from models.courses import CourseSchedule
from models.users import Administrator, Faculty, Student, UserType

os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"


def title(text):
    print(f"\n{CYAN}{BOLD}{'=' * 64}\n  {text}\n{'=' * 64}{RESET}")


def menu(text):
    print(f"{BLUE}{BOLD}{text}{RESET}")


def notice_success(text):
    print(f"{GREEN}[OK] {text}{RESET}")


def warning(text):
    print(f"{YELLOW}! {text}{RESET}")


def error(text):
    print(f"{RED}[ERROR] {text}{RESET}")


def select(prompt, allowed):
    while (choice := input(prompt).strip()) not in allowed:
        error("Invalid selection. Try again.")
    return choice


def show_courses(courses, system):
    courses = list(courses)
    if not courses:
        warning("No courses found.")
    for course in courses:
        lecturer = system.get_user(course.instructor_id)
        print(f"\n{MAGENTA}{BOLD}> {course.course_id} - {course.name}{RESET}")
        print(f"  {CYAN}Department:{RESET} {course.department}   {CYAN}Seats:{RESET} {course.available_seats}/{course.capacity}")
        print(f"  {CYAN}Description:{RESET} {course.description}")
        print(f"  {CYAN}Instructor:{RESET} {lecturer.name if lecturer else 'Unassigned'}")
        print(f"  {CYAN}Schedule:{RESET} {', '.join(sorted(course.schedule.days))} {course.schedule.start_time:%H:%M}-{course.schedule.end_time:%H:%M} | {course.schedule.location}")
        print(f"  {CYAN}Prerequisites:{RESET} {', '.join(sorted(course.prerequisites)) or 'None'}")


def show_calendar(courses, heading):
    title(heading)
    courses = list(courses)
    if not courses:
        warning("No classes are available for this schedule.")
        return
    days = ["MON", "TUE", "WED", "THU", "FRI"]
    for day in days:
        classes = sorted((course for course in courses if day in course.schedule.days), key=lambda course: course.schedule.start_time)
        print(f"{MAGENTA}{BOLD}{day}{RESET}")
        if not classes:
            print("  -- No classes --")
        for course in classes:
            print(f"  {GREEN}{course.schedule.start_time:%H:%M}-{course.schedule.end_time:%H:%M}{RESET}  {course.course_id} - {course.name} ({course.schedule.location})")


def student_menu(system, storage, student):
    while True:
        title("STUDENT PORTAL")
        menu("[1] Browse catalogue     [2] Search courses\n[3] Add course           [4] Drop course\n[5] View schedules       [6] Academic progress\n[0] Logout")
        choice = select("Enter number: ", set("0123456"))
        if choice == "0": return
        if choice == "1":
            department = input("Department (blank for all, e.g. Computer Science): ").strip().lower()
            professor = input("Professor name (blank for all, e.g. Turing): ").strip().lower()
            matches = [course for course in system.courses.values()
                       if (not department or department in course.department.lower())
                       and (not professor or professor in (system.get_user(course.instructor_id).name.lower() if system.get_user(course.instructor_id) else ""))]
            show_courses(matches, system)
        elif choice == "2":
            term = input("Keyword, department, or instructor: ").lower()
            matches = [course for course in system.courses.values() if term in (course.name + course.description + course.department).lower() or term in (system.get_user(course.instructor_id).name.lower() if system.get_user(course.instructor_id) else "")]
            show_courses(matches, system)
        elif choice in {"3", "4"}:
            course_id = input("Course ID (e.g. CS101): ").upper()
            success, message = (system.enrol_student if choice == "3" else system.drop_course)(student.user_id, course_id)
            notice_success(message) if success else error(message)
            if success: storage.save(system)
        elif choice == "5":
            schedule_choice = select("[1] Current semester  [2] Past semesters  [0] Back\nEnter number: ", {"0", "1", "2"})
            if schedule_choice == "1":
                show_calendar(system.get_student_schedule(student.user_id), "CURRENT SEMESTER CALENDAR")
            elif schedule_choice == "2":
                show_calendar(system.get_student_past_schedule(student.user_id), "PAST SEMESTER CALENDAR")
        else:
            print("Completed:", ", ".join(f"{course}: {grade:.1f}" for course, grade in student.completed_courses.items()) or "None")
            print("Enrolled:", ", ".join(sorted(student.enrolled_courses)) or "None")


def faculty_menu(system, storage, faculty):
    while True:
        title("FACULTY PORTAL")
        menu("[1] My courses       [2] Class roster\n[3] Submit one grade  [4] Submit grade batch\n[5] Request course change\n[0] Logout")
        choice = select("Enter number: ", set("012345"))
        if choice == "0": return
        if choice == "1": show_courses(system.get_courses_by_instructor(faculty.user_id), system)
        elif choice == "2":
            roster = system.get_class_roster(faculty.user_id, input("Course ID (e.g. CS101): ").upper())
            print("\n".join(f"{row['student_id']} | {row['name']} | {row['email']}" for row in roster) or "No roster found.")
        elif choice == "3":
            try: grade = float(input("Grade (0.0-4.0): "))
            except ValueError: error("Grade must be numeric."); continue
            success, message = system.submit_grade(faculty.user_id, input("Student ID (e.g. S001): ").upper(), input("Course ID (e.g. CS101): ").upper(), grade)
            notice_success(message) if success else error(message)
            if success: storage.save(system)
        elif choice == "4":
            course_id = input("Course ID (e.g. CS101): ").upper()
            print("Enter Student ID and grade as S001,3.5. Leave blank when finished.")
            entries = []
            while (entry := input("Grade entry: ").strip()):
                try:
                    student_id, grade_text = (part.strip() for part in entry.split(",", 1))
                    entries.append((student_id.upper(), float(grade_text)))
                except ValueError:
                    error("Use the format StudentID,grade (e.g. S001,3.5).")
            if not entries:
                warning("No grades entered.")
                continue
            for student_id, submitted, message in system.submit_grades_batch(faculty.user_id, course_id, entries):
                notice_success(f"{student_id}: {message}") if submitted else error(f"{student_id}: {message}")
            storage.save(system)
        else:
            course_id = input("Course ID (e.g. CS101): ").upper()
            description = input("New description (blank to skip): ").strip() or None
            prerequisite_text = input("New prerequisites, comma-separated (blank to skip): ").strip()
            prerequisites = {item.strip().upper() for item in prerequisite_text.split(",") if item.strip()} if prerequisite_text else None
            capacity_text = input("New capacity (blank to skip): ").strip()
            try:
                capacity = int(capacity_text) if capacity_text else None
            except ValueError:
                error("Capacity must be a whole number.")
                continue
            request = input("Additional notes (blank if none): ").strip()
            success, message = system.submit_course_change_request(faculty.user_id, course_id, request, description, prerequisites, capacity)
            notice_success(message) if success else error(message)
            if success: storage.save(system)


def create_course(system, storage):
    course_id, faculty_id = input("Course ID (e.g. CS201): ").upper(), input("Faculty ID (e.g. F001): ").upper()
    if system.get_course(course_id) or not isinstance(system.get_user(faculty_id), Faculty): print("Use a unique course ID and valid faculty ID."); return
    try:
        start = time.fromisoformat(input("Start time (HH:MM): ")); end = time.fromisoformat(input("End time (HH:MM): ")); capacity = int(input("Capacity: "))
    except ValueError: print("Invalid time or capacity."); return
    schedule = CourseSchedule(course_id, {day.strip().upper() for day in input("Days (MON,WED): ").split(",") if day.strip()}, start, end, input("Location: "))
    prerequisites = {item.strip().upper() for item in input("Prerequisites (comma-separated): ").split(",") if item.strip()}
    semester = input("Semester (blank for 2026 Semester 2): ").strip() or "2026 Semester 2"
    system.create_course(course_id, input("Course name: "), input("Description: "), faculty_id, input("Department: "), capacity, schedule, prerequisites, semester)
    storage.save(system); print("Course created.")


def administrator_menu(system, storage, admin):
    while True:
        title("ADMINISTRATOR PORTAL")
        menu("[1] Add user          [2] Create course\n[3] Edit course       [4] Delete course\n[5] Force-enrol       [6] Enrolment report\n[7] Faculty workload  [8] Approve grades\n[9] Approve course changes\n[10] Account management\n[11] Degree programs\n[12] Analytics\n[0] Logout")
        choice = select("Enter number: ", {str(number) for number in range(13)})
        if choice == "0": return
        if choice == "1":
            role = select("1 Student  2 Faculty  3 Administrator: ", {"1", "2", "3"}); user_id = input("ID (e.g. S002 / F002 / A002): ").upper()
            if system.get_user(user_id): print("ID already exists."); continue
            name, email = input("Name: "), input("Email: ")
            types = {"1": UserType.STUDENT, "2": UserType.FACULTY, "3": UserType.ADMINISTRATOR}
            details = {"major": input("Major: ")} if role == "1" else {"department": input("Department: ")}
            system.add_user(types[role], user_id, name, email, **details); storage.save(system); print("User created.")
        elif choice == "2": create_course(system, storage)
        elif choice == "3":
            course = system.get_course(input("Course ID (e.g. CS101): ").upper())
            if not course: print("Course not found."); continue
            description, capacity = input(f"New description (blank keeps current): "), input(f"New capacity [{course.capacity}] (blank keeps current): ")
            semester = input(f"Semester [{course.semester}] (blank keeps current): ")
            prerequisites = input("Prerequisites (blank keeps current, comma-separated): ")
            try: new_capacity = int(capacity) if capacity else None
            except ValueError: error("Capacity must be a whole number."); continue
            success, message = system.update_course(admin.user_id, course.course_id, description or None, new_capacity,
                                                    {item.strip().upper() for item in prerequisites.split(",") if item.strip()} if prerequisites else None,
                                                    semester or None)
            notice_success(message) if success else error(message)
            if success: storage.save(system)
        elif choice == "4":
            success, message = system.delete_course(admin.user_id, input("Course ID (e.g. CS101): ").upper())
            notice_success(message) if success else error(message)
            if success: storage.save(system)
        elif choice == "5":
            success, message = system.admin_force_enrol(admin.user_id, input("Student ID (e.g. S001): ").upper(), input("Course ID (e.g. CS101): ").upper()); notice_success(message) if success else error(message)
            if success: storage.save(system)
        elif choice == "6":
            report = system.generate_enrolment_report(input("Department (blank for all): ") or None,
                                                       input("Semester (blank for all): ") or None)
            for department, courses in report["departments"].items():
                print(department)
                for course in courses: print(f"  {course['course_id']}: {course['enrolled']}/{course['capacity']} ({course['utilization']})")
        elif choice == "7":
            for record in system.generate_faculty_workload_report()["faculty"]: print(f"{record['name']}: {record['courses_taught']} courses, {record['total_students']} students")
        elif choice == "8":
            pending = system.get_pending_grades()
            for grade in pending:
                student = system.get_user(grade.student_id)
                print(f"{grade.grade_id}: {grade.course_id} | {grade.student_id} {student.name if student else ''} | {grade.grade_value:.1f} | {grade.state.get_status()}")
            grade_id = input("Grade ID to approve (blank to cancel): ").strip().upper()
            if grade_id:
                success, message = system.approve_grade(admin.user_id, grade_id)
                notice_success(message) if success else error(message)
                if success: storage.save(system)
        else:
            if choice == "10":
                user_id = input("User ID: ").upper(); user = system.get_user(user_id)
                if not user: error("User not found."); continue
                action = select("[1] Edit  [2] Deactivate  [3] Activate\nEnter number: ", {"1", "2", "3"})
                if action == "1":
                    name, email = input(f"Name [{user.name}]: "), input(f"Email [{user.email}]: ")
                    details = {"major": input(f"Major [{getattr(user, 'major', '')}]: ")} if isinstance(user, Student) else {"department": input(f"Department [{getattr(user, 'department', '')}]: ")}
                    success, message = system.update_user(admin.user_id, user_id, name or None, email or None, **{key: value for key, value in details.items() if value})
                else:
                    success, message = system.set_user_active(admin.user_id, user_id, action == "3")
                notice_success(message) if success else error(message)
                if success: storage.save(system)
            elif choice == "11":
                program_id, name = input("Program ID: ").upper(), input("Program name: ")
                required = {}
                for item in input("Required courses as COURSE:CREDITS, comma-separated: ").split(","):
                    if item.strip():
                        try: course_id, credits = item.strip().upper().split(":", 1); required[course_id] = int(credits)
                        except ValueError: error("Use COURSE:CREDITS format."); required = {}; break
                if required:
                    success, message = system.create_degree_program(admin.user_id, program_id, name, required)
                    notice_success(message) if success else error(message)
                    if success: storage.save(system)
            elif choice == "12":
                report_type = select("[1] Over 90% capacity  [2] Course popularity\nEnter number: ", {"1", "2"})
                if report_type == "1":
                    report = system.generate_enrolment_report(input("Department: ") or None, input("Semester (blank for all): ") or None, 0.9)
                    for department, courses in report["departments"].items():
                        print(department)
                        for course in courses: print(f"  {course['course_id']} | {course['name']} | {course['enrolled']}/{course['capacity']} | {course['utilization']}")
                else:
                    for course in system.generate_course_popularity_report(input("Semester (blank for all): ") or None)["courses"]:
                        print(f"  {course['course_id']} | {course['name']} | {course['enrolled']}/{course['capacity']} | {course['utilization']}")
            else:
                pending = system.get_pending_course_change_requests()
                for request in pending:
                    print(f"{request['request_id']}: {request['course_id']} | description={request['description'] or '-'} | prerequisites={','.join(request['prerequisites'] or []) or '-'} | capacity={request['capacity'] or '-'}")
                request_id = input("Request ID to approve (blank to cancel): ").strip().upper()
                if request_id:
                    success, message = system.approve_course_change_request(admin.user_id, request_id)
                    notice_success(message) if success else error(message)
                    if success: storage.save(system)


def seed(system, storage):
    if not system.get_user("S001"):
        system.add_user(UserType.STUDENT, "S001", "Alice Johnson", "alice@nexus.edu", major="Computer Science")
    if not system.get_user("F001"):
        system.add_user(UserType.FACULTY, "F001", "Dr. Alan Turing", "turing@nexus.edu", department="Computer Science")
    if not system.get_user("F002"):
        system.add_user(UserType.FACULTY, "F002", "Dr. Emmy Noether", "noether@nexus.edu", department="Mathematics")
    if not system.get_user("F003"):
        system.add_user(UserType.FACULTY, "F003", "Dr. Peter Drucker", "drucker@nexus.edu", department="Business")
    if not system.get_user("A001"):
        system.add_user(UserType.ADMINISTRATOR, "A001", "System Admin", "admin@nexus.edu", privilege_level=3)

    courses = [
        ("CS101", "Introduction to Computer Science", "Programming fundamentals and computational thinking.", "F001", "Computer Science", 30, {"MON", "WED"}, time(9), time(10, 30), "Tech 101", set()),
        ("CS201", "Data Structures", "Lists, trees, graphs, and algorithm design.", "F001", "Computer Science", 25, {"TUE", "THU"}, time(11), time(12, 30), "Tech 201", {"CS101"}),
        ("CS301", "Database Systems", "Relational modelling, SQL, and transaction management.", "F001", "Computer Science", 20, {"MON", "WED"}, time(13), time(14, 30), "Tech 203", {"CS201"}),
        ("MATH101", "Calculus I", "Differential and integral calculus for science students.", "F002", "Mathematics", 40, {"TUE", "THU"}, time(9), time(10, 30), "Science 301", set()),
        ("MATH201", "Discrete Mathematics", "Logic, sets, combinatorics, and graph theory.", "F002", "Mathematics", 35, {"MON", "WED"}, time(11), time(12, 30), "Science 302", set()),
        ("BUS101", "Principles of Management", "Core management concepts and organisational leadership.", "F003", "Business", 45, {"FRI"}, time(9), time(12), "Business 110", set()),
    ]
    for course_id, name, description, faculty_id, department, capacity, days, start, end, location, prerequisites in courses:
        if not system.get_course(course_id):
            system.create_course(course_id, name, description, faculty_id, department, capacity,
                                 CourseSchedule(course_id, days, start, end, location), prerequisites)
    if not system.get_course("CS090"):
        system.create_course("CS090", "Computing Essentials", "Completed foundation course from a previous semester.",
                             "F001", "Computer Science", 30,
                             CourseSchedule("CS090", {"FRI"}, time(13), time(14, 30), "Tech 100"),
                             semester="2026 Semester 1")
    student = system.get_user("S001")
    if isinstance(student, Student) and "CS090" not in student.completed_courses:
        student.completed_courses["CS090"] = 3.5
    storage.save(system)


def main():
    storage = CsvStorage(); system = storage.load(); seed(system, storage)
    print(f"{CYAN}{BOLD}\n+==============================================================+\n|                      NEXUSENROLL                             |\n|               University Course Enrolment                    |\n+==============================================================+{RESET}")
    while True:
        title("SELECT YOUR ROLE")
        role = select(f"{BLUE}[1] Student\n[2] Faculty\n[3] Administrator\n[0] Exit{RESET}\nEnter number: ", {"0", "1", "2", "3"})
        if role == "0": notice_success("Goodbye."); return
        example_id = {"1": "S001", "2": "F001", "3": "A001"}[role]
        user = system.get_user(input(f"Enter your ID (e.g. {example_id}): ").upper()); expected = {"1": Student, "2": Faculty, "3": Administrator}[role]
        if not isinstance(user, expected) or not getattr(user, "active", False): error("Login failed: the account is invalid or inactive."); continue
        {"1": student_menu, "2": faculty_menu, "3": administrator_menu}[role](system, storage, user)


if __name__ == "__main__": main()
