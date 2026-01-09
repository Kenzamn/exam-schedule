import sys
import os
from datetime import datetime, date

# Add the parent directory (project root) to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import time
import pandas as pd
from backend.database_manager import DatabaseManager
from backend.auth import AuthManager
from backend.scheduler_engine import SchedulerEngine

# Page Config
st.set_page_config(page_title="Univ-Alger Exam Manager", layout="wide")

# Initialize Managers
auth = AuthManager()
db = DatabaseManager()

# --- LOGIN PAGE ---
def login_page():
    st.title("🎓 University Exam System")
    with st.container():
        st.subheader("Login Portal")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", use_container_width=True):
            user = auth.login(email, password)
            if user:
                st.session_state['user'] = user
                st.rerun()
            else:
                st.error("Invalid credentials")

# --- STUDENT DASHBOARD ---
def show_student_dashboard():
    user = st.session_state['user']
    st.header(f"🎓 Student Exam Portal")
    
    student_info = db.execute_query("SELECT id, first_name, last_name FROM students WHERE email = %s", (user['email'],))
    
    if student_info:
        s = student_info[0]
        st.subheader(f"Welcome, {s['first_name']} {s['last_name']}")
        
        # ✅ CRITICAL FIX: Check if schedule is published
        session_status = db.execute_query("""
            SELECT is_active, name 
            FROM exam_sessions 
            WHERE id = 1
        """)
        
        if not session_status or not session_status[0]['is_active']:
            st.info("📅 Exam schedule is not yet available. Please check back later.")
            st.warning("⏳ The schedule is currently under review by the Dean's office.")
            return
        
        # Only fetch exams if schedule is published
        my_exams = db.execute_query("""
            SELECT 
                m.name as "Module", 
                e.exam_date as "Date", 
                e.start_time as "Time", 
                r.name as "Assigned Room",
                e.duration_minutes as "Duration"
            FROM student_seating ss
            JOIN exams e ON ss.exam_id = e.id
            JOIN exam_rooms r ON e.room_id = r.id
            JOIN modules m ON e.module_id = m.id
            WHERE ss.student_id = %s 
            AND e.session_id = 1
            ORDER BY e.exam_date, e.start_time
        """, (s['id'],))

        if my_exams:
            df = pd.DataFrame(my_exams)
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%A, %b %d, %Y')
            st.success("✅ Your exam schedule is now official!")
            st.table(df)
            st.info("💡 Don't Forget To Bring Your Student ID!")
        else:
            st.warning("No room assignments found. Please contact administration.")

# --- PROFESSOR DASHBOARD ---
# --- PROFESSOR DASHBOARD ---
def show_professor_dashboard():
    user = st.session_state['user']
    st.header("👨‍🏫 Professor Surveillance Portal")
    
    prof_info = db.execute_query("SELECT id, full_name FROM professors WHERE email = %s", (user['email'],))
    
    if prof_info:
        p = prof_info[0]
        st.subheader(f"Welcome, Prof. {p['full_name']}")
        
        # ✅ CRITICAL FIX: Check if schedule is published
        session_status = db.execute_query("""
            SELECT is_active, name 
            FROM exam_sessions 
            WHERE id = 1
        """)
        
        if not session_status or not session_status[0]['is_active']:
            st.info("📅 Exam surveillance assignments are not yet available.")
            st.warning("⏳ The schedule is currently under review by the Dean's office.")
            return
        
        # Only fetch surveillances if schedule is published
        my_surveillances = db.execute_query("""
            SELECT 
                e.id as "Exam ID",
                m.name as "Module", 
                e.exam_date as "Date", 
                e.start_time as "Time", 
                r.name as "Room",
                e.expected_students as "Expected"
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN exam_rooms r ON e.room_id = r.id
            WHERE e.professor_id = %s
            AND e.session_id = 1
            ORDER BY e.exam_date, e.start_time
        """, (p['id'],))

        if my_surveillances:
            df = pd.DataFrame(my_surveillances)
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%b %d, %Y')
            st.success("✅ Your surveillance schedule is now official!")
            st.dataframe(df.drop(columns=["Exam ID"]), use_container_width=True)
            
            st.divider()
            
            st.subheader("📋 Room Attendance List")
            exam_labels = {f"{row['Module']} - {row['Room']} ({row['Time']})": row for row in my_surveillances}
            selected_label = st.selectbox("Select Exam to view Students:", list(exam_labels.keys()))
            
            if selected_label:
                exam_data = exam_labels[selected_label]
                e_id = exam_data['Exam ID']
                expected = exam_data['Expected']

                student_list = db.execute_query("""
                    SELECT s.id as "ID", s.last_name as "Last Name", s.first_name as "First Name"
                    FROM student_seating ss
                    JOIN students s ON ss.student_id = s.id
                    WHERE ss.exam_id = %s
                    ORDER BY s.last_name, s.first_name
                """, (e_id,))
                
                if student_list:
                    count = len(student_list)
                    fill_pct = min(100, int((count / expected) * 100)) if expected > 0 else 0
                    
                    st.write(f"**Room Status:** {count} / {expected} Students Seated")
                    st.progress(fill_pct / 100)
                    
                    st.dataframe(pd.DataFrame(student_list), use_container_width=True)
                    
                    csv = pd.DataFrame(student_list).to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download List", csv, f"attendance_room_{e_id}.csv", "text/csv")
                else:
                    st.error("❌ No students seated in this room yet.")
        else:
            st.info("No surveillance sessions assigned yet.")

