from abc import ABC, abstractmethod

class EnrolmentState(ABC):
    """Abstract state for enrolment"""
    @abstractmethod
    def transition(self) -> 'EnrolmentState':
        pass
    
    @abstractmethod
    def get_status(self) -> str:
        pass

class CompletedEnrolment(EnrolmentState):
    """Completed state"""
    def transition(self) -> EnrolmentState:
        return self  # Final state
    
    def get_status(self) -> str:
        return "COMPLETED"

class ConfirmedEnrolment(EnrolmentState):
    """Confirmed state"""
    def transition(self) -> EnrolmentState:
        return CompletedEnrolment()
    
    def get_status(self) -> str:
        return "CONFIRMED"

class PendingEnrolment(EnrolmentState):
    """Pending state"""
    def transition(self) -> EnrolmentState:
        return ConfirmedEnrolment()
    
    def get_status(self) -> str:
        return "PENDING"

class GradeState(ABC):
    """Abstract state for grades"""
    @abstractmethod
    def transition(self) -> 'GradeState':
        pass
    
    @abstractmethod
    def get_status(self) -> str:
        pass

class ApprovedGrade(GradeState):
    """Grade approved"""
    def transition(self) -> GradeState:
        return self  # Final state
    
    def get_status(self) -> str:
        return "APPROVED"

class SubmittedGrade(GradeState):
    """Grade submitted"""
    def transition(self) -> GradeState:
        return ApprovedGrade()
    
    def get_status(self) -> str:
        return "SUBMITTED"

class PendingGrade(GradeState):
    """Grade pending submission"""
    def transition(self) -> GradeState:
        return SubmittedGrade()
    
    def get_status(self) -> str:
        return "PENDING"