# Author: Thomas "Bl00dvault" Blauvelt
from flask import Flask, render_template, request, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, time, csv
import keys

__version__ = '1.1.2'

app = Flask(__name__, static_url_path='/static')
app.jinja_env.globals.update(zip=zip)
app.secret_key = keys.secret_key

# Create login database
basedir = os.path.abspath(os.path.dirname(__file__))
if not os.path.exists('db/'):
    os.makedirs('db/')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db/test.db')
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignment_id = db.Column(db.Integer)
    score = db.Column(db.Integer)
    time_to_complete = db.Column(db.Float, nullable=False)
    answers = db.Column(db.String(500))

    def __repr__(self):
        return f'<TestResult {self.id}>'

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exercise_name = db.Column(db.String(64), unique=True, nullable=False)
    track = db.Column(db.String(64), nullable=False)
    questions = db.relationship('Question', backref='assignment', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(255), nullable=False)
    correct_answer = db.Column(db.String(255), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)

# Instantiate the new database
def init_db():
    db.create_all()
    
    # check if admin exists
    admin = User.query.filter_by(username='admin').first()
    
    # if admin does not exist, create one
    if admin is None:
        admin = User(username='admin')
        admin.set_password('asdf')
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()

with app.app_context():
    init_db()
    with open('exercises.json', 'r') as file:
        data = json.load(file)

    for exercise in data:
        assignment = Assignment.query.filter_by(exercise_name=exercise["ExerciseName"]).first()

        if assignment is None:
            assignment = Assignment(exercise_name=exercise["ExerciseName"], track=exercise["Track"])
            db.session.add(assignment)
            db.session.commit()  # Ensure each assignment has an ID before creating questions

        for question_text, correct_answer in exercise["Questions"].items():
            question = Question(question_text=question_text, correct_answer=correct_answer, assignment_id=assignment.id)
            db.session.add(question)

    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # Fetch the user from the database

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            return "Invalid username or password"

        login_user(user)  # Log in the user
        return redirect(url_for('home'))

    else:
        return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form

        if is_admin:
            if not current_user.is_admin:
                return "Unauthorized", 403
            else:
                user = User(username=username)
                user.set_password(password)
                user.is_admin = is_admin

                db.session.add(user)
                db.session.commit()
        else:
            user = User(username=username)
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

        return redirect(url_for('login'))
    else:
        return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not current_user.check_password(current_password):
            return "Incorrect current password"

        if new_password != confirm_password:
            return "New password and confirmation password do not match"

        current_user.set_password(new_password)
        db.session.commit()
        
        return redirect(url_for('home'))

    else:
        return render_template('change_password.html')

@app.route('/user_management', methods=['GET', 'POST'])
@login_required
def user_management():
    if not current_user.is_admin:
        return "Unauthorized", 403

    if request.method == 'POST':
        if 'delete_user_id' in request.form:
            delete_user_id = request.form['delete_user_id']
            # prevent deleting own account
            if str(current_user.id) == delete_user_id:
                return "Error: You can't delete your own account", 400
            # prevent deleting 'admin' account
            elif delete_user_id == "1":
                return "Error: You can't delete the 'admin' account", 400
            else:
                User.query.filter_by(id=delete_user_id).delete()
                db.session.commit()

        elif 'make_admin_id' in request.form:
            make_admin_id = request.form['make_admin_id']
            user = User.query.get(make_admin_id)
            user.is_admin = True
            db.session.commit()

        else:
            user_id = request.form['user_id']
            new_password = request.form['new_password']
            user = User.query.get(user_id)
            user.set_password(new_password)
            db.session.commit()
            
    users = User.query.all()
    return render_template('user_management.html', users=users)
    
# Load exercise questions and correct answers from JSON
with open('exercises.json', 'r') as file:
    exercise_data = json.load(file)
    exercises = {str(i+1): ex["ExerciseName"] for i, ex in enumerate(exercise_data)}
    exercise_track = {str(i+1): ex["Track"] for i, ex in enumerate(exercise_data)}
    exercise_questions = {str(i+1): list(ex["Questions"].keys()) for i, ex in enumerate(exercise_data)}
    exercise_answers = {str(i+1): list(ex["Questions"].values()) for i, ex in enumerate(exercise_data)}

# create a dict where each key is a track name and each value is a list of exercises for that track
exercises_by_track = {}
for id, track_name in exercise_track.items():
    if track_name not in exercises_by_track:
        exercises_by_track[track_name] = []
    exercises_by_track[track_name].append((id, exercises[id]))

@app.route('/exercise/<int:id>', methods=['GET'])
def exercise_landing_page(id):
    # Fetch the assignment from the database
    assignment = Assignment.query.get(id)
    exercise_name = assignment.exercise_name

    # If no assignment is found, return a 404 error
    if assignment is None:
        return "PDF file not found", 404

    # Extract just the filenames for academics (remove the directory prefix)
    lab_guide_filenames = sorted([f for f in os.listdir('static/academics') if f.startswith(f'{assignment.exercise_name}-Lab') and f.endswith('.pdf')])

    # Extract just the filenames for labguides (remove the directory prefix)
    academics_filenames = sorted([f for f in os.listdir('static/academics') if f.startswith(f'{assignment.exercise_name}') and f.endswith('Academics.pdf')])

    # If no matching files are found, return an error
    if not lab_guide_filenames:
        return render_template('exercise_landing_page.html', id=id, lab_guide_filenames=lab_guide_filenames)
    
    return render_template('exercise_landing_page.html', id=id, lab_guide_filenames=lab_guide_filenames, academics_filenames=academics_filenames, exercise_name=exercise_name)

