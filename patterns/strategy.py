from abc import ABC, abstractmethod
from typing import Dict, List, Set
from models.courses import CourseSchedule

class ValidationStrategy(ABC):
    """
    Abstract validation strategy.
    Adheres to the Open/Closed Principle: New validation rules can be added 
    by creating new subclasses without modifying the EnrolmentValidator core logic.
    """
    @abstractmethod
    def validate(self, context: Dict) -> tuple[bool, str]:
        """
        Executes the specific validation rule.
        Returns (is_valid, message). The 'context' dict allows for future extensibility 
        without changing the method signature.
        """
        pass

class PrerequisiteValidation(ValidationStrategy):
    """Validates that student has completed prerequisites"""
    def __init__(self, required_prerequisites: Set[str], 
                 student_completed: Dict[str, float]):
        self.required_prerequisites = required_prerequisites
        self.student_completed = student_completed
    
    def validate(self, context: Dict) -> tuple[bool, str]:
        for prereq in self.required_prerequisites:
            if prereq not in self.student_completed:
                return False, f"Missing prerequisite: {prereq}"
        return True, "Prerequisites satisfied"

class CapacityValidation(ValidationStrategy):
    """Validates that course has available capacity"""
    def __init__(self, available_seats: int):
        self.available_seats = available_seats
    
    def validate(self, context: Dict) -> tuple[bool, str]:
        if self.available_seats <= 0:
            return False, "Course is at full capacity"
        return True, "Capacity available"

class TimeConflictValidation(ValidationStrategy):
    """Validates that course doesn't conflict with enrolled courses"""
    def __init__(self, new_course_schedule: CourseSchedule, 
                 student_schedule: List[CourseSchedule]):
        self.new_course_schedule = new_course_schedule
        self.student_schedule = student_schedule
    
    def validate(self, context: Dict) -> tuple[bool, str]:
        for scheduled_course in self.student_schedule:
            if self._has_conflict(self.new_course_schedule, scheduled_course):
                return False, f"Time conflict with existing course: {scheduled_course.course_id}"
        return True, "No time conflicts"
    
    def _has_conflict(self, schedule1: CourseSchedule, 
                     schedule2: CourseSchedule) -> bool:
        """Check if two schedules conflict"""
        if not schedule1.days & schedule2.days:
            return False
        
        start1, end1 = schedule1.start_time, schedule1.end_time
        start2, end2 = schedule2.start_time, schedule2.end_time
        return not (end1 <= start2 or end2 <= start1)

class EnrolmentValidator:
    """
    Context manager utilizing the Strategy pattern.
    Decouples the business rule algorithms from the main Facade transaction logic.
    """
    def __init__(self):
        self.strategies: List[ValidationStrategy] = []
    
    def add_strategy(self, strategy: ValidationStrategy) -> None:
        """Dynamically compose validation rules at runtime (Composition over Inheritance)."""
        self.strategies.append(strategy)
    
    def validate_all(self) -> tuple[bool, List[str]]:
        """
        Validate using all attached strategies.
        Enforces the 'all-or-nothing' transaction requirement: if a single strategy fails, 
        it immediately returns False, preventing partial state changes.
        """
        messages = []
        for strategy in self.strategies:
            is_valid, message = strategy.validate({})
            messages.append(message)
            if not is_valid:
                return False, messages
        return True, messages