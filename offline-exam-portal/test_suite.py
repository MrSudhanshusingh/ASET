import unittest
import os
import json
import base64
import numpy as np
import cv2

TEST_DB_PATH = os.path.abspath("test_exam.db")
os.environ['DATABASE_URL'] = f"sqlite:///{TEST_DB_PATH}"

from app import create_app
from models import db, User, Exam, Question, ExamSession, StudentAnswer
from security.crypto import encrypt_text, decrypt_text
from security.proctor import detect_faces

class ASETExamPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    def setUp(self):
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

        # Teacher
        teacher = User(username='test_teacher', role='teacher', full_name='Prof. Test')
        teacher.set_password('admin123')
        db.session.add(teacher)

        # Student
        student = User(username='CS999901', roll_no='CS999901', role='student', full_name='Test Student')
        student.set_password('student123')
        db.session.add(student)

        # Exam
        exam = Exam(
            title='Test Networks Exam',
            subject_code='CS-101',
            duration_minutes=20,
            total_marks=4.0,
            passing_marks=2.0,
            exam_key='TESTPASS',
            created_by=1
        )
        db.session.add(exam)
        db.session.commit()

        # Questions
        q1 = Question(exam_id=exam.id, set_name='ALL', marks=2.0, negative_marks=0.0)
        q1.set_content(
            q_text='What is 2+2?',
            opt_a='1', opt_b='2', opt_c='4', opt_d='5',
            correct_opt='C',
            explanation='2+2 equals 4.',
            passcode='TESTPASS'
        )
        q2 = Question(exam_id=exam.id, set_name='ALL', marks=2.0, negative_marks=0.0)
        q2.set_content(
            q_text='Which protocol is connection-oriented?',
            opt_a='TCP', opt_b='UDP', opt_c='IP', opt_d='ICMP',
            correct_opt='A',
            explanation='TCP establishes a virtual circuit.',
            passcode='TESTPASS'
        )
        db.session.add(q1)
        db.session.add(q2)
        db.session.commit()

        self.teacher_id = teacher.id
        self.student_id = student.id
        self.exam_id = exam.id
        self.q1_id = q1.id
        self.q2_id = q2.id

    def tearDown(self):
        db.session.remove()

    def test_01_encryption_decryption(self):
        secret = "Confidential Exam Question"
        passcode = "MYSECRET2026"
        encrypted = encrypt_text(secret, passcode)
        self.assertNotEqual(secret, encrypted)
        decrypted = decrypt_text(encrypted, passcode)
        self.assertEqual(secret, decrypted)

        wrong_attempt = decrypt_text(encrypted, "WRONGPASS")
        self.assertNotEqual(wrong_attempt, secret)

    def test_02_face_detection_synthetic(self):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.ellipse(img, (320, 240), (90, 130), 0, 0, 360, (140, 175, 225), -1)
        count, rects = detect_faces(img)
        self.assertGreaterEqual(count, 1)

    def test_03_login_and_session(self):
        res = self.client.post('/login', data={
            'username': 'CS999901',
            'password': 'student123',
            'role': 'student'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Test Student', res.data)

    def test_04_save_answer_and_grading(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_id
            sess['role'] = 'student'
            sess['roll_no'] = 'CS999901'
            sess['full_name'] = 'Test Student'

        session_rec = ExamSession(exam_id=self.exam_id, student_id=self.student_id, assigned_set='A')
        db.session.add(session_rec)
        db.session.commit()
        sess_id = session_rec.id

        res1 = self.client.post('/api/save-answer', json={
            'session_id': sess_id,
            'question_id': self.q1_id,
            'selected_option': 'C',
            'marked_for_review': False
        })
        self.assertTrue(res1.get_json()['success'])

        res2 = self.client.post('/api/save-answer', json={
            'session_id': sess_id,
            'question_id': self.q2_id,
            'selected_option': 'B',
            'marked_for_review': False
        })
        self.assertTrue(res2.get_json()['success'])

        sub_res = self.client.post(f'/student/exam/{sess_id}/submit', follow_redirects=True)
        self.assertEqual(sub_res.status_code, 200)

        rec = ExamSession.query.get(sess_id)
        self.assertEqual(rec.total_score, 2.0)
        self.assertEqual(rec.percentage, 50.0)
        self.assertTrue(rec.passed)
        self.assertEqual(rec.status, 'completed')

    def test_05_anti_cheat_violation_strike_logging(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_id
            sess['role'] = 'student'

        s = ExamSession(exam_id=self.exam_id, student_id=self.student_id)
        db.session.add(s)
        db.session.commit()
        s_id = s.id

        res1 = self.client.post('/api/log-violation', json={
            'session_id': s_id,
            'type': 'Tab Switch',
            'details': 'User left exam window'
        }).get_json()
        self.assertEqual(res1['strikes'], 1)
        self.assertFalse(res1['auto_submit'])

        res2 = self.client.post('/api/log-violation', json={
            'session_id': s_id,
            'type': 'Window Blur',
            'details': 'Focus lost'
        }).get_json()
        self.assertEqual(res2['strikes'], 2)
        self.assertFalse(res2['auto_submit'])

        res3 = self.client.post('/api/log-violation', json={
            'session_id': s_id,
            'type': 'DevTools Open',
            'details': 'Inspect shortcut pressed'
        }).get_json()
        self.assertEqual(res3['strikes'], 3)
        self.assertTrue(res3['auto_submit'])

    def test_06_leaderboard_view(self):
        res = self.client.get('/leaderboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'ASET College Leaderboard', res.data)

    def test_07_student_self_registration(self):
        res = self.client.post('/register', data={
            'full_name': 'New Candidate',
            'roll_no': 'CS202688',
            'department': 'Computer Science & Engineering',
            'password': 'mypassword',
            'confirm_password': 'mypassword',
            'face_photo_data': ''
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome to the examination portal', res.data)

        u = User.query.filter_by(username='CS202688').first()
        self.assertIsNotNone(u)
        self.assertEqual(u.full_name, 'New Candidate')
        self.assertTrue(u.check_password('mypassword'))

        res_dup = self.client.post('/register', data={
            'full_name': 'New Candidate Duplicate',
            'roll_no': 'CS202688',
            'department': 'Computer Science & Engineering',
            'password': 'mypassword',
            'confirm_password': 'mypassword'
        }, follow_redirects=True)
        self.assertIn(b'already registered', res_dup.data)

if __name__ == '__main__':
    unittest.main()