@app.route('/exercise/<int:id>/clear', methods=['GET'])
def exercise_clear(id):
    exercise_id = str(id)
    
    # Loop over the session keys for this exercise and delete them
    for i in range(len(session)):
        session.pop(f'{exercise_id}_{i}', None)
    
    return redirect(url_for('exercise_assessment', id=exercise_id))

@app.route('/exercise/<int:id>/assessment', methods=['GET', 'POST'])
def exercise_assessment(id):
    exercise_id = str(id)
    student_answers = request.form.getlist('answer')
    exercise_name = exercises.get(exercise_id)

    if request.method == 'POST':
        student_answers = request.form.getlist('answer')

        # Store the current time as the start time for this exercise
        session['start_time'] = time.time()
        
        correct_answers = exercise_answers.get(id)
        result_text = []

        for student_answer, correct_answer in zip(student_answers, correct_answers):
            if student_answer.lower() == correct_answer.lower():
                result_text.append('Correct!')
            else:
                result_text.append('Incorrect!')
        
        # Store the submitted answers in the session
        for i, answer in enumerate(student_answers):
            session[f'{id}_{i}'] = answer

        return render_template('result.html', result=result_text, id=id, answers=student_answers, exercises=exercises, exercise_name=exercise_name)
    elif request.method == 'GET':
        questions = exercise_questions.get(str(id))

        if questions is None:
            # Provide an appropriate message to the user or redirect to another page
            return "No questions found for this exercise id", 400

        # Get all previously submitted answers for this exercise
        answers = [session.get(f'{id}_{i}', '') for i in range(len(questions))]

        # Store the current time as the start time for this exercise
        session['start_time'] = time.time()

        return render_template('exercise.html', id=id, questions=questions, answers=answers, exercises=exercises, exercise_name=exercise_name)

@app.route('/result/<int:id>', methods=['POST'])
def result(id):
    exercise_id = str(id)
    student_answers = request.form.getlist('answer')
    exercise_name = exercises.get(exercise_id)
    questions = exercise_questions.get(exercise_id)
    correct_answers = exercise_answers.get(exercise_id)
    result_text = []
    start_time = session.get('start_time')
    end_time = time.time()  # The current time is the end time of the test

    for student_answer, correct_answer in zip(student_answers, correct_answers):
        if student_answer.lower() == correct_answer.lower():
            result_text.append('Correct!')
        else:
            result_text.append('Incorrect!')
    
    # Calculate the score as the number of correct answers
    score = int(result_text.count('Correct!') / len(questions) * 100)

    # Store the submitted answers in the session
    for i, answer in enumerate(student_answers):
        session[f'{exercise_id}_{i}'] = answer
    
    # Store the test result in the database
    time_to_complete = int(end_time - start_time)
    test_result = TestResult(
        user_id=current_user.id,
        assignment_id=exercise_id,
        score=score,
        time_to_complete=time_to_complete,
        answers=json.dumps(student_answers)  # Store the answers as a JSON string
    )
    db.session.add(test_result)
    db.session.commit()

    return render_template('result.html', result=result_text, id=exercise_id, answers=student_answers, exercise_name=exercise_name, questions=questions, correct_answers=correct_answers, exercises=exercises, test_result=test_result)

@app.route('/all_results', methods=['GET', 'POST'])
def all_results():
    # Ensure only admin users can access this page
    if not current_user.is_admin:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Fetch all test results
        test_results = db.session.query(TestResult, User, Assignment)\
        .join(User, TestResult.user_id == User.id)\
        .join(Assignment, TestResult.assignment_id == Assignment.id).all()

        # specify the path to your csv file
        csv_file_path = "scores/results.csv"

        # open the file in write mode
        with open(csv_file_path, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            
            # write the header
            writer.writerow(["UserName","ExerciseName", "Score", "Time (seconds)"])
                
            for result, user, assignment in test_results:
                writer.writerow([user.username, assignment.exercise_name, result.score, int(result.time_to_complete)])
        
        return "Results have been written to csv file.", 200

    elif request.method == 'GET':
        # Fetch all test results
        test_results = db.session.query(TestResult, User, Assignment)\
        .join(User, TestResult.user_id == User.id)\
        .join(Assignment, TestResult.assignment_id == Assignment.id).all()

        # Group test results by user
        results_by_user = {}
        for result, user, assignment in test_results:
            if user.username not in results_by_user:
                results_by_user[user.username] = []
            results_by_user[user.username].append({
                'exercise_name': assignment.exercise_name,
                'score': result.score,
                'time_to_complete': int(result.time_to_complete)
            })

        return render_template('all_results.html', results_by_user=results_by_user)

@app.context_processor
def inject_version():
    return dict(version=__version__)

@app.route('/')
def home():
    return render_template('index.html', exercises=exercises, tracks=exercises_by_track, current_user=current_user)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
