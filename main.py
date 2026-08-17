import sys
from datetime import time
from core.facade import EnrolmentSystemFacade
from models.users import UserType, Student
from models.courses import CourseSchedule

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main():
    """Main demonstration of NexusEnroll system"""
    
    # Set console encoding to avoid character map errors in Windows
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    # Initialize the system
    system = EnrolmentSystemFacade()
    
    print_section("1. SETTING UP SAMPLE DATA")
    
    print("Creating users...")
    system.add_user(UserType.STUDENT, "S001", "Alice Johnson", "alice@nexus.edu", major="Computer Science")
    system.add_user(UserType.STUDENT, "S002", "Bob Smith", "bob@nexus.edu", major="Computer Science")
    system.add_user(UserType.STUDENT, "S003", "Carol White", "carol@nexus.edu", major="Mathematics")
    
    system.add_user(UserType.FACULTY, "F001", "Dr. Alan Turing", "turing@nexus.edu", department="Computer Science")
    system.add_user(UserType.FACULTY, "F002", "Dr. Emmy Noether", "noether@nexus.edu", department="Mathematics")
    
    system.add_user(UserType.ADMINISTRATOR, "A001", "System Admin", "admin@nexus.edu", privilege_level=3)
    print("[OK] Users created successfully\n")
    
    print("Creating courses...")
    system.create_course(
        "CS101", "Introduction to Computer Science", "Fundamentals of programming and computational thinking",
        "F001", "Computer Science", 30,
        CourseSchedule("CS101", {"MON", "WED", "FRI"}, time(9, 0), time(10, 30), "Tech Building Room 101")
    )
    
    system.create_course(
        "CS201", "Data Structures", "Study of advanced data structures and algorithms",
        "F001", "Computer Science", 25,
        CourseSchedule("CS201", {"TUE", "THU"}, time(11, 0), time(12, 30), "Tech Building Room 201"),
        prerequisites={"CS101"}
    )
    
    system.create_course(
        "MATH101", "Calculus I", "Differential and integral calculus",
        "F002", "Mathematics", 40,
        CourseSchedule("MATH101", {"MON", "WED", "FRI"}, time(14, 0), time(15, 30), "Science Building Room 301")
    )
    print("[OK] Courses created successfully\n")
    
    # ========================================================================
    print_section("2. DEMONSTRATING VALIDATION STRATEGIES (Strategy Pattern)")
    print("Testing course enrolment with different validation scenarios...\n")
    
    print("TEST 1: Alice enrolls in CS101 (no prerequisites required)")
    success, message = system.enrol_student("S001", "CS101")
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    print("TEST 2: Bob enrolls in MATH101")
    success, message = system.enrol_student("S002", "MATH101")
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    print("TEST 3: Alice enrolls in MATH101 (different schedule from CS101)")
    success, message = system.enrol_student("S001", "MATH101")
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    print("TEST 4: Alice tries CS201 (requires CS101 - should succeed now as she took it)")
    success, message = system.enrol_student("S001", "CS201")
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    print("TEST 5: Carol tries CS201 (requires CS101 - should fail)")
    success, message = system.enrol_student("S003", "CS201")
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    # ========================================================================
    print_section("3. STUDENT MODULE - COURSE BROWSING & SCHEDULE")
    
    print("Browsing Computer Science courses:")
    cs_courses = system.browse_courses_by_department("Computer Science")
    for course in cs_courses:
        print(f"  • {course.course_id}: {course.name} (Available: {course.available_seats}/{course.capacity})")
    print()
    
    print("Searching for 'Data' courses:")
    search_results = system.search_courses("Data")
    for course in search_results:
        print(f"  • {course.course_id}: {course.name}")
    print()
    
    print("Alice's Current Schedule:")
    alice_schedule = system.get_student_schedule("S001")
    for course in alice_schedule:
        print(f"  • {course.course_id}: {course.name}")
        print(f"    Time: {course.schedule.days} {course.schedule.start_time}-{course.schedule.end_time}")
        print(f"    Location: {course.schedule.location}")
    print()
    
    # ========================================================================
    print_section("4. STATE PATTERN DEMONSTRATION - GRADE SUBMISSION")
    print("Faculty submitting grades (demonstrating state transitions)...\n")
    
    print("Dr. Turing submitting grade for Alice in CS101:")
    success, message = system.submit_grade("F001", "S001", "CS101", 3.8)
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    print("Dr. Noether submitting grade for Bob in MATH101:")
    success, message = system.submit_grade("F002", "S002", "MATH101", 3.5)
    print(f"Result: {'[SUCCESS]' if success else '[FAILED]'} {message}\n")
    
    # ========================================================================
    print_section("5. FACULTY MODULE - CLASS ROSTER & MANAGEMENT")
    
    print("CS101 Class Roster (Dr. Turing's class):")
    roster = system.get_class_roster("F001", "CS101")
    for student in roster:
        print(f"  • {student['name']} ({student['student_id']}) - Major: {student['major']}")
    print()
    
    print("MATH101 Class Roster (Dr. Noether's class):")
    roster = system.get_class_roster("F002", "MATH101")
    for student in roster:
        print(f"  • {student['name']} ({student['student_id']}) - Major: {student['major']}")
    print()
    
    # ========================================================================
    print_section("6. ADMINISTRATOR MODULE - REPORTING & ANALYTICS")
    
    print("Enrolment Report by Department:\n")
    enrolment_report = system.generate_enrolment_report()
    for dept, courses in enrolment_report["departments"].items():
        print(f"Department: {dept}")
        for course in courses:
            print(f"  • {course['course_id']}: {course['name']}")
            print(f"    Enrolled: {course['enrolled']}/{course['capacity']} ({course['utilization']})")
    print()
    
    print("Faculty Workload Report:\n")
    workload_report = system.generate_faculty_workload_report()
    for faculty in workload_report["faculty"]:
        print(f"  • {faculty['name']} ({faculty['faculty_id']}) - {faculty['department']}")
        print(f"    Courses: {faculty['courses_taught']}, Students: {faculty['total_students']}")
    print()
    
    # ========================================================================
    print_section("7. DEMONSTRATION OF SYSTEM EVENTS (Triggering Observers)")
    
    print("-> Triggering a System Error...")
    system.event_manager.notify_observers(
        "SYSTEM_ERROR", 
        {"error_message": "Database connection timeout during nightly backup."}
    )
    print("[OK] System error event dispatched.\n")
    
    print("-> Triggering Advisor Notification (Alice dropping critical course)...")
    alice = system.get_user("S001")
    if isinstance(alice, Student):
        alice.advisor_id = "F001"
        alice.critical_courses.add("CS201")
        print("   (Alice S001 dropping CS201...)")
        system.drop_course("S001", "CS201")
        print("[OK] Critical course dropped. Advisor notified.\n")
    
    print("-> Triggering Waitlist Notification (Bob dropping MATH101)...")
    math101 = system.get_course("MATH101")
    if math101:
        # Add Carol to waitlist for MATH101
        math101.waitlisted_students.append("S003")
        print("   (Bob S002 dropping MATH101...)")
        system.drop_course("S002", "MATH101")
        print("[OK] Course dropped. Waitlisted student notified.\n")

    # ========================================================================
    print_section("8. OBSERVER PATTERN - COMPLETE NOTIFICATION HISTORY")
    print("All system notifications (Observer Pattern in action):\n")
    
    notifications = system.get_notification_history()
    for i, notif in enumerate(notifications, 1):
        print(f"{i}. [{notif['event']}] {notif['data']}")
    print()
    
    # ========================================================================
    print_section("SYSTEM SUMMARY")
    print(f"Total Users: {len(system.users)}")
    print(f"Total Courses: {len(system.courses)}")
    print(f"Total Enrolments: {len(system.enrolments)}")
    print(f"Total Grades: {len(system.grades)}")
    print(f"System Notifications: {len(system.get_notification_history())}")
    
    print("\n" + "="*70)
    print("  NexusEnroll Demo Complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()