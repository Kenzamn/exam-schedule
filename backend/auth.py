from backend.database_manager import DatabaseManager

class AuthManager:
    def __init__(self):
        self.db = DatabaseManager()

    def login(self, email, password):
        """
        Validates user credentials and returns full session data.
        """
        # Select all columns to ensure we get linked_dept_id
        query = "SELECT * FROM users WHERE email = %s AND is_active = TRUE"
        result = self.db.execute_query(query, (email,))

        if result:
            user = result[0]
            # Check password
            if user['password_hash'] == password:
                # We return the full context so the app knows 
                # exactly which professor and which department this user owns
                return {
                    "id": user['id'],
                    "email": user['email'],
                    "role": user['role'],
                    "linked_professor_id": user['linked_professor_id'],
                    "linked_student_id": user['linked_student_id'],
                    "linked_dept_id": user['linked_dept_id'] # This is the missing key!
                }
        
        return None