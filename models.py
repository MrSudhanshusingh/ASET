import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from security.crypto import encrypt_text, decrypt_text

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False) # Roll No for students, username for teachers
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # 'teacher' or 'student'
    full_name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(50), nullable=True) # Unique identifier for student
    department = db.Column(db.String(100), default='Computer Science & Engineering')
    profile_photo = db.Column(db.String(255), nullable=True) # Reference photo path
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Exam(db.Model):
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    subject_code = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, default="")
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    total_marks = db.Column(db.Float, nullable=False, default=20.0)
    passing_marks = db.Column(db.Float, nullable=False, default=8.0)
    
    # Security & Leak Prevention settings
    exam_key = db.Column(db.String(50), nullable=False) # Session secret passcode required to unlock paper
    shuffle_questions = db.Column(db.Boolean, default=True) # Random question sequence per student
    shuffle_options = db.Column(db.Boolean, default=True) # Random A, B, C, D sequence per student
    sets_enabled = db.Column(db.Boolean, default=False)
    available_sets = db.Column(db.String(50), default="A,B")
    
    # State & Visibility
    is_active = db.Column(db.Boolean, default=True)
    show_leaderboard = db.Column(db.Boolean, default=True)
    release_results = db.Column(db.Boolean, default=True) # Instantly reveal marks/analysis post-exam
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    questions = db.relationship('Question', backref='exam', cascade='all, delete-orphan', lazy=True)
    sessions = db.relationship('ExamSession', backref='exam', cascade='all, delete-orphan', lazy=True)
    attendances = db.relationship('Attendance', backref='exam', cascade='all, delete-orphan', lazy=True)

class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    set_name = db.Column(db.String(10), default='ALL') # 'ALL', 'A', 'B', etc.
    
    # Encrypted fields stored at rest
    question_text_enc = db.Column(db.Text, nullable=False)
    option_a_enc = db.Column(db.Text, nullable=False)
    option_b_enc = db.Column(db.Text, nullable=False)
    option_c_enc = db.Column(db.Text, nullable=False)
    option_d_enc = db.Column(db.Text, nullable=False)
    correct_option_enc = db.Column(db.String(255), nullable=False)
    explanation_enc = db.Column(db.Text, default="")
    
    marks = db.Column(db.Float, default=1.0)
    negative_marks = db.Column(db.Float, default=0.0)

    def set_content(self, q_text, opt_a, opt_b, opt_c, opt_d, correct_opt, explanation="", passcode=None):
        """Encrypt all sensitive question data before saving to DB."""
        self.question_text_enc = encrypt_text(q_text, passcode)
        self.option_a_enc = encrypt_text(opt_a, passcode)
        self.option_b_enc = encrypt_text(opt_b, passcode)
        self.option_c_enc = encrypt_text(opt_c, passcode)
        self.option_d_enc = encrypt_text(opt_d, passcode)
        self.correct_option_enc = encrypt_text(correct_opt.strip().upper(), passcode)
        self.explanation_enc = encrypt_text(explanation, passcode)

    def get_decrypted(self, passcode=None):
        """Decrypt question data in memory."""
        return {
            'id': self.id,
            'exam_id': self.exam_id,
            'set_name': self.set_name,
            'question_text': decrypt_text(self.question_text_enc, passcode),
            'option_a': decrypt_text(self.option_a_enc, passcode),
            'option_b': decrypt_text(self.option_b_enc, passcode),
            'option_c': decrypt_text(self.option_c_enc, passcode),
            'option_d': decrypt_text(self.option_d_enc, passcode),
            'correct_option': decrypt_text(self.correct_option_enc, passcode),
            'explanation': decrypt_text(self.explanation_enc, passcode),
            'marks': self.marks,
            'negative_marks': self.negative_marks
        }

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    verified_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    photo_path = db.Column(db.String(255), nullable=True)
    confidence_score = db.Column(db.Float, default=100.0)
    status = db.Column(db.String(30), default='verified') # 'verified', 'flagged', 'manual_approved'

    student = db.relationship('User', backref='attendances')

class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_set = db.Column(db.String(10), default='A')
    
    start_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    submit_time = db.Column(db.DateTime, nullable=True)
    time_taken_seconds = db.Column(db.Integer, default=0)
    
    # Status: 'in_progress', 'completed', 'disqualified'
    status = db.Column(db.String(30), default='in_progress')
    
    # Anti-cheating logs
    warning_count = db.Column(db.Integer, default=0)
    violations_json = db.Column(db.Text, default="[]")
    
    # Grading results
    total_score = db.Column(db.Float, default=0.0)
    percentage = db.Column(db.Float, default=0.0)
    passed = db.Column(db.Boolean, default=False)
    
    student = db.relationship('User', backref='exam_sessions')
    answers = db.relationship('StudentAnswer', backref='session', cascade='all, delete-orphan', lazy=True)

    def log_violation(self, violation_type, details=""):
        """Append an anti-cheat strike to the session log."""
        try:
            logs = json.loads(self.violations_json or "[]")
        except Exception:
            logs = []
        logs.append({
            'timestamp': datetime.now(timezone.utc).strftime("%H:%M:%S"),
            'type': violation_type,
            'details': details
        })
        self.violations_json = json.dumps(logs)
        self.warning_count = len(logs)

    def get_violations(self):
        try:
            return json.loads(self.violations_json or "[]")
        except Exception:
            return []

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_option = db.Column(db.String(10), nullable=True) # 'A', 'B', 'C', 'D' or None
    is_correct = db.Column(db.Boolean, default=False)
    marks_awarded = db.Column(db.Float, default=0.0)
    marked_for_review = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    question = db.relationship('Question')
