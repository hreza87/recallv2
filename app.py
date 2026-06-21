# =============================================================================
# app.py
# -----------------------------------------------------------------------------
# This is the main file. It:
#   - creates the Flask web application,
#   - connects it to the database,
#   - sets up logging in and out,
#   - and defines every page (called a "route").
#
# Run it with:  python app.py
# Then open the address it prints (usually http://127.0.0.1:5000) in a browser.
# =============================================================================

from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import database, User, Topic, Question, Response
from adaptive import (
    get_or_create_schedule_state,
    choose_next_question,
    update_schedule_after_answer,
)
from reporting import calculate_topic_accuracy, get_focus_areas
from seed_data import seed_database_if_empty


# ----- Create and configure the application ----------------------------------

app = Flask(__name__)

# The secret key is used to keep login sessions safe. In a real, public app
# this must be a long random value kept private, not the simple value below.
app.config["SECRET_KEY"] = "change-this-secret-key-for-a-real-deployment"

# Tell SQLAlchemy to store the database in a file called recall.db.
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recall.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Connect the database object (made in models.py) to this application.
database.init_app(app)


# ----- Set up Flask-Login ----------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login calls this to fetch the logged-in user from their id.

    Input:  user_id, a string holding the user's id.
    Output: the matching User object, or None.
    """
    return User.query.get(int(user_id))


# ----- Pages (routes) --------------------------------------------------------

@app.route("/")
def home():
    """
    The front page. If the user is logged in, send them to the right
    dashboard for their role. Otherwise show the login page.
    """
    if current_user.is_authenticated:
        if current_user.role == "teacher":
            return redirect(url_for("teacher_dashboard"))
        else:
            return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Let a new person create an account. On a GET request we show the form.
    On a POST request we check the details and create the account.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        # --- Validation, done step by step so it is easy to follow.
        if username == "":
            flash("Please enter a username.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Your password must be at least 6 characters long.")
            return render_template("register.html")

        if role != "teacher" and role != "student":
            flash("Please choose whether you are a teacher or a student.")
            return render_template("register.html")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user is not None:
            flash("That username is already taken. Please choose another.")
            return render_template("register.html")

        # --- All checks passed, so create the account with a hashed password.
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        database.session.add(new_user)
        database.session.commit()

        flash("Account created. You can now log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Let a person log in. We look up their username, then check the password
    against the stored hash.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        # Check the user exists AND the password matches the stored hash.
        if user is not None and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("home"))
        else:
            flash("Wrong username or password.")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Log the current user out and return to the login page."""
    logout_user()
    return redirect(url_for("login"))


# ----- Student pages ---------------------------------------------------------

@app.route("/student")
@login_required
def student_dashboard():
    """
    The student's home page. It lists the topics they can revise.
    """
    if current_user.role != "student":
        flash("That page is for students.")
        return redirect(url_for("home"))

    all_topics = Topic.query.all()
    return render_template("student_dashboard.html", topics=all_topics)


@app.route("/quiz/<int:topic_id>", methods=["GET", "POST"])
@login_required
def quiz(topic_id):
    """
    Show one adaptive question from a topic, and mark the answer when the
    student submits it.

    On GET: choose a question with the adaptive algorithm and display it.
    On POST: mark the submitted answer, update the schedule, and show
             feedback.
    """
    if current_user.role != "student":
        flash("That page is for students.")
        return redirect(url_for("home"))

    topic = Topic.query.get(topic_id)
    if topic is None:
        flash("That topic does not exist.")
        return redirect(url_for("student_dashboard"))

    # --- Marking a submitted answer.
    if request.method == "POST":
        question_id = request.form.get("question_id", "")
        chosen_option = request.form.get("chosen_option", "")

        question = Question.query.get(int(question_id))
        if question is None:
            flash("Something went wrong with that question.")
            return redirect(url_for("quiz", topic_id=topic_id))

        if chosen_option == "":
            flash("Please choose an answer before submitting.")
            return render_template("quiz.html", topic=topic, question=question)

        was_correct = chosen_option == question.correct_option

        # Save the answer in the history log.
        new_response = Response(
            user_id=current_user.id,
            question_id=question.id,
            was_correct=was_correct,
            answered_at=datetime.now(),
        )
        database.session.add(new_response)
        database.session.commit()

        # Update the adaptive schedule for this question.
        state = get_or_create_schedule_state(current_user.id, question.id)
        update_schedule_after_answer(state, was_correct)

        correct_text = question.get_option_text(question.correct_option)
        return render_template(
            "quiz.html",
            topic=topic,
            question=question,
            answered=True,
            was_correct=was_correct,
            correct_option=question.correct_option,
            correct_text=correct_text,
            chosen_option=chosen_option,
        )

    # --- Showing a fresh question (GET request).
    questions_in_topic = Question.query.filter_by(topic_id=topic_id).all()
    if len(questions_in_topic) == 0:
        flash("This topic has no questions yet.")
        return redirect(url_for("student_dashboard"))

    question = choose_next_question(current_user.id, questions_in_topic)
    return render_template("quiz.html", topic=topic, question=question)