# --- ADMIN DASHBOARD ---
def show_admin_dashboard():
    st.header("🛠️ Planning Service Dashboard")
    
    with st.expander("📅 Set Exam Session Dates", expanded=True):
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            session_name = st.text_input("Session Name", "Final Exams Winter 2026")
            start_dt = st.date_input("Exam Start Date", date(2026, 1, 5))
        with col_date2:
            st.write("") 
            st.write("") 
            end_dt = st.date_input("Exam End Date", date(2026, 1, 20))

    stats_data = db.execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM students) as s_count,
            (SELECT COUNT(*) FROM modules) as m_count,
            (SELECT COUNT(*) FROM exams) as e_count,
            (SELECT COUNT(*) FROM professors) as p_count,
            (SELECT COUNT(*) FROM exam_rooms) as r_count
    """)
    stats = stats_data[0] if stats_data else {'s_count':0, 'm_count':0, 'e_count':0, 'p_count':0, 'r_count':0}
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Students", f"{stats['s_count']:,}")
    col2.metric("Modules", stats['m_count'])
    col3.metric("Professors", stats['p_count'])
    col4.metric("Total Rooms", stats['r_count'])
    col5.metric("Exam Slots", stats['e_count'])

    st.divider()

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.subheader("Run Optimization Engine")
        if st.button("🚀 Generate Schedule", use_container_width=True):
            if start_dt >= end_dt:
                st.error("Error: Start date must be before End date.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                engine = SchedulerEngine()
                def update_ui(msg, val):
                    status_text.text(msg)
                    progress_bar.progress(val)
                count = engine.run_custom(name=session_name, start=start_dt, end=end_dt, progress_callback=update_ui)
                st.success(f"✅ {count} Modules Scheduled!")
                st.rerun()

    with col_btn2:
        st.subheader("Seating Management")
        if st.button("🪑 Repair & Fill Student Seats", use_container_width=True):
            with st.spinner("Assigning one unique room per student..."):
                # 1. Clear current seating
                db.execute_query("DELETE FROM student_seating", fetch=False)
                
                # 2. Logic: Ensure one student gets ONLY one room per module
                db.execute_query("""
                    WITH SortedSeats AS (
                        SELECT 
                            en.student_id, 
                            e.id as exam_id,
                            -- Rank rooms for the SAME student/module so we only pick one
                            ROW_NUMBER() OVER (PARTITION BY en.student_id, e.module_id ORDER BY e.id) as room_rank,
                            -- Rank students inside each room to respect capacity
                            ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY en.student_id) as seat_num,
                            CASE WHEN r.name LIKE '%AMPHI%' THEN 100 ELSE 20 END as cap
                        FROM enrollments en
                        JOIN exams e ON en.module_id = e.module_id
                        JOIN exam_rooms r ON e.room_id = r.id
                    )
                    INSERT INTO student_seating (student_id, exam_id)
                    SELECT student_id, exam_id FROM SortedSeats
                    WHERE room_rank = 1  -- CRITICAL: Only assign the student to the FIRST available room
                    AND seat_num <= cap   -- Respect 20/100 limit
                    ON CONFLICT DO NOTHING
                """, fetch=False)
                
                # Cleanup empty exams
                db.execute_query("DELETE FROM exams WHERE id NOT IN (SELECT exam_id FROM student_seating)", fetch=False)
                st.success("Seating assignments repaired! Duplicates removed.")
                st.rerun()

    # --- Infrastructure Viewer ---
    st.divider()
    with st.expander("🏢 Infrastructure & Room Viewer"):
        dept_view = st.selectbox("View Rooms by Department:", ["All", "DEPT1", "DEPT2", "DEPT3", "DEPT4", "DEPT5", "DEPT6", "DEPT7"])
        r_query = "SELECT name, capacity as physical_cap, (CASE WHEN name LIKE '%AMPHI%' THEN 100 ELSE 20 END) as exam_cap FROM exam_rooms"
        if dept_view != "All":
            r_query += f" WHERE name LIKE '{dept_view}%'"
        r_query += " ORDER BY name"
        rooms_df = pd.DataFrame(db.execute_query(r_query))
        st.dataframe(rooms_df, use_container_width=True, height=300)

    if stats['e_count'] > 0:
        st.subheader("🗓️ Generated Schedule Preview")
        preview = db.execute_query("""
            SELECT m.name as "Module", e.exam_date as "Date", e.start_time as "Time", r.name as "Room", p.full_name as "Professor"
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN exam_rooms r ON e.room_id = r.id
            JOIN professors p ON e.professor_id = p.id
            ORDER BY e.exam_date, e.start_time LIMIT 15
        """)
        if preview:
            st.dataframe(pd.DataFrame(preview), use_container_width=True)

    st.markdown("---")
    with st.expander("⚠️ Danger Zone"):
        if st.button("🗑️ Reset All Exams & Seating", use_container_width=True):
            db.execute_query("DELETE FROM student_seating", fetch=False)
            db.execute_query("DELETE FROM exams", fetch=False)
            st.warning("All data cleared.")
            st.rerun()

def show_doyen_dashboard():
    # Force wide layout for a professional feel
    st.header("🏛️ Strategic Dean Dashboard")
    
    engine = SchedulerEngine()
    db = engine.db
    
    # 1. FETCH LIVE STATUS (Crucial for fixing the "Pending" bug)
    session_info = db.execute_query("SELECT is_active, name FROM exam_sessions WHERE id = 1")
    is_active = session_info[0]['is_active'] if session_info else False
    
    analytics = engine.get_dean_dashboard(session_id=1)
    if not analytics or not analytics.get('summary'):
        st.warning("⚠️ No exams scheduled yet. Please run the engine first.")
        return

    summary_data = analytics['summary']

    # 2. CALCULATION: Real Utilization
    real_util_query = db.execute_query("""
        SELECT 
            ROUND(
                (SUM(e.expected_students)::numeric / 
                NULLIF(SUM(r.capacity), 0)::numeric) * 100, 2
            ) as real_rate
        FROM exams e
        JOIN exam_rooms r ON e.room_id = r.id
        WHERE e.session_id = 1
    """)
    real_rate = real_util_query[0]['real_rate'] if real_util_query and real_util_query[0]['real_rate'] else 0

    # --- TOP METRICS BAR ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Seat Utilization", f"{real_rate}%")
    c2.metric("Active Professors", summary_data.get('active_profs', 0))
    c3.metric("Total Unique Exams", summary_data.get('total_unique_exams', 0))
    
    # Dynamic Status Metric
    status_label = "PUBLISHED" if is_active else "PENDING"
    status_delta = "Live" if is_active else "Draft"
    c4.metric("Status", status_label, delta=status_delta, delta_color="normal" if is_active else "inverse")

    st.divider()

    # --- 1. STRATEGIC AUDIT (Integrity & Fairness) ---
    st.subheader("🕵️ Academic Integrity Audit")
    
    col_a, col_b = st.columns(2)
    with col_a:
        # Integrity: 1 Exam/Day Check
        student_conflicts = db.execute_query("""
            SELECT f.name as formation, e.exam_date, COUNT(DISTINCT e.module_id) as unique_exams_today
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            WHERE e.session_id = 1
            GROUP BY f.name, e.exam_date
            HAVING COUNT(DISTINCT e.module_id) > 1
        """)
        if not student_conflicts:
            st.success("✅ Student Load: 1 Exam/Day rule respected.")
        else:
            st.error(f"🚩 Conflict: {len(student_conflicts)} overloads detected!")
            with st.expander("View Overloaded Specialties"):
                st.table(pd.DataFrame(student_conflicts))

    with col_b:
        # Fairness: Professor Workload Gap (7h Rule)
        load_gap_query = db.execute_query("""
            SELECT COALESCE(MAX(cnt) - MIN(cnt), 0) as gap
            FROM (
                SELECT COUNT(id) as cnt FROM exams WHERE session_id = 1 GROUP BY professor_id
            ) sub
        """)
        gap_val = load_gap_query[0]['gap'] if load_gap_query else 0
        
        if gap_val <= 7:
            st.success(f"✅ Professor Fairness: Gap is {gap_val} (Healthy < 7)")
        else:
            st.warning(f"⚖️ Fairness Warning: Gap is {gap_val} (High workload variation)")

    st.divider()

    # --- 2. ADVANCED ANALYTICS ---
    st.subheader("📊 Operational Insights")
    graph_col1, graph_col2 = st.columns(2)

    with graph_col1:
        st.write("**Daily Exam Volume**")
        daily_occ = db.execute_query("""
            SELECT exam_date, COUNT(DISTINCT module_id) as exam_count
            FROM exams WHERE session_id = 1 GROUP BY exam_date ORDER BY exam_date
        """)
        if daily_occ:
            df_occ = pd.DataFrame(daily_occ)
            st.area_chart(df_occ.set_index('exam_date'))

    with graph_col2:
        st.write("**Exams per Specialty**")
        dept_stats = db.execute_query("""
            SELECT f.name as formation, COUNT(e.id) as sessions
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            WHERE e.session_id = 1
            GROUP BY f.name ORDER BY sessions DESC
        """)
        if dept_stats:
            df_dept = pd.DataFrame(dept_stats)
            st.bar_chart(df_dept.set_index('formation'))

    st.divider()

    # --- 3. FINAL VALIDATION (Decision Zone) ---
    st.subheader("🏁 Final Schedule Validation")
    v_col1, v_col2, v_col3 = st.columns([1, 1, 2])
    
    if not is_active:
        if v_col1.button("✅ APPROVE & PUBLISH", use_container_width=True, type="primary"):
            db.execute_query("UPDATE exam_sessions SET is_active = true WHERE id = 1", fetch=False)
            st.balloons()
            st.success("The schedule is now OFFICIAL.")
            st.rerun() # Forces the dashboard to update the status metric
    else:
        if v_col1.button("❌ REVOKE PUBLICATION", use_container_width=True, type="secondary"):
            db.execute_query("UPDATE exam_sessions SET is_active = false WHERE id = 1", fetch=False)
            st.warning("Schedule reverted to Draft mode.")
            st.rerun()

    if v_col2.button("❌ REJECT / RESET", use_container_width=True):
        st.error("Schedule flagged for review. Administrator notified.")
        
    with v_col3:
        if is_active:
            st.info("ℹ️ Schedule is currently visible to students and faculty.")
        else:
            st.info("ℹ️ Approval will release the schedule to the Student and Professor portals.")


def show_chef_dept_dashboard():
    """
    Chef de Département Portal
    - View department schedule
    - Validate department exams
    - Monitor conflicts by formation
    - Department statistics
    """
    user = st.session_state.get('user')
    db = DatabaseManager()
    
    dept_id = user.get('linked_dept_id')
    
    if not dept_id:
        st.error("Department ID missing. Please contact administration.")
        return

    # Fetch Department Info
    dept_info = db.execute_query("SELECT name FROM departments WHERE id = %s", (dept_id,))
    dept_name = dept_info[0]['name'] if dept_info else f"Department {dept_id}"

    # Check if schedule is published
    session_status = db.execute_query("SELECT is_active, name FROM exam_sessions WHERE id = 1")
    is_active = session_status[0]['is_active'] if session_status else False

    st.header(f"{dept_name} - Department Head Portal")

    if not is_active:
        st.info("Exam schedule is currently under Dean review. Preview mode active.")
    
    # --- COMPREHENSIVE DEPARTMENT STATISTICS ---
    stats = db.execute_query("""
        WITH dept_overview AS (
            SELECT 
                COUNT(DISTINCT f.id) as total_formations,
                COUNT(DISTINCT m.id) as total_modules,
                COUNT(DISTINCT e.id) as total_exam_sessions,
                COUNT(DISTINCT e.professor_id) as professors_assigned,
                SUM(CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END) as scheduled_modules,
                COUNT(DISTINCT s.id) as total_students
            FROM formations f
            LEFT JOIN modules m ON f.id = m.formation_id
            LEFT JOIN exams e ON m.id = e.module_id AND e.session_id = 1
            LEFT JOIN enrollments en ON m.id = en.module_id
            LEFT JOIN students s ON en.student_id = s.id
            WHERE f.dept_id = %s
        ),
        exam_days AS (
            SELECT COUNT(DISTINCT e.exam_date) as active_days
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            WHERE f.dept_id = %s AND e.session_id = 1
        )
        SELECT 
            o.*,
            d.active_days
        FROM dept_overview o
        CROSS JOIN exam_days d
    """, (dept_id, dept_id))
    
    overview = stats[0] if stats else {}

    # --- KEY METRICS ---
    st.subheader("Department Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Formations", overview.get('total_formations', 0))
        st.caption("Specialties managed")
    
    with col2:
        st.metric("Total Modules", overview.get('total_modules', 0))
        st.caption("Courses to examine")
    
    with col3:
        scheduled = overview.get('scheduled_modules', 0)
        total = overview.get('total_modules', 1)
        completion = int((scheduled / total * 100)) if total > 0 else 0
        st.metric("Scheduled", f"{completion}%")
        st.caption(f"{scheduled}/{total} modules")
    
    with col4:
        st.metric("Exam Days", overview.get('active_days', 0))
        st.caption("Days with exams")
    
    with col5:
        st.metric("Students", f"{overview.get('total_students', 0):,}")
        st.caption("Total enrolled")

    st.divider()

    # --- CONFLICT DETECTION & VALIDATION ---
    st.subheader("Academic Integrity Validation")
    
    # Check for scheduling conflicts
    conflicts = db.execute_query("""
        SELECT 
            f.name as formation,
            e.exam_date,
            COUNT(DISTINCT e.module_id) as exams_same_day,
            string_agg(m.name, ', ') as conflicting_modules
        FROM exams e
        JOIN modules m ON e.module_id = m.id
        JOIN formations f ON m.formation_id = f.id
        WHERE f.dept_id = %s AND e.session_id = 1
        GROUP BY f.name, e.exam_date
        HAVING COUNT(DISTINCT e.module_id) > 1
        ORDER BY e.exam_date, f.name
    """, (dept_id,))

    val_col1, val_col2 = st.columns(2)
    
    with val_col1:
        if not conflicts:
            st.success("No scheduling conflicts detected")
            st.caption("All formations respect 1 exam per day rule")
        else:
            st.error(f"Found {len(conflicts)} conflict(s)")
            st.caption("Multiple exams scheduled on same day")
    
    with val_col2:
        # Check professor workload for this department
        dept_profs = db.execute_query("""
            SELECT 
                MAX(cnt) - MIN(cnt) as workload_gap
            FROM (
                SELECT professor_id, COUNT(id) as cnt
                FROM exams e
                JOIN modules m ON e.module_id = m.id
                JOIN formations f ON m.formation_id = f.id
                WHERE f.dept_id = %s AND e.session_id = 1
                GROUP BY professor_id
            ) sub
        """, (dept_id,))
        
        gap = dept_profs[0]['workload_gap'] if dept_profs and dept_profs[0]['workload_gap'] else 0
        
        if gap <= 5:
            st.success(f"Balanced workload (gap: {gap})")
            st.caption("Fair distribution across faculty")
        else:
            st.warning(f"Workload imbalance (gap: {gap})")
            st.caption("Some professors overloaded")

    # Show detailed conflicts if any
    if conflicts:
        st.divider()
        st.markdown("**Detailed Conflict Report**")
        conflict_df = pd.DataFrame(conflicts)
        conflict_df['exam_date'] = pd.to_datetime(conflict_df['exam_date']).dt.strftime('%A, %B %d, %Y')
        st.dataframe(conflict_df, use_container_width=True, hide_index=True)
        
        st.error("Action Required: These conflicts must be resolved before dean approval.")

    st.divider()

    # --- FORMATION-LEVEL BREAKDOWN ---
    st.subheader("Formation Statistics")
    
    formation_stats = db.execute_query("""
        SELECT 
            f.name as formation,
            COUNT(DISTINCT m.id) as total_modules,
            COUNT(DISTINCT e.id) as scheduled_sessions,
            COUNT(DISTINCT e.exam_date) as exam_days,
            COUNT(DISTINCT e.professor_id) as professors_used,
            SUM(e.expected_students) as total_student_slots
        FROM formations f
        LEFT JOIN modules m ON f.id = m.formation_id
        LEFT JOIN exams e ON m.id = e.module_id AND e.session_id = 1
        WHERE f.dept_id = %s
        GROUP BY f.id, f.name
        ORDER BY f.name
    """, (dept_id,))
    
    if formation_stats:
        st.dataframe(pd.DataFrame(formation_stats), use_container_width=True, hide_index=True)
    else:
        st.info("No formations found for this department.")

    st.divider()

    # --- DETAILED SCHEDULE VIEW ---
    st.subheader("Complete Department Schedule")
    
    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    
    with filter_col1:
        formations = db.execute_query("""
            SELECT DISTINCT f.id, f.name 
            FROM formations f 
            WHERE f.dept_id = %s 
            ORDER BY f.name
        """, (dept_id,))
        
        formation_options = ["All Formations"] + [f['name'] for f in formations]
        selected_formation = st.selectbox("Filter by Formation", formation_options)
    
    with filter_col2:
        view_mode = st.radio("View Mode", ["By Date", "By Formation"], horizontal=True)

    # Build query based on filters
    if selected_formation == "All Formations":
        schedule_query = """
            SELECT 
                m.name as "Module",
                f.name as "Formation",
                e.exam_date as "Date",
                e.start_time as "Time",
                r.name as "Room",
                p.full_name as "Professor",
                e.expected_students as "Students"
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN exam_rooms r ON e.room_id = r.id
            JOIN professors p ON e.professor_id = p.id
            WHERE f.dept_id = %s AND e.session_id = 1
            ORDER BY e.exam_date, e.start_time, f.name
        """
        schedule = db.execute_query(schedule_query, (dept_id,))
    else:
        schedule_query = """
            SELECT 
                m.name as "Module",
                e.exam_date as "Date",
                e.start_time as "Time",
                r.name as "Room",
                p.full_name as "Professor",
                e.expected_students as "Students"
            FROM exams e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            JOIN exam_rooms r ON e.room_id = r.id
            JOIN professors p ON e.professor_id = p.id
            WHERE f.dept_id = %s AND f.name = %s AND e.session_id = 1
            ORDER BY e.exam_date, e.start_time
        """
        schedule = db.execute_query(schedule_query, (dept_id, selected_formation))

    if schedule:
        schedule_df = pd.DataFrame(schedule)
        schedule_df['Date'] = pd.to_datetime(schedule_df['Date']).dt.strftime('%A, %b %d, %Y')
        
        if view_mode == "By Date":
            st.dataframe(schedule_df, use_container_width=True, hide_index=True)
        else:
            # Group by formation
            if 'Formation' in schedule_df.columns:
                for formation_name in schedule_df['Formation'].unique():
                    with st.expander(f"📚 {formation_name}"):
                        formation_data = schedule_df[schedule_df['Formation'] == formation_name].drop(columns=['Formation'])
                        st.dataframe(formation_data, use_container_width=True, hide_index=True)
            else:
                st.dataframe(schedule_df, use_container_width=True, hide_index=True)
        
        # Export options
        st.divider()
        export_col1, export_col2 = st.columns([3, 1])
        
        with export_col2:
            csv = schedule_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Schedule",
                csv,
                f"{dept_name}_schedule.csv",
                "text/csv",
                use_container_width=True
            )
    else:
        st.warning("No exams scheduled for this department yet.")

    st.divider()

    # --- PROFESSOR WORKLOAD BREAKDOWN ---
    with st.expander("📊 Professor Workload Analysis"):
        prof_workload = db.execute_query("""
            SELECT 
                p.full_name as "Professor",
                COUNT(e.id) as "Total Surveillances",
                COUNT(DISTINCT e.exam_date) as "Active Days",
                string_agg(DISTINCT f.name, ', ') as "Formations Covered"
            FROM exams e
            JOIN professors p ON e.professor_id = p.id
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            WHERE f.dept_id = %s AND e.session_id = 1
            GROUP BY p.id, p.full_name
            ORDER BY COUNT(e.id) DESC
        """, (dept_id,))
        
        if prof_workload:
            st.dataframe(pd.DataFrame(prof_workload), use_container_width=True, hide_index=True)
        else:
            st.info("No professor assignments yet.")

    # --- VALIDATION ACTION ZONE ---
    st.divider()
    st.subheader("Department Validation")
    
    action_col1, action_col2, action_col3 = st.columns([2, 2, 3])
    
    with action_col1:
        if not conflicts:
            if st.button("✅ APPROVE Department Schedule", use_container_width=True, type="primary"):
                st.success(f"{dept_name} schedule approved!")
                st.info("Approval logged. Dean will be notified for final validation.")
        else:
            st.button("✅ APPROVE Department Schedule", use_container_width=True, disabled=True)
            st.caption("Resolve conflicts first")
    
    with action_col2:
        if st.button("📋 Request Modifications", use_container_width=True):
            st.warning("Modification request submitted to Planning Service.")
    
    with action_col3:
        if conflicts:
            st.error(f"⚠️ {len(conflicts)} conflict(s) must be resolved before approval")
        else:
            st.success("✅ Department schedule is ready for approval")


# --- APP CONTROL ---
def main():
    # 1. Check if user is already logged in
    if 'user' not in st.session_state:
        login_page()
        return  # Stop here if not logged in

    # 2. If we reach here, the user is logged in
    user = st.session_state['user']
    
    # Sidebar Setup
    st.sidebar.title("Univ-Alger Portal")
    st.sidebar.markdown(f"**User:** {user['email']}")
    st.sidebar.write(f"**Role:** {user['role'].upper()}")
    
    if st.sidebar.button("Log Out", use_container_width=True):
        # Clear the specific key and rerun
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

    st.sidebar.divider()

    # 3. Routing (Using a dictionary for cleaner code)
    role = user.get('role')
    
    if role == 'admin':
        show_admin_dashboard()
    elif role == 'student':
        show_student_dashboard()
    elif role == 'professor':
        show_professor_dashboard()
    elif role in ['doyen', 'vice_doyen']:
        show_doyen_dashboard()
    elif role == 'chef_dept':
        show_chef_dept_dashboard()
    else:
        st.error("Unknown Role Assigned. Please contact Admin.")

            
if __name__ == "__main__":
    main()