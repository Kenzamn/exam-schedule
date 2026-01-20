import json
from datetime import timedelta, datetime, time
from collections import defaultdict
import psycopg2.extras
from backend.database_manager import DatabaseManager
import random 
from datetime import timedelta, datetime, time
from collections import defaultdict

class SchedulerEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.max_exams_per_day_student = 1
        self.max_exams_per_day_prof = 3
        self.DAY_START = time(8, 30)
        self.DAY_END = time(18, 0)
        self.BUFFER_MINUTES = 10
        self.CAP_AMPHI = 100
        self.CAP_SALLE = 20

    def run_custom(self, name, start, end, progress_callback=None):
        # ✅ CRITICAL FIX: Always reset to PENDING when generating new schedule
        self.db.execute_query("""
            INSERT INTO exam_sessions (id, name, start_date, end_date, is_active)
            VALUES (1, %s, %s, %s, false)
            ON CONFLICT (id) DO UPDATE SET 
                name = EXCLUDED.name, 
                start_date = EXCLUDED.start_date, 
                end_date = EXCLUDED.end_date,
                is_active = false
        """, (name, start, end), fetch=False)
        return self.run(session_id=1, progress_callback=progress_callback)

    def run(self, session_id, progress_callback=None):
        """
        Final Balanced Engine: 
        - Skip FRIDAY ONLY
        - Merges small exams (< 15 students)
        - Maintains tight Professor Workload Gap
        """
        if progress_callback: progress_callback("Initializing Engine...", 10)
        
        # 1. Load Data
        session_data = self.db.execute_query("SELECT * FROM exam_sessions WHERE id=%s", (session_id,))
        if not session_data: return 0
        session = session_data[0]
        
        # ✅ FIX: Ensure rooms is always a list, never None
        rooms = self.db.execute_query("SELECT id, name, capacity FROM exam_rooms ORDER BY capacity DESC") or []
        profs = self.db.execute_query("SELECT id, full_name, dept_id, surveillance_count FROM professors") or []
        
        modules = self.db.execute_query("""
            SELECT m.id, m.name, m.exam_duration_minutes, 
                COUNT(e.student_id) as student_count, m.formation_id, f.name as formation_name
            FROM modules m
            JOIN enrollments e ON m.id = e.module_id
            JOIN formations f ON m.formation_id = f.id
            GROUP BY m.id, m.name, m.exam_duration_minutes, m.formation_id, f.name
            ORDER BY student_count DESC, m.id ASC
        """) or []

        # ✅ ADD: Early validation check
        if not rooms:
            if progress_callback: 
                progress_callback("ERROR: No exam rooms found in database!", 100)
            return 0
        
        if not profs:
            if progress_callback: 
                progress_callback("ERROR: No professors found in database!", 100)
            return 0
        
        if not modules:
            if progress_callback: 
                progress_callback("ERROR: No modules found in database!", 100)
            return 0

        processed_modules = set()
        formation_busy_days = defaultdict(set) 
        prof_daily_count = defaultdict(lambda: defaultdict(int))
        prof_time_occupancy = defaultdict(list)
        room_ready_at = {} 
        room_seats_used = defaultdict(int) 

        # 2. Build Calendar (Skipping Friday ONLY)
        calendar_dates = []
        curr = session['start_date']
        while curr <= session['end_date']:
            if curr.weekday() != 4: # 4 is Friday. 6 (Sunday) is now ALLOWED.
                calendar_dates.append(curr)
            curr += timedelta(days=1)

        # Cleanup
        self.db.execute_query("DELETE FROM student_seating", fetch=False)
        self.db.execute_query("DELETE FROM exams WHERE session_id=%s", (session_id,), fetch=False)
        self.db.execute_query("UPDATE professors SET surveillance_count = 0", fetch=False)

        scheduled_count = 0
        total_mods = len(modules)

        # Helper function to find best available professors to keep workload gap small
        def get_balanced_profs(day, search_time, end_candidate, needed=1):
            avail = [p for p in profs if prof_daily_count[p['id']][day] < 3]
            # Sort by total count first (Global Balance), then daily count (Daily Balance)
            avail.sort(key=lambda x: (x['surveillance_count'], prof_daily_count[x['id']][day]))
            
            selected = []
            for p in avail:
                p_conf = any(not (end_candidate <= ps or search_time >= pe) 
                            for (ps, pe) in prof_time_occupancy[(p['id'], day)])
                if not p_conf:
                    selected.append(p)
                    if len(selected) >= needed: return selected
            return None

        # 5. MAIN SCHEDULING LOOP
        for i, mod in enumerate(modules):
            m_id, m_name = mod['id'], mod['name']
            if m_id in processed_modules: continue 

            m_count, m_duration, f_name = mod['student_count'], mod['exam_duration_minutes'], mod['formation_name'] 
            assigned = False

            for day_idx, day in enumerate(calendar_dates):
                if assigned: break
                if day_idx in formation_busy_days[f_name]: continue

                time_slots = [time(8,30), time(11,0), time(13,30), time(15,30)]
                for t_start in time_slots:
                    if assigned: break
                    
                    search_time = datetime.combine(day, t_start)
                    end_candidate = search_time + timedelta(minutes=m_duration)

                    # --- OPTION A: MERGE INTO EXISTING ROOM ---
                    if m_count < 15:
                        for r in rooms:
                            key = (r['id'], day, t_start)
                            used = room_seats_used.get(key, 0)
                            if used > 0 and (r['capacity'] - used) >= m_count:
                                best_profs = get_balanced_profs(day, search_time, end_candidate, 1)
                                if best_profs:
                                    p = best_profs[0]
                                    self.db.execute_query("""
                                        INSERT INTO exams (session_id, module_id, professor_id, room_id, 
                                                        exam_date, start_time, duration_minutes, expected_students)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (session_id, m_id, p['id'], r['id'], day, t_start, m_duration, m_count), fetch=False)
                                    
                                    p['surveillance_count'] += 1
                                    prof_daily_count[p['id']][day] += 1
                                    prof_time_occupancy[(p['id'], day)].append((search_time, end_candidate))
                                    room_seats_used[key] += m_count
                                    formation_busy_days[f_name].add(day_idx)
                                    processed_modules.add(m_id)
                                    assigned = True; scheduled_count += 1
                                    break
                        if assigned: break

                    # --- OPTION B: STANDARD NEW ROOM ALLOCATION ---
                    usable_rooms = []; cap_sum = 0
                    for r in rooms:
                        ready = room_ready_at.get((r['id'], day), datetime.combine(day, time(8,0)))
                        if ready <= search_time:
                            usable_rooms.append(r); cap_sum += r['capacity']
                            if cap_sum >= m_count: break 

                    if cap_sum >= m_count:
                        best_profs = get_balanced_profs(day, search_time, end_candidate, len(usable_rooms))
                        if best_profs:
                            rem = m_count
                            for idx, room in enumerate(usable_rooms):
                                p = best_profs[idx]
                                num = min(room['capacity'], rem)
                                self.db.execute_query("""
                                    INSERT INTO exams (session_id, module_id, professor_id, room_id, 
                                                    exam_date, start_time, duration_minutes, expected_students)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, (session_id, m_id, p['id'], room['id'], day, t_start, m_duration, num), fetch=False)
                                
                                p['surveillance_count'] += 1
                                prof_daily_count[p['id']][day] += 1
                                prof_time_occupancy[(p['id'], day)].append((search_time, end_candidate))
                                room_ready_at[(room['id'], day)] = end_candidate + timedelta(minutes=15)
                                room_seats_used[(room['id'], day, t_start)] += num
                                rem -= num
                                if rem <= 0: break
                            
                            formation_busy_days[f_name].add(day_idx) 
                            processed_modules.add(m_id)
                            assigned = True; scheduled_count += 1

            if progress_callback:
                progress_callback(f"Scheduling {m_name}...", int((i/total_mods)*100))
        
        if progress_callback:
            progress_callback("✅ Schedule generation complete!", 100)
        
        return scheduled_count
    
    def get_dean_dashboard(self, session_id=1):
        """
        Fetches high-level analytics for the Dean's dashboard.
        """
        try:
            summary = self.db.execute_query("""
                SELECT 
                    COUNT(DISTINCT e.professor_id) as active_profs,
                    COUNT(DISTINCT e.module_id) as total_unique_exams,
                    COUNT(e.id) as total_sessions,
                    COUNT(DISTINCT e.exam_date) as total_days
                FROM exams e
                WHERE e.session_id = %s
            """, (session_id,))

            return {
                "summary": summary[0] if summary else {
                    "active_profs": 0,
                    "total_unique_exams": 0,
                    "total_sessions": 0,
                    "total_days": 0
                }
            }
        except Exception as e:
            print(f"Error fetching Dean stats: {e}")
            return {"summary": {}}
    
    def get_dept_dashboard_optimized(self, dept_id, session_id=1):
        """
        OPTIMIZED: Single query for department dashboard
        Gets all metrics, conflicts, and stats in one round trip
        """
        try:
            d_id = int(dept_id)
            
            result = self.db.execute_query("""
                WITH dept_metrics AS (
                    SELECT 
                        COUNT(DISTINCT f.id) as total_formations,
                        COUNT(DISTINCT m.id) as total_modules,
                        COUNT(DISTINCT e.id) as scheduled_sessions,
                        COUNT(DISTINCT e.professor_id) as active_profs,
                        COUNT(DISTINCT s.id) as total_students,
                        COUNT(DISTINCT e.exam_date) as active_days
                    FROM formations f
                    LEFT JOIN modules m ON f.id = m.formation_id
                    LEFT JOIN exams e ON m.id = e.module_id AND e.session_id = %s
                    LEFT JOIN enrollments en ON m.id = en.module_id
                    LEFT JOIN students s ON en.student_id = s.id
                    WHERE f.dept_id = %s
                ),
                dept_conflicts AS (
                    SELECT 
                        json_agg(
                            json_build_object(
                                'formation', f.name,
                                'exam_date', e.exam_date,
                                'daily_count', cnt,
                                'modules', modules
                            )
                        ) as conflicts
                    FROM (
                        SELECT 
                            f.name, 
                            e.exam_date, 
                            COUNT(DISTINCT e.module_id) as cnt,
                            string_agg(m.name, ', ') as modules
                        FROM exams e
                        JOIN modules m ON e.module_id = m.id
                        JOIN formations f ON m.formation_id = f.id
                        WHERE f.dept_id = %s AND e.session_id = %s
                        GROUP BY f.name, e.exam_date
                        HAVING COUNT(DISTINCT e.module_id) > 1
                    ) sub
                ),
                workload_gap AS (
                    SELECT 
                        COALESCE(MAX(cnt) - MIN(cnt), 0) as gap
                    FROM (
                        SELECT professor_id, COUNT(id) as cnt
                        FROM exams e
                        JOIN modules m ON e.module_id = m.id
                        JOIN formations f ON m.formation_id = f.id
                        WHERE f.dept_id = %s AND e.session_id = %s
                        GROUP BY professor_id
                    ) sub
                )
                SELECT 
                    dm.*,
                    COALESCE(dc.conflicts, '[]'::json) as conflicts,
                    wg.gap as workload_gap
                FROM dept_metrics dm
                CROSS JOIN dept_conflicts dc
                CROSS JOIN workload_gap wg
            """, (session_id, d_id, d_id, session_id, d_id, session_id))
            
            if result:
                import json
                row = result[0]
                return {
                    "metrics": {
                        "total_formations": row['total_formations'],
                        "total_modules": row['total_modules'],
                        "scheduled_sessions": row['scheduled_sessions'],
                        "active_profs": row['active_profs'],
                        "total_students": row['total_students'],
                        "active_days": row['active_days']
                    },
                    "conflicts": json.loads(row['conflicts']) if row['conflicts'] else [],
                    "workload_gap": row['workload_gap']
                }
            return {
                "metrics": {
                    "total_formations": 0,
                    "total_modules": 0,
                    "scheduled_sessions": 0,
                    "active_profs": 0,
                    "total_students": 0,
                    "active_days": 0
                },
                "conflicts": [],
                "workload_gap": 0
            }
            
        except Exception as e:
            print(f"Engine Error: {e}")
            return None