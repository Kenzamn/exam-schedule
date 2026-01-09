-- 1. CLEANUP
DROP TABLE IF EXISTS exams CASCADE;
DROP TABLE IF EXISTS enrollments CASCADE;
DROP TABLE IF EXISTS modules CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;
DROP TABLE IF EXISTS professors CASCADE;
DROP TABLE IF EXISTS formations CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS exam_rooms CASCADE;
DROP TABLE IF EXISTS exam_sessions CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;

-- 2. ENUMS & SESSIONS
CREATE TYPE user_role AS ENUM ('admin', 'doyen', 'chef_dept', 'professor', 'student');

CREATE TABLE exam_sessions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL, -- e.g., 'Winter 2026'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. CORE STRUCTURE
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE formations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dept_id INTEGER REFERENCES departments(id) ON DELETE CASCADE,
    level VARCHAR(10), 
    nb_modules INTEGER DEFAULT 6
);

CREATE TABLE professors (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    dept_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    specialization VARCHAR(100),
    surveillance_count INTEGER DEFAULT 0 
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    formation_id INTEGER REFERENCES formations(id) ON DELETE CASCADE,
    promo INTEGER NOT NULL
);

CREATE TABLE modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    credits INTEGER DEFAULT 6,
    formation_id INTEGER REFERENCES formations(id) ON DELETE CASCADE,
    exam_duration_minutes INTEGER DEFAULT 90
);

CREATE TABLE exam_rooms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    capacity INTEGER NOT NULL,
    room_type VARCHAR(20) CHECK (room_type IN ('amphi', 'salle')),
    building VARCHAR(50),
    is_accessible BOOLEAN DEFAULT TRUE
);

CREATE TABLE enrollments (
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE,
    registration_date DATE DEFAULT CURRENT_DATE,
    PRIMARY KEY (student_id, module_id)
);

CREATE TABLE exams (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES exam_sessions(id) ON DELETE CASCADE,
    module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE,
    professor_id INTEGER REFERENCES professors(id) ON DELETE SET NULL,
    room_id INTEGER REFERENCES exam_rooms(id) ON DELETE CASCADE,
    exam_date DATE NOT NULL,
    start_time TIME NOT NULL,
    duration_minutes INTEGER NOT NULL,
    expected_students INTEGER,
    status VARCHAR(20) DEFAULT 'scheduled'
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL,
    linked_professor_id INTEGER REFERENCES professors(id) ON DELETE CASCADE,
    linked_student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    linked_dept_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_settings (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT
);

-- 4. PERFORMANCE INDEXES
CREATE INDEX idx_student_formation ON students(formation_id);
CREATE INDEX idx_enrollment_module ON enrollments(module_id);
CREATE INDEX idx_exam_datetime ON exams(exam_date, start_time);
CREATE INDEX idx_user_email ON users(email);