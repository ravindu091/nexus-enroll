from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, TYPE_CHECKING
from models.users import Student, Administrator

if TYPE_CHECKING:
    from core.facade import EnrolmentSystemFacade

class Observer(ABC):
    """
    Observer interface for the event-driven architecture.
    Provides a standardized contract (Liskov Substitution Principle) for all auxiliary tasks.
    """
    @abstractmethod
    def update(self, event: str, data: Dict) -> None:
        """Called by the EventManager when a system event occurs"""
        pass

class NotificationService(Observer):
    """Concrete Observer: Handles email notifications"""
    def __init__(self):
        self.notifications_sent = []
    
    def update(self, event: str, data: Dict) -> None:
        """Simulate sending email notifications"""
        notification = {
            'event': event,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        self.notifications_sent.append(notification)
        
    def get_notification_history(self) -> List[Dict]:
        return self.notifications_sent

class EnrolmentEventManager:
    """Subject: Manages observers and notifies them of enrolment events"""
    def __init__(self):
        self._observers: List[Observer] = []
    
    def attach_observer(self, observer: Observer) -> None:
        """Attach an observer"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def detach_observer(self, observer: Observer) -> None:
        """Detach an observer"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def notify_observers(self, event: str, data: Dict) -> None:
        """Notify all observers of an event"""
        for observer in self._observers:
            observer.update(event, data)

class WaitlistObserver(Observer):
    """
    Concrete Observer: Listens for course drops and notifies waitlisted students.
    Demonstrates Single Responsibility Principle: Moves complex waitlist queue processing 
    out of the main 'drop_course' transaction.
    """
    def __init__(self, facade: 'EnrolmentSystemFacade'):
        self.facade = facade 
    
    def update(self, event: str, data: Dict) -> None:
        if event == "COURSE_DROPPED":
            # Decoupled Execution: Processes waitlist only after course drop is confirmed
            course_id = data.get("course_id")
            course = self.facade.get_course(course_id)
            if course and course.waitlisted_students:
                next_student_id = course.waitlisted_students[0]
                self.facade.event_manager.notify_observers(
                    "WAITLIST_SPOT_OPENED",
                    {
                        "student_id": next_student_id,
                        "course_id": course_id,
                        "message": f"Good news! A spot has opened up in {course.name}."
                    }
                )


class AdvisorObserver(Observer):
    """
    Concrete Observer: Notifies academic advisors when advisees drop critical courses.
    Ensures the core enrolment engine does not need to query advisor relationships.
    """
    def __init__(self, facade: 'EnrolmentSystemFacade'):
        self.facade = facade
    
    def update(self, event: str, data: Dict) -> None:
        if event == "COURSE_DROPPED":
            student_id = data.get("student_id")
            course_id = data.get("course_id")
            student = self.facade.get_user(student_id)
            # Auxiliary Logic: Checks specific student properties asynchronously
            if isinstance(student, Student) and course_id in student.critical_courses:
                if student.advisor_id:
                    self.facade.event_manager.notify_observers(
                        "ADVISOR_ALERT",
                        {
                            "advisor_id": student.advisor_id,
                            "student_id": student_id,
                            "message": f"URGENT: Your advisee ({student.name}) just dropped a critical course: {course_id}"
                        }
                    )

class SystemErrorObserver(Observer):
    """Concrete Observer: Notifies all administrators of system-wide errors"""
    def __init__(self, facade: 'EnrolmentSystemFacade'):
        self.facade = facade
    
    def update(self, event: str, data: Dict) -> None:
        if event == "SYSTEM_ERROR":
            error_message = data.get("error_message", "Unknown error occurred")
            admin_ids = [u_id for u_id, u in self.facade.users.items() 
                        if isinstance(u, Administrator)]
            for admin_id in admin_ids:
                self.facade.event_manager.notify_observers(
                    "ADMIN_ERROR_ALERT",
                    {
                        "admin_id": admin_id,
                        "error_message": f"SYSTEM FAILURE DETECTED: {error_message}"
                    }
                )