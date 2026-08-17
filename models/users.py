from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Set

class UserType(Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    ADMINISTRATOR = "administrator"

class User(ABC):
    """Abstract base class for all users"""
    def __init__(self, user_id: str, name: str, email: str):
        self.user_id = user_id
        self.name = name
        self.email = email
    
    @abstractmethod
    def get_user_type(self) -> str:
        pass

class Student(User):
    """Student user type"""
    def __init__(self, user_id: str, name: str, email: str, major: str, advisor_id: str = None):
        super().__init__(user_id, name, email)
        self.major = major
        self.advisor_id = advisor_id
        self.critical_courses: Set[str] = set()
        self.enrolled_courses: Set[str] = set()
        self.completed_courses: Dict[str, float] = {}
    
    def get_user_type(self) -> str:
        return UserType.STUDENT.value

class Faculty(User):
    """Faculty user type"""
    def __init__(self, user_id: str, name: str, email: str, department: str):
        super().__init__(user_id, name, email)
        self.department = department
        self.taught_courses: Set[str] = set()
    
    def get_user_type(self) -> str:
        return UserType.FACULTY.value

class Administrator(User):
    """Administrator user type"""
    def __init__(self, user_id: str, name: str, email: str, privilege_level: int = 1):
        super().__init__(user_id, name, email)
        self.privilege_level = privilege_level
    
    def get_user_type(self) -> str:
        return UserType.ADMINISTRATOR.value