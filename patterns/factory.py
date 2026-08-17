from models.users import User, UserType, Student, Faculty, Administrator

class UserFactory:
    """Factory for creating user objects"""
    @staticmethod
    def create_user(user_type: UserType, user_id: str, name: str, 
                   email: str, **kwargs) -> User:
        """Factory method to create users"""
        if user_type == UserType.STUDENT:
            return Student(user_id, name, email, kwargs.get('major', 'Undeclared'))
        elif user_type == UserType.FACULTY:
            return Faculty(user_id, name, email, kwargs.get('department', 'General'))
        elif user_type == UserType.ADMINISTRATOR:
            return Administrator(user_id, name, email, kwargs.get('privilege_level', 1))
        else:
            raise ValueError(f"Unknown user type: {user_type}")