@app.route("/focus")
@login_required
def focus_areas():
    """
    Show the student a list of their topics, weakest first, so they know
    what to revise next.
    """
    if current_user.role != "student":
        flash("That page is for students.")
        return redirect(url_for("home"))

    focus_list = get_focus_areas(current_user.id)
    return render_template("focus_areas.html", focus_list=focus_list)


# ----- Teacher pages ---------------------------------------------------------

@app.route("/teacher")
@login_required
def teacher_dashboard():
    """
    The teacher's home page. It shows, for each student, how well they are
    doing in each topic. The numbers are also passed to a chart.
    """
    if current_user.role != "teacher":
        flash("That page is for teachers.")
        return redirect(url_for("home"))

    all_topics = Topic.query.all()
    all_students = User.query.filter_by(role="student").all()

    # Build a table of results: one row per student, one number per topic.
    student_rows = []
    for student in all_students:
        topic_scores = []
        for topic in all_topics:
            percentage, number_answered = calculate_topic_accuracy(
                student.id, topic.id
            )
            topic_scores.append(
                {
                    "percentage": percentage,
                    "number_answered": number_answered,
                }
            )
        student_rows.append(
            {
                "username": student.username,
                "topic_scores": topic_scores,
            }
        )

    # Work out the class average for each topic, for the chart.
    topic_names = []
    topic_averages = []
    for topic_index in range(len(all_topics)):
        topic_names.append(all_topics[topic_index].name)

        total = 0
        count = 0
        for row in student_rows:
            score = row["topic_scores"][topic_index]
            if score["number_answered"] > 0:
                total = total + score["percentage"]
                count = count + 1

        if count > 0:
            average = round(total / count)
        else:
            average = 0
        topic_averages.append(average)

    return render_template(
        "teacher_dashboard.html",
        topics=all_topics,
        student_rows=student_rows,
        topic_names=topic_names,
        topic_averages=topic_averages,
    )


@app.route("/teacher/questions", methods=["GET", "POST"])
@login_required
def manage_questions():
    """
    Let a teacher add a new question. On GET we show the form and the list
    of existing questions. On POST we validate and save the new question.
    """
    if current_user.role != "teacher":
        flash("That page is for teachers.")
        return redirect(url_for("home"))

    if request.method == "POST":
        topic_id = request.form.get("topic_id", "")
        question_text = request.form.get("question_text", "").strip()
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()
        correct_option = request.form.get("correct_option", "")
        difficulty = request.form.get("difficulty", "1")

        # --- Validation.
        if question_text == "":
            flash("Please enter the question text.")
            return redirect(url_for("manage_questions"))

        if option_a == "" or option_b == "" or option_c == "" or option_d == "":
            flash("Please fill in all four options.")
            return redirect(url_for("manage_questions"))

        if correct_option not in ["A", "B", "C", "D"]:
            flash("Please choose which option is correct.")
            return redirect(url_for("manage_questions"))

        topic = Topic.query.get(int(topic_id))
        if topic is None:
            flash("Please choose a valid topic.")
            return redirect(url_for("manage_questions"))

        # --- Save the question.
        new_question = Question(
            topic_id=topic.id,
            question_text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option,
            difficulty=int(difficulty),
        )
        database.session.add(new_question)
        database.session.commit()

        flash("Question added.")
        return redirect(url_for("manage_questions"))

    all_topics = Topic.query.all()
    all_questions = Question.query.all()
    return render_template(
        "manage_questions.html",
        topics=all_topics,
        questions=all_questions,
    )


# ----- Start the application -------------------------------------------------

def setup_database():
    """
    Create the database tables if they do not exist yet, then add the demo
    data. This runs inside the application context so the database knows
    which app it belongs to.
    """
    with app.app_context():
        database.create_all()
        seed_database_if_empty()


if __name__ == "__main__":
    setup_database()
    app.run(debug=True)