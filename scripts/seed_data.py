import random
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.database_manager import DatabaseManager

def seed_university_data():
    db = DatabaseManager()
    print("⏳ Starting realistic data seeding...")

    # 1. Departments
    depts = ['Informatique', 'Mathématiques', 'Physique', 'Biologie', 'Chimie', 'Économie', 'Droit']
    for d in depts:
        db.execute_query("INSERT INTO departments (name) VALUES (%s) ON CONFLICT DO NOTHING", (d,), fetch=False)
    
    dept_ids = [r['id'] for r in db.execute_query("SELECT id FROM departments")]

    # 2. Names for realism
    first_names = ['Amine', 'Lydia', 'Yacine', 'Meriem', 'Mohamed', 'Sarah', 'Hamza', 'Anis', 'Imane', 'Ryad']
    last_names = ['Brahimi', 'Mansouri', 'Belaid', 'Ziane', 'Haddad', 'Kaci', 'Oubraham', 'Messaoudi']

    # 3. Seed Professors (with real names)
    print("👨‍🏫 Seeding Professors...")
    for d_id in dept_ids:
        prof_batch = []
        for _ in range(25): # 25 profs per dept
            full_name = f"Pr. {random.choice(first_names)} {random.choice(last_names)}"
            prof_batch.append((full_name, d_id, "Enseignant-Chercheur"))
        db.execute_batch("INSERT INTO professors (full_name, dept_id, specialization) VALUES %s", prof_batch)

    # 4. Formations & Modules
    print("📚 Seeding Formations & Modules...")
    all_depts = db.execute_query("SELECT id FROM departments")
    for d in all_depts:
        d_id = d['id']
        for i in range(1, 15): # 15 formations per dept
            f_name = f"Licence {random.choice(['GTR', 'MI', 'ST', 'Eco'])} - G{i}"
            db.execute_query("INSERT INTO formations (name, dept_id, level) VALUES (%s, %s, %s)", 
                             (f_name, d_id, random.choice(['L1', 'L2', 'L3'])), fetch=False)
            
            f_id = db.execute_query("SELECT id FROM formations WHERE name=%s", (f_name,))[0]['id']
            
            # 8 Modules per formation
            mod_batch = [(f"Module {f_id}-{m}", f"MOD{f_id}{m}", f_id) for m in range(1, 9)]
            db.execute_batch("INSERT INTO modules (name, code, formation_id) VALUES %s", mod_batch)

    # 5. Seed 13,000 Students with Realistic Emails
    print("👨‍🎓 Generating 13,000 students...")
    formation_ids = [r['id'] for r in db.execute_query("SELECT id FROM formations")]
    
    for chunk in range(13):
        student_batch = []
        for i in range(1000):
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            s_id = (chunk * 1000) + i
            email = f"{fn.lower()}.{ln.lower()}{s_id}@univ-alger.dz"
            student_batch.append((fn, ln, email, random.choice(formation_ids), 2025))
        
        db.execute_batch("INSERT INTO students (first_name, last_name, email, formation_id, promo) VALUES %s", student_batch)
        print(f"   > { (chunk+1)*1000 } students created...")

    # 6. Create Enrollments (The Link)
    print("🔗 Linking students to modules (130k rows)...")
    db.execute_query("""
        INSERT INTO enrollments (student_id, module_id)
        SELECT s.id, m.id FROM students s
        JOIN modules m ON s.formation_id = m.formation_id
    """, fetch=False)

    # 7. IMPORTANT: Create the Admin User for you to log in
    # We use a simple hash for now (in production we'd use bcrypt)
    print("🔐 Creating Admin access...")
    db.execute_query("""
        INSERT INTO users (email, password_hash, role) 
        VALUES ('admin@univ.dz', 'admin123', 'admin') 
        ON CONFLICT DO NOTHING
    """, fetch=False)

    print("✅ All data seeded. System ready for optimization tests.")

# 8. Create Sample Logins for Demo
    print("🔐 Creating Demo Accounts for all roles...")
    
    # Get one of each to link the accounts
    sample_prof = db.execute_query("SELECT id, email FROM professors LIMIT 1")[0] if False else \
                  db.execute_query("SELECT id, full_name FROM professors LIMIT 1")[0]
    sample_student = db.execute_query("SELECT id, email FROM students LIMIT 1")[0]
    sample_dept = db.execute_query("SELECT id, name FROM departments LIMIT 1")[0]

    demo_users = [
        # Email, Password, Role, linked_prof, linked_student, linked_dept
        ('admin@univ.dz', 'admin123', 'admin', None, None, None),
        ('doyen@univ.dz', 'doyen123', 'doyen', None, None, None),
        ('chef.dept@univ.dz', 'chef123', 'chef_dept', None, None, sample_dept['id']),
        (f"prof@univ.dz", 'prof123', 'professor', sample_prof['id'], None, None),
        (sample_student['email'], 'student123', 'student', None, sample_student['id'], None)
    ]

    for email, pwd, role, p_id, s_id, d_id in demo_users:
        db.execute_query("""
            INSERT INTO users (email, password_hash, role, linked_professor_id, linked_student_id, linked_dept_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (email, pwd, role, p_id, s_id, d_id), fetch=False)

if __name__ == "__main__":
    seed_university_data()