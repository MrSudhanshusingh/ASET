"""
Seed data script to initialize ASET with faculty, students,
realistic exam questions, and sample completed sessions for the Leaderboard.
"""

from app import create_app
from models import db, User, Exam, Question, ExamSession
from datetime import datetime, timedelta, timezone

def seed_database():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        print("[ASET Seed] Creating faculty and student accounts...")

        # 1. Create Teacher
        teacher = User(
            username='teacher',
            role='teacher',
            full_name='Prof. Rajesh Sharma',
            department='Computer Science & Engineering'
        )
        teacher.set_password('admin123')
        db.session.add(teacher)

        # 2. Create Students
        students_data = [
            ('CS202601', 'Aman Verma', 'student123'),
            ('CS202602', 'Priya Patel', 'student123'),
            ('CS202603', 'Rahul Singh', 'student123'),
            ('CS202604', 'Sneha Sharma', 'student123'),
        ]

        students = []
        for roll, name, pwd in students_data:
            st = User(
                username=roll,
                roll_no=roll,
                role='student',
                full_name=name,
                department='Computer Science & Engineering'
            )
            st.set_password(pwd)
            db.session.add(st)
            students.append(st)

        db.session.commit()

        # 3. Create Sample Exam
        print("[ASET Seed] Creating Sample College Exam: CS-401...")
        exam_key = "SECURE2026"
        exam = Exam(
            title='Computer Networks & Security Final',
            subject_code='CS-401',
            description='End-Semester offline laboratory examination covering OSI model, TCP/IP, Cryptography, and Network Defense.',
            duration_minutes=25,
            total_marks=10.0,
            passing_marks=4.0,
            exam_key=exam_key,
            shuffle_questions=True,
            shuffle_options=True,
            sets_enabled=False,
            show_leaderboard=True,
            release_results=True,
            created_by=teacher.id
        )
        db.session.add(exam)
        db.session.commit()

        # 4. Add 5 Encrypted Questions
        print("[ASET Seed] Encrypting and inserting Question Bank...")
        questions_data = [
            {
                'text': 'Which layer of the OSI model is responsible for end-to-end communication and port addressing?',
                'a': 'Network Layer',
                'b': 'Transport Layer',
                'c': 'Data Link Layer',
                'd': 'Session Layer',
                'correct': 'B',
                'marks': 2.0,
                'explanation': 'The Transport Layer (Layer 4) handles end-to-end communication and process-level addressing using port numbers (e.g., TCP/UDP).'
            },
            {
                'text': 'What type of cryptographic algorithm is AES (Advanced Encryption Standard)?',
                'a': 'Asymmetric Key Cipher',
                'b': 'Hashing Algorithm',
                'c': 'Symmetric Block Cipher',
                'd': 'Stream Cipher',
                'correct': 'C',
                'marks': 2.0,
                'explanation': 'AES is a symmetric key block cipher operating on 128-bit blocks of data with key sizes of 128, 192, or 256 bits.'
            },
            {
                'text': 'In a TCP 3-Way Handshake, which sequence of flags is exchanged to establish a connection?',
                'a': 'SYN -> SYN-ACK -> ACK',
                'b': 'ACK -> SYN -> FIN',
                'c': 'SYN -> ACK -> RST',
                'd': 'PING -> PONG -> ACK',
                'correct': 'A',
                'marks': 2.0,
                'explanation': 'TCP connection setup initiates with a SYN segment from the client, followed by SYN-ACK from the server, and concluded with an ACK from the client.'
            },
            {
                'text': 'Which attack involves an attacker secretly intercepting and relaying messages between two parties who believe they are directly communicating?',
                'a': 'Denial of Service (DoS)',
                'b': 'Man-in-the-Middle (MitM)',
                'c': 'SQL Injection',
                'd': 'Buffer Overflow',
                'correct': 'B',
                'marks': 2.0,
                'explanation': 'In a Man-in-the-Middle (MitM) attack, the adversary intercepts, inspects, and potentially modifies traffic flowing between two legitimate endpoints.'
            },
            {
                'text': 'What is the standard size of an IPv4 address vs an IPv6 address?',
                'a': '16 bits vs 64 bits',
                'b': '32 bits vs 128 bits',
                'c': '64 bits vs 256 bits',
                'd': '128 bits vs 512 bits',
                'correct': 'B',
                'marks': 2.0,
                'explanation': 'An IPv4 address is 32 bits (4 octets) long, whereas an IPv6 address provides 128 bits of address space.'
            },
        ]

        for q_item in questions_data:
            q = Question(
                exam_id=exam.id,
                set_name='ALL',
                marks=q_item['marks'],
                negative_marks=0.0
            )
            q.set_content(
                q_text=q_item['text'],
                opt_a=q_item['a'],
                opt_b=q_item['b'],
                opt_c=q_item['c'],
                opt_d=q_item['d'],
                correct_opt=q_item['correct'],
                explanation=q_item['explanation'],
                passcode=exam_key
            )
            db.session.add(q)

        db.session.commit()

        # 5. Create Sample Submissions for the Leaderboard
        print("[ASET Seed] Simulating previous student submissions for the Leaderboard...")
        
        now = datetime.now(timezone.utc)
        # Student 2: Priya Patel (Rank 1 - 10/10 in 8 mins)
        s2 = students[1]
        session_priya = ExamSession(
            exam_id=exam.id,
            student_id=s2.id,
            assigned_set='A',
            start_time=now - timedelta(minutes=20),
            submit_time=now - timedelta(minutes=12),
            time_taken_seconds=480,
            status='completed',
            warning_count=0,
            total_score=10.0,
            percentage=100.0,
            passed=True
        )
        db.session.add(session_priya)

        # Student 4: Sneha Sharma (Rank 2 - 8/10 in 11 mins)
        s4 = students[3]
        session_sneha = ExamSession(
            exam_id=exam.id,
            student_id=s4.id,
            assigned_set='A',
            start_time=now - timedelta(minutes=25),
            submit_time=now - timedelta(minutes=14),
            time_taken_seconds=660,
            status='completed',
            warning_count=0,
            total_score=8.0,
            percentage=80.0,
            passed=True
        )
        db.session.add(session_sneha)

        # Student 3: Rahul Singh (Rank 3 - 6/10 in 14 mins)
        s3 = students[2]
        session_rahul = ExamSession(
            exam_id=exam.id,
            student_id=s3.id,
            assigned_set='A',
            start_time=now - timedelta(minutes=30),
            submit_time=now - timedelta(minutes=16),
            time_taken_seconds=840,
            status='completed',
            warning_count=1,
            total_score=6.0,
            percentage=60.0,
            passed=True
        )
        db.session.add(session_rahul)

        db.session.commit()

        print("=======================================================")
        print("  [OK] ASET DATABASE INITIALIZATION & SEEDING COMPLETED!")
        print("  Faculty Account: user: 'teacher' | pass: 'admin123'")
        print("  Candidate (Ready to Take Test): roll: 'CS202601' | pass: 'student123'")
        print("  Exam Passcode: 'SECURE2026'")
        print("=======================================================")

if __name__ == '__main__':
    seed_database()
