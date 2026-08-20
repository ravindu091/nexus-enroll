from datetime import datetime
from typing import List, Dict, Optional

# Importing Models
from models.users import User, Student, Faculty, Administrator, UserType
from models.courses import Course, CourseSchedule, Enrolment, CourseGrade

# Importing Patterns
from patterns.factory import UserFactory
from patterns.strategy import (
    EnrolmentValidator, PrerequisiteValidation, 
    CapacityValidation, TimeConflictValidation
)
from patterns.observer import (
    EnrolmentEventManager, NotificationService, 
    WaitlistObserver, AdvisorObserver, SystemErrorObserver
)

class EnrolmentSystemFacade:
    """
    Facade providing a simplified, unified interface to the core system.
    Acts as the central orchestrator, managing domain entities and 
    delegating logic to specialized subsystems (Validator, Factory, EventManager)
    to ensure architectural decoupling and high cohesion.
    """
    
    def __init__(self):
        # Centralized State Management for Domain Entities
        self.users: Dict[str, User] = {}
        self.courses: Dict[str, Course] = {}
        self.enrolments: Dict[str, Enrolment] = {}
        self.grades: Dict[str, CourseGrade] = {}
        self.course_change_requests: List[Dict] = []
        self.degree_programs: Dict[str, Dict] = {}
        
        # Initialize Event Manager and Observers (Observer Pattern Setup)
        self.event_manager = EnrolmentEventManager()

        # The Facade maintains a composition relationship with NotificationService 
        # for direct data retrieval (e.g., getting history), but relies on the 
        # event_manager for asynchronous execution to maintain transactional decoupling.
        self.notification_service = NotificationService()
        self.event_manager.attach_observer(self.notification_service)
        
        self.waitlist_observer = WaitlistObserver(self)
        self.event_manager.attach_observer(self.waitlist_observer)
        
        self.advisor_observer = AdvisorObserver(self)
        self.event_manager.attach_observer(self.advisor_observer)
        
        self.error_observer = SystemErrorObserver(self)
        self.event_manager.attach_observer(self.error_observer)
        
        self._enrolment_counter = 0
        self._grade_counter = 0
        self._change_request_counter = 0
    
    # ---- USER MANAGEMENT ----
    def add_user(self, user_type: UserType, user_id: str, name: str, email: str, **kwargs) -> User:
        # Delegation: Utilizes Factory Pattern to abstract complex creation logic
        user = UserFactory.create_user(user_type, user_id, name, email, **kwargs)
        self.users[user_id] = user

        # Event Trigger: Decoupled notification of user creation
        self.event_manager.notify_observers("USER_CREATED", {"user_id": user_id, "type": user_type.value})
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def _is_admin(self, user_id: str) -> bool:
        return isinstance(self.get_user(user_id), Administrator)

    def update_user(self, admin_id: str, user_id: str, name: str = None,
                    email: str = None, major: str = None, department: str = None) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can edit accounts"
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email
        if isinstance(user, Student) and major is not None:
            user.major = major
        if isinstance(user, Faculty) and department is not None:
            user.department = department
        return True, f"Account {user_id} updated"

    def set_user_active(self, admin_id: str, user_id: str, active: bool) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can change account status"
        user = self.get_user(user_id)
        if not user or isinstance(user, Administrator):
            return False, "Only student and faculty accounts can be activated or deactivated"
        user.active = active
        return True, f"Account {user_id} {'activated' if active else 'deactivated'}"
    
    # ---- COURSE MANAGEMENT ----
    def create_course(self, course_id: str, name: str, description: str, instructor_id: str, 
                      department: str, capacity: int, schedule: CourseSchedule, prerequisites: set = None,
                      semester: str = "2026 Semester 2") -> Course:
        course = Course(
            course_id=course_id, name=name, description=description, instructor_id=instructor_id,
            department=department, capacity=capacity, available_seats=capacity, schedule=schedule,
            semester=semester, prerequisites=prerequisites or set()
        )
        self.courses[course_id] = course
        self.event_manager.notify_observers("COURSE_CREATED", {"course_id": course_id, "name": name})
        return course
    
    def get_course(self, course_id: str) -> Optional[Course]:
        return self.courses.get(course_id)

    def update_course(self, admin_id: str, course_id: str, description: str = None,
                      capacity: int = None, prerequisites: set = None,
                      semester: str = None) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can edit courses"
        course = self.get_course(course_id)
        if not course:
            return False, "Course not found"
        if capacity is not None and (capacity <= 0 or capacity < len(course.enrolled_students)):
            return False, "Capacity must be positive and cannot be below current enrolment"
        if description is not None:
            course.description = description
        if capacity is not None:
            course.available_seats += capacity - course.capacity
            course.capacity = capacity
        if prerequisites is not None:
            course.prerequisites = set(prerequisites)
        if semester is not None:
            course.semester = semester
        return True, f"Course {course_id} updated"

    def delete_course(self, admin_id: str, course_id: str) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can delete courses"
        course = self.get_course(course_id)
        if not course:
            return False, "Course not found"
        if course.enrolled_students:
            return False, "Cannot delete a course with enrolled students"
        del self.courses[course_id]
        return True, f"Course {course_id} deleted"
    
    def browse_courses_by_department(self, department: str) -> List[Course]:
        return [c for c in self.courses.values() if c.department == department]
    
    def search_courses(self, keyword: str) -> List[Course]:
        keyword_lower = keyword.lower()
        return [c for c in self.courses.values() if keyword_lower in c.name.lower() or keyword_lower in c.description.lower()]

    def get_courses_by_instructor(self, instructor_id: str) -> List[Course]:
        return [c for c in self.courses.values() if c.instructor_id == instructor_id]

    # ---- DEGREE PROGRAM MANAGEMENT ----
    def create_degree_program(self, admin_id: str, program_id: str, name: str,
                              required_courses: Dict[str, int]) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can manage degree programs"
        if program_id in self.degree_programs:
            return False, "Degree program already exists"
        if not required_courses or any(course_id not in self.courses or credits <= 0
                                       for course_id, credits in required_courses.items()):
            return False, "Each required course must exist and have positive credits"
        self.degree_programs[program_id] = {
            "program_id": program_id, "name": name,
            "required_courses": dict(required_courses), "credits": sum(required_courses.values()),
        }
        return True, f"Degree program {program_id} created"

    def update_degree_program(self, admin_id: str, program_id: str, name: str = None,
                              required_courses: Dict[str, int] = None) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can manage degree programs"
        program = self.degree_programs.get(program_id)
        if not program:
            return False, "Degree program not found"
        if required_courses is not None and (not required_courses or any(course_id not in self.courses or credits <= 0
                                                                         for course_id, credits in required_courses.items())):
            return False, "Each required course must exist and have positive credits"
        if name is not None:
            program["name"] = name
        if required_courses is not None:
            program["required_courses"] = dict(required_courses)
            program["credits"] = sum(required_courses.values())
        return True, f"Degree program {program_id} updated"

    def delete_degree_program(self, admin_id: str, program_id: str) -> tuple[bool, str]:
        if not self._is_admin(admin_id):
            return False, "Only administrators can manage degree programs"
        if program_id not in self.degree_programs:
            return False, "Degree program not found"
        del self.degree_programs[program_id]
        return True, f"Degree program {program_id} deleted"
    
    # ---- ENROLMENT MANAGEMENT ----
    def enrol_student(self, student_id: str, course_id: str) -> tuple[bool, str]:
        """Handles student enrolment with strict 'all-or-nothing' transaction semantics."""
        student = self.get_user(student_id)
        if not isinstance(student, Student) or not student.active: return False, "Invalid or inactive student"
        
        course = self.get_course(course_id)
        if not course: return False, "Course not found"
        if course_id in student.enrolled_courses: return False, "Student already enrolled in this course"

        # Strategy Pattern: Dynamically compose validation rules at runtime
        validator = EnrolmentValidator()
        validator.add_strategy(PrerequisiteValidation(course.prerequisites, student.completed_courses))
        validator.add_strategy(CapacityValidation(course.available_seats))
        validator.add_strategy(TimeConflictValidation(course.schedule, self._get_student_schedule_internal(student_id)))

        # Validation Phase: If any check fails, the transaction is immediately aborted
        is_valid, messages = validator.validate_all()
        if not is_valid:
            return False, f"Enrolment denied: {messages[-1]}"

        # Execution Phase: State transitions and data persistence
        self._enrolment_counter += 1
        enrolment = Enrolment(enrolment_id=f"ENR_{self._enrolment_counter}", student_id=student_id, course_id=course_id)

        # State Pattern: safely advance the lifecycle from PENDING to CONFIRMED
        enrolment.state = enrolment.state.transition()
        
        self.enrolments[enrolment.enrolment_id] = enrolment
        student.enrolled_courses.add(course_id)
        course.enrolled_students.add(student_id)
        course.available_seats -= 1

        # Event Phase: Transaction is complete. Publish event and yield control.
        self.event_manager.notify_observers("STUDENT_ENROLLED", {
            "student_id": student_id, "course_id": course_id, "enrolment_id": enrolment.enrolment_id
        })
        return True, (
            f"Enrolment confirmed for {course.name}. "
            "Your schedule and academic enrolment record have been updated."
        )
    
    def drop_course(self, student_id: str, course_id: str) -> tuple[bool, str]:
        student = self.get_user(student_id)
        if not isinstance(student, Student): return False, "Invalid student"
        
        course = self.get_course(course_id)
        if not course: return False, "Course not found"
        if course_id not in student.enrolled_courses: return False, "Student not enrolled in this course"
        
        student.enrolled_courses.remove(course_id)
        course.enrolled_students.remove(student_id)
        course.available_seats += 1
        
        self.event_manager.notify_observers("COURSE_DROPPED", {"student_id": student_id, "course_id": course_id})
        return True, f"Successfully dropped {course.name}"
    
    def get_student_schedule(self, student_id: str) -> List[Course]:
        student = self.get_user(student_id)
        if not isinstance(student, Student): return []
        return [self.get_course(cid) for cid in student.enrolled_courses if self.get_course(cid)]

    def get_student_past_schedule(self, student_id: str) -> List[Course]:
        """Returns completed courses that are no longer part of the active schedule."""
        student = self.get_user(student_id)
        if not isinstance(student, Student):
            return []
        return [self.get_course(course_id) for course_id in student.completed_courses
                if course_id not in student.enrolled_courses and self.get_course(course_id)]
    
    def _get_student_schedule_internal(self, student_id: str) -> List[CourseSchedule]:
        return [c.schedule for c in self.get_student_schedule(student_id)]
    
    # ---- FACULTY OPERATIONS ----
    def get_class_roster(self, faculty_id: str, course_id: str) -> List[Dict]:
        faculty = self.get_user(faculty_id)
        course = self.get_course(course_id)
        if not isinstance(faculty, Faculty) or not course or course.instructor_id != faculty_id: return []
        
        roster = []
        for s_id in course.enrolled_students:
            student = self.get_user(s_id)
            if isinstance(student, Student):
                roster.append({"student_id": s_id, "name": student.name, "email": student.email, "major": student.major})
        return roster
    
    def submit_grade(self, faculty_id: str, student_id: str, course_id: str, grade_value: float) -> tuple[bool, str]:
        """Handles grade submission and state lifecycle management."""
        faculty = self.get_user(faculty_id)
        course = self.get_course(course_id)
        if not isinstance(faculty, Faculty) or not faculty.active or not course or course.instructor_id != faculty_id:
            return False, "Unauthorized or invalid inputs"
        
        student = self.get_user(student_id)
        if not isinstance(student, Student) or student_id not in course.enrolled_students or not (0 <= grade_value <= 4.0):
            return False, "Invalid student or grade"

        existing_grade = next((grade for grade in self.grades.values()
                               if grade.student_id == student_id and grade.course_id == course_id), None)
        if existing_grade:
            if existing_grade.state.get_status() == "APPROVED":
                return False, "An approved grade cannot be changed"
            existing_grade.grade_value = grade_value
            return True, f"Grade {grade_value} corrected for {student_id}; Grade ID: {existing_grade.grade_id}; awaiting approval"
        
        self._grade_counter += 1
        grade = CourseGrade(grade_id=f"GRD_{self._grade_counter}", student_id=student_id, course_id=course_id, grade_value=grade_value)

        # State Pattern: Safely transition Pending -> Submitted for approval.
        grade.state = grade.state.transition()
        grade.submitted_date = datetime.now()
        
        self.grades[grade.grade_id] = grade
        
        self.event_manager.notify_observers("GRADE_SUBMITTED", {"student_id": student_id, "course_id": course_id, "grade": grade_value})
        return True, f"Grade {grade_value} submitted for {student_id}; Grade ID: {grade.grade_id}; awaiting approval"

    def submit_grades_batch(self, faculty_id: str, course_id: str, grade_entries: List[tuple[str, float]]) -> List[tuple[str, bool, str]]:
        """Processes each grade independently, preserving valid submissions if one fails."""
        return [(student_id, *self.submit_grade(faculty_id, student_id, course_id, grade_value))
                for student_id, grade_value in grade_entries]

    def get_pending_grades(self) -> List[CourseGrade]:
        return [grade for grade in self.grades.values() if grade.state.get_status() == "SUBMITTED"]

    def approve_grade(self, admin_id: str, grade_id: str) -> tuple[bool, str]:
        admin = self.get_user(admin_id)
        grade = self.grades.get(grade_id)
        if not isinstance(admin, Administrator):
            return False, "Only administrators can approve grades"
        if not grade or grade.state.get_status() != "SUBMITTED":
            return False, "Pending grade submission not found"
        student = self.get_user(grade.student_id)
        if not isinstance(student, Student):
            return False, "Student record not found"
        grade.state = grade.state.transition()
        student.completed_courses[grade.course_id] = grade.grade_value
        self.event_manager.notify_observers("GRADE_APPROVED", {"student_id": grade.student_id, "course_id": grade.course_id, "grade": grade.grade_value})
        return True, f"Grade {grade_id} approved and academic record updated"

    def submit_course_change_request(self, faculty_id: str, course_id: str,
                                     request: str = "", description: str = None,
                                     prerequisites: set = None, capacity: int = None) -> tuple[bool, str]:
        faculty = self.get_user(faculty_id)
        course = self.get_course(course_id)
        if not isinstance(faculty, Faculty) or not faculty.active or not course or course.instructor_id != faculty_id:
            return False, "Unauthorized or invalid course"
        if not request and description is None and prerequisites is None and capacity is None:
            return False, "At least one course change is required"
        if capacity is not None and (capacity < len(course.enrolled_students) or capacity <= 0):
            return False, "Capacity must be positive and cannot be below current enrolment"

        self._change_request_counter += 1
        change_request = {
            "request_id": f"CR_{self._change_request_counter}",
            "faculty_id": faculty_id,
            "course_id": course_id,
            "request": request,
            "description": description,
            "prerequisites": sorted(prerequisites) if prerequisites is not None else None,
            "capacity": capacity,
            "status": "PENDING",
        }
        self.course_change_requests.append(change_request)
        return True, f"Course change request {change_request['request_id']} submitted for approval"

    def get_pending_course_change_requests(self) -> List[Dict]:
        return [request for request in self.course_change_requests if request["status"] == "PENDING"]

    def approve_course_change_request(self, admin_id: str, request_id: str) -> tuple[bool, str]:
        if not isinstance(self.get_user(admin_id), Administrator):
            return False, "Only administrators can approve course changes"
        change_request = next((request for request in self.course_change_requests
                               if request["request_id"] == request_id), None)
        if not change_request or change_request["status"] != "PENDING":
            return False, "Pending course change request not found"
        course = self.get_course(change_request["course_id"])
        if not course:
            return False, "Course not found"
        if change_request["description"] is not None:
            course.description = change_request["description"]
        if change_request["prerequisites"] is not None:
            course.prerequisites = set(change_request["prerequisites"])
        if change_request["capacity"] is not None:
            course.available_seats += change_request["capacity"] - course.capacity
            course.capacity = change_request["capacity"]
        change_request["status"] = "APPROVED"
        return True, f"Course change request {request_id} approved"
    
    # ---- ADMINISTRATOR OPERATIONS ----
    def generate_enrolment_report(self, department: str = None, semester: str = None,
                                  minimum_utilization: float = None) -> Dict:
        report = {"timestamp": datetime.now().isoformat(), "filters": {
            "department": department, "semester": semester,
            "minimum_utilization": minimum_utilization,
        }, "departments": {}}
        filtered_courses = [course for course in self.courses.values()
                            if (not department or course.department.lower() == department.lower())
                            and (not semester or course.semester.lower() == semester.lower())
                            and (minimum_utilization is None or course.capacity == 0 or
                                 len(course.enrolled_students) / course.capacity >= minimum_utilization)]
        
        for course in filtered_courses:
            dept = course.department
            if dept not in report["departments"]: report["departments"][dept] = []
            report["departments"][dept].append({
                "course_id": course.course_id, "name": course.name, "enrolled": len(course.enrolled_students),
                "capacity": course.capacity, "semester": course.semester,
                "utilization": f"{(len(course.enrolled_students)/course.capacity)*100:.1f}%"
            })
        return report

    def generate_course_popularity_report(self, semester: str = None) -> Dict:
        courses = [course for course in self.courses.values()
                   if not semester or course.semester.lower() == semester.lower()]
        popularity = [{"course_id": course.course_id, "name": course.name,
                       "department": course.department, "semester": course.semester,
                       "enrolled": len(course.enrolled_students), "capacity": course.capacity,
                       "utilization": f"{(len(course.enrolled_students) / course.capacity) * 100:.1f}%"}
                      for course in courses]
        popularity.sort(key=lambda course: course["enrolled"], reverse=True)
        return {"timestamp": datetime.now().isoformat(), "semester": semester, "courses": popularity}
    
    def generate_faculty_workload_report(self) -> Dict:
        report = {"timestamp": datetime.now().isoformat(), "faculty": []}
        for user_id, user in self.users.items():
            if isinstance(user, Faculty):
                taught_courses = [c for c in self.courses.values() if c.instructor_id == user_id]
                report["faculty"].append({
                    "faculty_id": user_id, "name": user.name, "department": user.department,
                    "courses_taught": len(taught_courses), "total_students": sum(len(c.enrolled_students) for c in taught_courses)
                })
        return report

    def search_courses_by_instructor(self, instructor_name: str) -> List[Course]:
        """Search courses by the instructor's name"""
        matching_courses = []
        search_name = instructor_name.lower()
        
        for course in self.courses.values():
            instructor = self.get_user(course.instructor_id)
            if isinstance(instructor, Faculty) and search_name in instructor.name.lower():
                matching_courses.append(course)
                
        return matching_courses

    def admin_force_enrol(self, admin_id: str, student_id: str, course_id: str) -> tuple[bool, str]:
        """
        Administrator override: Force-add a student into a class.
        Intentionally bypasses the EnrolmentValidator (Strategy Pattern) to allow
        manual overrides of capacity and prerequisite restrictions.
        """
        admin = self.get_user(admin_id)
        if not isinstance(admin, Administrator):
            return False, "Unauthorized: Only administrators can force-enrol"
        
        student = self.get_user(student_id)
        course = self.get_course(course_id)
        
        if not isinstance(student, Student) or not student.active: return False, "Invalid or inactive student"
        if not course: return False, "Course not found"
        if course_id in student.enrolled_courses: return False, "Student already enrolled"
        
        
        self._enrolment_counter += 1
        enrolment = Enrolment(
            enrolment_id=f"ENR_{self._enrolment_counter}", 
            student_id=student_id, 
            course_id=course_id
        )

        # Proceed directly to state transition without Strategy validation
        enrolment.state = enrolment.state.transition() 
        self.enrolments[enrolment.enrolment_id] = enrolment
        
        student.enrolled_courses.add(course_id)
        course.enrolled_students.add(student_id)
        course.available_seats -= 1 
        
        self.event_manager.notify_observers("STUDENT_ENROLLED", {
            "student_id": student_id, 
            "course_id": course_id, 
            "enrolment_id": enrolment.enrolment_id,
            "note": "Forced added by Administrator"
        })
        
        return True, f"Admin {admin.name} successfully force-enrolled {student.name} into {course.name}"
    
    def get_notification_history(self) -> List[Dict]:
        return self.notification_service.get_notification_history()
