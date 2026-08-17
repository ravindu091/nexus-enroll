from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Set, List, Optional
from patterns.state import EnrolmentState, PendingEnrolment, GradeState, PendingGrade

@dataclass
class CourseSchedule:
    """Represents course schedule"""
    course_id: str
    days: Set[str]  # {'MON', 'WED', 'FRI'}
    start_time: time
    end_time: time
    location: str

@dataclass
class Course:
    """Represents a course"""
    course_id: str
    name: str
    description: str
    instructor_id: str
    department: str
    capacity: int
    available_seats: int
    schedule: CourseSchedule
    prerequisites: Set[str] = field(default_factory=set)
    enrolled_students: Set[str] = field(default_factory=set)
    waitlisted_students: List[str] = field(default_factory=list)

@dataclass
class Enrolment:
    """Represents a student's enrolment in a course"""
    enrolment_id: str
    student_id: str
    course_id: str
    state: EnrolmentState = field(default_factory=PendingEnrolment)
    enrollment_date: datetime = field(default_factory=datetime.now)

@dataclass
class CourseGrade:
    """Represents a grade for a student in a course"""
    grade_id: str
    student_id: str
    course_id: str
    grade_value: Optional[float] = None
    state: GradeState = field(default_factory=PendingGrade)
    submitted_date: Optional[datetime] = None