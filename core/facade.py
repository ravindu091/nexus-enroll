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
    
    # ---- COURSE MANAGEMENT ----
    def create_course(self, course_id: str, name: str, description: str, instructor_id: str, 
                      department: str, capacity: int, schedule: CourseSchedule, prerequisites: set = None) -> Course:
        course = Course(
            course_id=course_id, name=name, description=description, instructor_id=instructor_id,
            department=department, capacity=capacity, available_seats=capacity, schedule=schedule,
            prerequisites=prerequisites or set()
        )
        self.courses[course_id] = course
        self.event_manager.notify_observers("COURSE_CREATED", {"course_id": course_id, "name": name})
        return course
    
    def get_course(self, course_id: str) -> Optional[Course]:
        return self.courses.get(course_id)
    
    def browse_courses_by_department(self, department: str) -> List[Course]:
        return [c for c in self.courses.values() if c.department == department]
    
    def search_courses(self, keyword: str) -> List[Course]:
        keyword_lower = keyword.lower()
        return [c for c in self.courses.values() if keyword_lower in c.name.lower() or keyword_lower in c.description.lower()]

    def get_courses_by_instructor(self, instructor_id: str) -> List[Course]:
        return [c for c in self.courses.values() if c.instructor_id == instructor_id]
    
    # ---- ENROLMENT MANAGEMENT ----
    def enrol_student(self, student_id: str, course_id: str) -> tuple[bool, str]:
        """Handles student enrolment with strict 'all-or-nothing' transaction semantics."""
        student = self.get_user(student_id)
        if not isinstance(student, Student): return False, "Invalid student"
        
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
        if not is_valid: return False, messages[0]

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
        return True, f"Successfully enrolled in {course.name}"
    
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
        if not isinstance(faculty, Faculty) or not course or course.instructor_id != faculty_id:
            return False, "Unauthorized or invalid inputs"
        
        student = self.get_user(student_id)
        if not isinstance(student, Student) or not (0 <= grade_value <= 4.0):
            return False, "Invalid student or grade"
        
        self._grade_counter += 1
        grade = CourseGrade(grade_id=f"GRD_{self._grade_counter}", student_id=student_id, course_id=course_id, grade_value=grade_value)

        # State Pattern: Safely transition Pending -> Submitted -> Approved
        grade.state = grade.state.transition()
        grade.state = grade.state.transition()
        grade.submitted_date = datetime.now()
        
        self.grades[grade.grade_id] = grade
        student.completed_courses[course_id] = grade_value
        
        self.event_manager.notify_observers("GRADE_SUBMITTED", {"student_id": student_id, "course_id": course_id, "grade": grade_value})
        return True, f"Grade {grade_value} submitted for student {student_id}"
    
    # ---- ADMINISTRATOR OPERATIONS ----
    def generate_enrolment_report(self, department: str = None) -> Dict:
        report = {"timestamp": datetime.now().isoformat(), "departments": {}}
        filtered_courses = (self.courses.values() if not department else [c for c in self.courses.values() if c.department == department])
        
        for course in filtered_courses:
            dept = course.department
            if dept not in report["departments"]: report["departments"][dept] = []
            report["departments"][dept].append({
                "course_id": course.course_id, "name": course.name, "enrolled": len(course.enrolled_students),
                "capacity": course.capacity, "utilization": f"{(len(course.enrolled_students)/course.capacity)*100:.1f}%"
            })
        return report
    
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
        
        if not isinstance(student, Student): return False, "Invalid student"
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