#  University Exam Management System

##  Project Overview
This project is a full-stack database application designed to manage university exam schedules. It handles complex relationships between departments, formations (majors), modules, and students while ensuring academic integrity through conflict detection.

##  Database Statistics
The database is populated with realistic, large-scale data to test performance and scalability:
* **Students:** 13,100 total enrollments.
* **Departments:** 7 distinct departments (Informatique, Physique, Math, etc.).
* **Modules:** ~800+ unique modules across various levels.
* **Levels Covered:** L1, L2, L3, Master 1, and Master 2.

##  Key Database Logic
* **Unique Module Identification:** The system correctly distinguishes between modules with similar names (e.g., "Informatique de Base") by linking them to specific **Formation IDs**. This allows L1 and L3 to have separate exam schedules.
* **Session Management:** All current statistics are filtered by `session_id ` to represent the current active exam period.
* **Conflict Prevention:** The system identifies if a specific Formation has more than one exam scheduled on the same date.

##  Tech Stack
* **Language:** Python 3.x
* **Web Framework:** Streamlit
* **Database:** PostgreSQL (Local/Neon Cloud)
* **Data Library:** Pandas (for analytics and CSV exports)

## Installation & Setup

### 1. Database Restoration
### To view the data, import the provided SQL dump into your PostgreSQL instance:
```bash
psql -U your_username -d your_database_name -f university_local_backup.sql

To recreate the database, please run the attached SQL script. It includes 7 departments and the full enrollment data for 13,100 students. -> DB/university_project.sql
```
### these are some users and passwords to be able to try the website:
   admin@univ.dz   admin123
   doyen@univ.dz doyen123
   lydia.belaid10344@univ-alger.dz  student123
   m.kaci@univ.dz   prof123

   