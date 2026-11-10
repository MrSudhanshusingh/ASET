import os
import json
import csv
import io
import random
from datetime import datetime, timezone
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response
)
from config import Config
from models import db, User, Exam, Question, Attendance, ExamSession, StudentAnswer
from security.crypto import encrypt_text, decrypt_text
from security.proctor import detect_faces, save_image_from_base64, compare_faces

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    # Ensure required directories exist
    os.makedirs(Config.FACE_UPLOADS, exist_ok=True)
    os.makedirs(Config.AUDIT_UPLOADS, exist_ok=True)

    with app.app_context():
        db.create_all()

    # -------------------------------------------------------------------------
    # Authentication Decorators
    # -------------------------------------------------------------------------
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    def role_required(role_name):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session or session.get('role') != role_name:
                    flash(f"Access restricted to {role_name}s.", "danger")
                    return redirect(url_for('login'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    # -------------------------------------------------------------------------
    # Public & Auth Routes
    # -------------------------------------------------------------------------
    @app.route('/')
    def index():
        if 'user_id' in session:
            if session.get('role') == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            role = request.form.get('role', 'student').strip()

            user = User.query.filter_by(username=username, role=role).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['full_name'] = user.full_name
                session['role'] = user.role
                session['roll_no'] = user.roll_no or user.username
                flash(f"Welcome back, {user.full_name}!", "success")
                if user.role == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                return redirect(url_for('student_dashboard'))
            else:
                flash("Invalid credentials. Please check your username/roll number and password.", "danger")

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash("You have been signed out safely.", "info")
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    def student_register():
        if request.method == 'POST':
            full_name = request.form.get('full_name', '').strip()
            roll_no = request.form.get('roll_no', '').strip().upper()
            department = request.form.get('department', 'Computer Science & Engineering')
            password = request.form.get('password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            face_photo_data = request.form.get('face_photo_data', '')

            if not full_name or not roll_no or not password:
                flash("All required fields must be filled.", "warning")
                return redirect(url_for('student_register'))

            if password != confirm_pwd:
                flash("Passwords do not match! Please check again.", "danger")
                return redirect(url_for('student_register'))

            # Check if roll number already exists
            existing_user = User.query.filter_by(username=roll_no).first()
            if existing_user:
                flash(f"Roll Number '{roll_no}' is already registered! Please sign in with your password.", "warning")
                return redirect(url_for('login'))

            photo_filename = None
            if face_photo_data and len(face_photo_data) > 500:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                photo_filename = f"profile_{roll_no}_{timestamp}.jpg"
                dest_path = os.path.join(Config.FACE_UPLOADS, photo_filename)
                saved = save_image_from_base64(face_photo_data, dest_path)
                if not saved:
                    photo_filename = None

            new_student = User(
                username=roll_no,
                roll_no=roll_no,
                role='student',
                full_name=full_name,
                department=department,
                profile_photo=photo_filename
            )
            new_student.set_password(password)

            db.session.add(new_student)
            db.session.commit()

            session['user_id'] = new_student.id
            session['username'] = new_student.username
            session['full_name'] = new_student.full_name
            session['role'] = new_student.role
            session['roll_no'] = new_student.roll_no

            flash(f"Registration successful! Welcome to the examination portal, {full_name}.", "success")
            return redirect(url_for('student_dashboard'))

        return render_template('register.html')

    # -------------------------------------------------------------------------
    # College Leaderboard (Accessible to all)
    # -------------------------------------------------------------------------
    @app.route('/leaderboard')
    def leaderboard_view():
        exams = Exam.query.filter_by(is_active=True).all()
        selected_exam_id = request.args.get('exam_id', type=int)

        current_exam = None
        if selected_exam_id:
            current_exam = Exam.query.get(selected_exam_id)
        elif exams:
            current_exam = exams[0]

        leaderboard_data = []
        if current_exam:
            sessions = ExamSession.query.filter_by(
                exam_id=current_exam.id,
                status='completed'
            ).order_by(
                ExamSession.total_score.desc(),
                ExamSession.time_taken_seconds.asc()
            ).all()

            for rank, s in enumerate(sessions, 1):
                mins = s.time_taken_seconds // 60
                secs = s.time_taken_seconds % 60
                leaderboard_data.append({
                    'rank': rank,
                    'student_name': s.student.full_name,
                    'roll_no': s.student.roll_no or s.student.username,
                    'score': s.total_score,
                    'percentage': s.percentage,
                    'passed': s.passed,
                    'time_taken_str': f"{mins}m {secs}s",
                    'warning_count': s.warning_count
                })

        return render_template(
            'leaderboard.html',
            exams=exams,
            current_exam=current_exam,
            leaderboard_data=leaderboard_data
        )

    # -------------------------------------------------------------------------
    # Teacher Dashboard & Management Routes
    # -------------------------------------------------------------------------
    @app.route('/teacher/dashboard')
    @login_required
    @role_required('teacher')
    def teacher_dashboard():
        exams = Exam.query.order_by(Exam.created_at.desc()).all()
        active_exams_count = sum(1 for e in exams if e.is_active)
        total_submissions = ExamSession.query.filter_by(status='completed').count()

        return render_template(
            'teacher/dashboard.html',
            exams=exams,
            active_exams_count=active_exams_count,
            total_submissions=total_submissions
        )

    @app.route('/teacher/students')
    @login_required
    @role_required('teacher')
    def teacher_students():
        students = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
        return render_template('teacher/students.html', students=students)

    @app.route('/teacher/exam/create', methods=['GET', 'POST'])
    @login_required
    @role_required('teacher')
    def teacher_create_exam():
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            subject_code = request.form.get('subject_code', '').strip().upper()
            description = request.form.get('description', '').strip()
            duration_minutes = int(request.form.get('duration_minutes', 30))
            total_marks = float(request.form.get('total_marks', 20.0))
            passing_marks = float(request.form.get('passing_marks', 8.0))
            exam_key = request.form.get('exam_key', '').strip().upper()

            shuffle_q = bool(request.form.get('shuffle_questions'))
            shuffle_opt = bool(request.form.get('shuffle_options'))
            sets_en = bool(request.form.get('sets_enabled'))
            show_lb = bool(request.form.get('show_leaderboard'))
            rel_res = bool(request.form.get('release_results'))

            exam = Exam(
                title=title,
                subject_code=subject_code,
                description=description,
                duration_minutes=duration_minutes,
                total_marks=total_marks,
                passing_marks=passing_marks,
                exam_key=exam_key,
                shuffle_questions=shuffle_q,
                shuffle_options=shuffle_opt,
                sets_enabled=sets_en,
                show_leaderboard=show_lb,
                release_results=rel_res,
                created_by=session['user_id']
            )
            db.session.add(exam)
            db.session.commit()

            flash(f"Exam '{title}' created successfully! Now add questions to the question bank.", "success")
            return redirect(url_for('teacher_manage_questions', exam_id=exam.id))

        default_key = f"EXAM{random.randint(100, 999)}"
        return render_template('teacher/exam_create.html', default_key=default_key)

    @app.route('/teacher/exam/<int:exam_id>/toggle')
    @login_required
    @role_required('teacher')
    def teacher_toggle_exam(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        exam.is_active = not exam.is_active
        db.session.commit()
        status_str = "activated" if exam.is_active else "paused"
        flash(f"Exam '{exam.title}' has been {status_str}.", "info")
        return redirect(url_for('teacher_dashboard'))

    @app.route('/teacher/exam/<int:exam_id>/questions')
    @login_required
    @role_required('teacher')
    def teacher_manage_questions(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        decrypted_questions = [q.get_decrypted(exam.exam_key) for q in exam.questions]
        total_configured = sum(q['marks'] for q in decrypted_questions)

        return render_template(
            'teacher/questions.html',
            exam=exam,
            questions=decrypted_questions,
            total_marks_configured=total_configured
        )

    @app.route('/teacher/exam/<int:exam_id>/question/add', methods=['POST'])
    @login_required
    @role_required('teacher')
    def teacher_add_question(exam_id):
        exam = Exam.query.get_or_404(exam_id)

        q_text = request.form.get('question_text', '').strip()
        opt_a = request.form.get('option_a', '').strip()
        opt_b = request.form.get('option_b', '').strip()
        opt_c = request.form.get('option_c', '').strip()
        opt_d = request.form.get('option_d', '').strip()
        correct_opt = request.form.get('correct_option', 'A').strip().upper()
        marks = float(request.form.get('marks', 1.0))
        negative_marks = float(request.form.get('negative_marks', 0.0))
        set_name = request.form.get('set_name', 'ALL').strip().upper()
        explanation = request.form.get('explanation', '').strip()

        question = Question(
            exam_id=exam.id,
            set_name=set_name,
            marks=marks,
            negative_marks=negative_marks
        )
        question.set_content(
            q_text=q_text,
            opt_a=opt_a,
            opt_b=opt_b,
            opt_c=opt_c,
            opt_d=opt_d,
            correct_opt=correct_opt,
            explanation=explanation,
            passcode=exam.exam_key
        )
        db.session.add(question)
        db.session.commit()

        flash("Encrypted MCQ added to exam paper successfully.", "success")
        return redirect(url_for('teacher_manage_questions', exam_id=exam.id))

    @app.route('/teacher/question/<int:q_id>/delete')
    @login_required
    @role_required('teacher')
    def teacher_delete_question(q_id):
        question = Question.query.get_or_404(q_id)
        exam_id = question.exam_id
        db.session.delete(question)
        db.session.commit()
        flash("Question removed from paper.", "info")
        return redirect(url_for('teacher_manage_questions', exam_id=exam_id))

    @app.route('/teacher/monitor')
    @login_required
    @role_required('teacher')
    def teacher_monitor():
        sessions = ExamSession.query.order_by(ExamSession.start_time.desc()).all()
        for s in sessions:
            att = Attendance.query.filter_by(exam_id=s.exam_id, student_id=s.student_id).first()
            s.attendance = att

        return render_template('teacher/monitor.html', sessions=sessions)

    @app.route('/teacher/exam/<int:exam_id>/results')
    @login_required
    @role_required('teacher')
    def teacher_results(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        sessions = ExamSession.query.filter_by(exam_id=exam.id, status='completed').all()

        pass_count = sum(1 for s in sessions if s.passed)
        avg_score = round(sum(s.total_score for s in sessions) / len(sessions), 1) if sessions else 0.0
        avg_pct = round(sum(s.percentage for s in sessions) / len(sessions), 1) if sessions else 0.0
        pass_pct = round((pass_count / len(sessions)) * 100, 1) if sessions else 0.0
        highest_score = max((s.total_score for s in sessions), default=0.0)

        return render_template(
            'teacher/results.html',
            exam=exam,
            sessions=sessions,
            pass_count=pass_count,
            avg_score=avg_score,
            avg_pct=avg_pct,
            pass_percentage=pass_pct,
            highest_score=highest_score
        )

    @app.route('/teacher/exam/<int:exam_id>/export-csv')
    @login_required
    @role_required('teacher')
    def teacher_export_csv(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        sessions = ExamSession.query.filter_by(exam_id=exam.id, status='completed').all()

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Roll Number', 'Student Name', 'Department', 'Set', 'Score', 'Total Marks', 'Percentage', 'Result', 'Time Taken (s)', 'Cheat Strikes'])

        for s in sessions:
            cw.writerow([
                s.student.roll_no or s.student.username,
                s.student.full_name,
                s.student.department,
                s.assigned_set,
                s.total_score,
                exam.total_marks,
                s.percentage,
                'PASS' if s.passed else 'FAIL',
                s.time_taken_seconds,
                s.warning_count
            ])

        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={exam.subject_code}_Results.csv"}
        )

    # -------------------------------------------------------------------------
    # Student Routes
    # -------------------------------------------------------------------------
    @app.route('/student/dashboard')
    @login_required
    @role_required('student')
    def student_dashboard():
        student = User.query.get(session['user_id'])
        exams = Exam.query.filter_by(is_active=True).all()

        existing_sessions = ExamSession.query.filter_by(student_id=student.id).all()
        student_sessions = {s.exam_id: s for s in existing_sessions}

        return render_template(
            'student/dashboard.html',
            user=student,
            exams=exams,
            student_sessions=student_sessions
        )

    @app.route('/student/exam/<int:exam_id>/verify')
    @login_required
    @role_required('student')
    def student_verify(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        student = User.query.get(session['user_id'])

        session_rec = ExamSession.query.filter_by(exam_id=exam.id, student_id=student.id).first()
        if session_rec and session_rec.status == 'completed':
            flash("You have already submitted this exam.", "info")
            return redirect(url_for('student_result_analysis', session_id=session_rec.id))

        return render_template('student/verify.html', exam=exam, student=student)

    @app.route('/student/exam/<int:exam_id>/start', methods=['POST'])
    @login_required
    @role_required('student')
    def student_start_exam(exam_id):
        exam = Exam.query.get_or_404(exam_id)
        student_id = session['user_id']
        entered_key = request.form.get('exam_key', '').strip().upper()
        face_verified = request.form.get('face_verified', '0')

        if entered_key != exam.exam_key:
            flash("Incorrect Exam Passcode! Please enter the exact key provided by your invigilator.", "danger")
            return redirect(url_for('student_verify', exam_id=exam.id))

        if face_verified != "1":
            flash("Facial verification is required before starting the exam.", "danger")
            return redirect(url_for('student_verify', exam_id=exam.id))

        session_rec = ExamSession.query.filter_by(exam_id=exam.id, student_id=student_id).first()
        if not session_rec:
            assigned_set = 'A' if not exam.sets_enabled else ('A' if student_id % 2 == 1 else 'B')
            session_rec = ExamSession(
                exam_id=exam.id,
                student_id=student_id,
                assigned_set=assigned_set,
                start_time=datetime.now(timezone.utc),
                status='in_progress'
            )
            db.session.add(session_rec)
            db.session.commit()

        return redirect(url_for('student_exam_room', session_id=session_rec.id))

    @app.route('/student/exam/<int:session_id>/room')
    @login_required
    @role_required('student')
    def student_exam_room(session_id):
        session_rec = ExamSession.query.get_or_404(session_id)
        if session_rec.student_id != session['user_id']:
            flash("Unauthorized access to exam session.", "danger")
            return redirect(url_for('student_dashboard'))

        if session_rec.status == 'completed':
            return redirect(url_for('student_result_analysis', session_id=session_rec.id))

        exam = session_rec.exam
        student = session_rec.student

        raw_questions = [
            q for q in exam.questions
            if q.set_name in ['ALL', session_rec.assigned_set]
        ]

        rng = random.Random(session_rec.id * 1000 + student.id)
        if exam.shuffle_questions:
            rng.shuffle(raw_questions)

        prepared_questions = []
        for q in raw_questions:
            d = q.get_decrypted(exam.exam_key)
            options = [
                {'key': 'A', 'text': d['option_a']},
                {'key': 'B', 'text': d['option_b']},
                {'key': 'C', 'text': d['option_c']},
                {'key': 'D', 'text': d['option_d']}
            ]
            if exam.shuffle_options:
                rng.shuffle(options)
            prepared_questions.append({
                'id': d['id'],
                'question_text': d['question_text'],
                'options': options,
                'marks': d['marks'],
                'negative_marks': d['negative_marks']
            })

        elapsed_seconds = int((datetime.now(timezone.utc) - session_rec.start_time.replace(tzinfo=timezone.utc)).total_seconds())
        total_allowed_seconds = exam.duration_minutes * 60
        remaining_seconds = max(0, total_allowed_seconds - elapsed_seconds)

        saved_answers_records = StudentAnswer.query.filter_by(session_id=session_rec.id).all()
        existing_answers_map = {
            a.question_id: {'option': a.selected_option, 'review': a.marked_for_review}
            for a in saved_answers_records
        }

        client_ip = request.remote_addr or "127.0.0.1"

        return render_template(
            'student/exam.html',
            exam=exam,
            student=student,
            session_record=session_rec,
            questions=prepared_questions,
            questions_json=json.dumps(prepared_questions),
            existing_answers_json=json.dumps(existing_answers_map),
            remaining_seconds=remaining_seconds,
            client_ip=client_ip
        )

    @app.route('/student/exam/<int:session_id>/submit', methods=['POST'])
    @login_required
    @role_required('student')
    def student_submit_exam(session_id):
        session_rec = ExamSession.query.get_or_404(session_id)
        if session_rec.student_id != session['user_id']:
            flash("Unauthorized.", "danger")
            return redirect(url_for('student_dashboard'))

        exam = session_rec.exam

        payload_str = request.form.get('final_payload', '')
        if payload_str:
            try:
                final_answers = json.loads(payload_str)
                for q_id_str, ans_data in final_answers.items():
                    q_id = int(q_id_str)
                    sel_opt = ans_data.get('option')
                    is_rev = bool(ans_data.get('review', False))
                    rec = StudentAnswer.query.filter_by(session_id=session_rec.id, question_id=q_id).first()
                    if not rec:
                        rec = StudentAnswer(session_id=session_rec.id, question_id=q_id)
                        db.session.add(rec)
                    rec.selected_option = sel_opt
                    rec.marked_for_review = is_rev
                db.session.commit()
            except Exception as e:
                print(f"[ASET Submit Error] Payload parse: {e}")

        # Automated Grading
        answers = StudentAnswer.query.filter_by(session_id=session_rec.id).all()
        answers_by_qid = {a.question_id: a for a in answers}

        total_score = 0.0
        relevant_questions = [
            q for q in exam.questions
            if q.set_name in ['ALL', session_rec.assigned_set]
        ]

        for q in relevant_questions:
            d = q.get_decrypted(exam.exam_key)
            correct_choice = d['correct_option']
            ans_rec = answers_by_qid.get(q.id)

            if ans_rec and ans_rec.selected_option:
                if ans_rec.selected_option.strip().upper() == correct_choice.strip().upper():
                    ans_rec.is_correct = True
                    ans_rec.marks_awarded = d['marks']
                    total_score += d['marks']
                else:
                    ans_rec.is_correct = False
                    ans_rec.marks_awarded = -d['negative_marks']
                    total_score -= d['negative_marks']
            elif ans_rec:
                ans_rec.is_correct = False
                ans_rec.marks_awarded = 0.0

        session_rec.total_score = max(0.0, round(total_score, 2))
        session_rec.percentage = round((session_rec.total_score / exam.total_marks) * 100, 1) if exam.total_marks > 0 else 0.0
        session_rec.passed = (session_rec.total_score >= exam.passing_marks)
        session_rec.submit_time = datetime.now(timezone.utc)
        session_rec.time_taken_seconds = int((session_rec.submit_time.replace(tzinfo=timezone.utc) - session_rec.start_time.replace(tzinfo=timezone.utc)).total_seconds())
        session_rec.status = 'completed'

        db.session.commit()
        flash("Exam submitted successfully! Here is your performance analysis.", "success")
        return redirect(url_for('student_result_analysis', session_id=session_rec.id))

    @app.route('/student/result/<int:session_id>')
    @login_required
    def student_result_analysis(session_id):
        session_rec = ExamSession.query.get_or_404(session_id)
        if session.get('role') != 'teacher' and session_rec.student_id != session['user_id']:
            flash("Unauthorized access.", "danger")
            return redirect(url_for('student_dashboard'))

        exam = session_rec.exam
        student = session_rec.student

        answers_records = StudentAnswer.query.filter_by(session_id=session_rec.id).all()
        answers_map = {a.question_id: a for a in answers_records}

        relevant_questions = [
            q for q in exam.questions
            if q.set_name in ['ALL', session_rec.assigned_set]
        ]

        analysis_items = []
        correct_count = 0
        attempted_count = 0

        for q in relevant_questions:
            d = q.get_decrypted(exam.exam_key)
            ans = answers_map.get(q.id)
            user_opt = ans.selected_option if ans else None
            is_corr = ans.is_correct if ans else False
            awarded = ans.marks_awarded if ans else 0.0

            if user_opt:
                attempted_count += 1
            if is_corr:
                correct_count += 1

            analysis_items.append({
                'question_text': d['question_text'],
                'option_a': d['option_a'],
                'option_b': d['option_b'],
                'option_c': d['option_c'],
                'option_d': d['option_d'],
                'correct_option': d['correct_option'],
                'selected_option': user_opt,
                'is_correct': is_corr,
                'marks_awarded': awarded,
                'explanation': d['explanation']
            })

        accuracy_pct = round((correct_count / attempted_count) * 100, 1) if attempted_count > 0 else 0.0

        return render_template(
            'student/result_analysis.html',
            exam=exam,
            student=student,
            session_record=session_rec,
            analysis_items=analysis_items,
            correct_count=correct_count,
            total_q_count=len(relevant_questions),
            accuracy_pct=accuracy_pct
        )

    # -------------------------------------------------------------------------
    # Anti-Cheating & Proctoring APIs
    # -------------------------------------------------------------------------
    @app.route('/api/verify-face', methods=['POST'])
    @login_required
    def api_verify_face():
        data = request.get_json() or {}
        image_base64 = data.get('image')
        exam_id = data.get('exam_id')
        student_id = session['user_id']

        if not image_base64:
            return jsonify({'success': False, 'message': 'No image received'}), 400

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"user_{student_id}_exam_{exam_id}_{timestamp}.jpg"
        save_path = os.path.join(Config.FACE_UPLOADS, filename)

        saved = save_image_from_base64(image_base64, save_path)
        if not saved:
            return jsonify({'success': False, 'message': 'Failed to process webcam image'}), 400

        face_count, faces = detect_faces(save_path)
        if face_count == 0:
            return jsonify({'success': False, 'message': 'No face detected! Make sure lighting is good and face the camera directly.'})
        if face_count > 1:
            return jsonify({'success': False, 'message': f'Multiple people ({face_count}) detected in camera view! You must be alone.'})

        student = User.query.get(student_id)
        confidence_score = 96.0

        if student.profile_photo and os.path.exists(student.profile_photo):
            matched, score, msg = compare_faces(student.profile_photo, save_path)
            confidence_score = score
            if not matched:
                return jsonify({'success': False, 'message': f'Face mismatch ({score}%): {msg}'})
        else:
            student.profile_photo = save_path

        att = Attendance.query.filter_by(exam_id=exam_id, student_id=student_id).first()
        if not att:
            att = Attendance(
                exam_id=exam_id,
                student_id=student_id,
                photo_path=filename,
                confidence_score=confidence_score,
                status='verified'
            )
            db.session.add(att)
        else:
            att.photo_path = filename
            att.confidence_score = confidence_score
            att.status = 'verified'

        db.session.commit()
        return jsonify({'success': True, 'score': confidence_score, 'message': 'Face verified successfully'})

    @app.route('/api/save-answer', methods=['POST'])
    @login_required
    def api_save_answer():
        data = request.get_json() or {}
        session_id = data.get('session_id')
        q_id = data.get('question_id')
        selected_option = data.get('selected_option')
        marked_review = bool(data.get('marked_for_review', False))

        session_rec = ExamSession.query.get(session_id)
        if not session_rec or session_rec.student_id != session['user_id']:
            return jsonify({'success': False, 'message': 'Invalid session'}), 403

        if session_rec.status == 'completed':
            return jsonify({'success': False, 'message': 'Exam already submitted'}), 400

        ans = StudentAnswer.query.filter_by(session_id=session_id, question_id=q_id).first()
        if not ans:
            ans = StudentAnswer(
                session_id=session_id,
                question_id=q_id,
                selected_option=selected_option,
                marked_for_review=marked_review
            )
            db.session.add(ans)
        else:
            ans.selected_option = selected_option
            ans.marked_for_review = marked_review

        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/log-violation', methods=['POST'])
    @login_required
    def api_log_violation():
        data = request.get_json() or {}
        session_id = data.get('session_id')
        v_type = data.get('type', 'Unknown Malpractice Alert')
        details = data.get('details', '')

        session_rec = ExamSession.query.get(session_id)
        if not session_rec or session_rec.student_id != session['user_id']:
            return jsonify({'success': False}), 403

        session_rec.log_violation(v_type, details)
        db.session.commit()

        auto_submit = (session_rec.warning_count >= Config.MAX_CHEAT_STRIKES)
        return jsonify({
            'success': True,
            'strikes': session_rec.warning_count,
            'auto_submit': auto_submit
        })

    return app

if __name__ == '__main__':
    app = create_app()
    print("=" * 65)
    print("  ASET - Ansh Secure Examination Technology")
    print("  Tagline: Secure. Offline. Intelligent.")
    print("  Server running on http://0.0.0.0:5000 (accessible on LAN)")
    print("=" * 65)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
