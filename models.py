# =============================================================================
# models.py
# -----------------------------------------------------------------------------
# This file defines every table in the database.
#
# We use SQLAlchemy, which lets us describe each table as a Python class.
# Each class becomes one table. Each class attribute becomes one column.
#
# The tables and how they relate to each other:
#
#   User  ---<  Response        (one user writes many responses)
#   User  ---<  ScheduleState   (one user has many schedule states)
#   Topic ---<  Question        (one topic contains many questions)
#   Question ---< Response      (one question receives many responses)
#   Question ---< ScheduleState (one question has many schedule states)
#
# The "---<" symbol means "one to many".
# =============================================================================

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

# Create the database object. We attach it to the Flask app later, in app.py.
# Keeping it here (and not inside app.py) avoids an import loop between the
# two files.
database = SQLAlchemy()


class User(database.Model, UserMixin):
    """
    One row = one person who can log in.

    We never store the real password. We store a hashed version of it,
    which cannot be turned back into the original password. The 'role'
    is either "teacher" or "student", and decides what the user is
    allowed to do.
    """

    __tablename__ = "users"

    id = database.Column(database.Integer, primary_key=True)
    username = database.Column(database.String(80), unique=True, nullable=False)
    password_hash = database.Column(database.String(256), nullable=False)
    role = database.Column(database.String(20), nullable=False)

    # These links let us write, for example, a_user.responses to get a list
    # of all that user's responses.
    responses = database.relationship("Response", backref="user", lazy=True)
    schedule_states = database.relationship("ScheduleState", backref="user", lazy=True)


class Topic(database.Model):
    """
    One row = one subject area, for example "Networks" or "Algorithms".
    Every question belongs to exactly one topic.
    """

    __tablename__ = "topics"

    id = database.Column(database.Integer, primary_key=True)
    name = database.Column(database.String(120), unique=True, nullable=False)

    # All the questions that belong to this topic.
    questions = database.relationship("Question", backref="topic", lazy=True)


class Question(database.Model):
    """
    One row = one multiple-choice question.

    A question stores its text, four answer options, the letter of the
    correct option ("A", "B", "C" or "D") and a difficulty number from
    1 (easy) to 3 (hard).
    """

    __tablename__ = "questions"

    id = database.Column(database.Integer, primary_key=True)
    topic_id = database.Column(database.Integer, database.ForeignKey("topics.id"), nullable=False)
    question_text = database.Column(database.String(500), nullable=False)
    option_a = database.Column(database.String(200), nullable=False)
    option_b = database.Column(database.String(200), nullable=False)
    option_c = database.Column(database.String(200), nullable=False)
    option_d = database.Column(database.String(200), nullable=False)
    correct_option = database.Column(database.String(1), nullable=False)
    difficulty = database.Column(database.Integer, nullable=False, default=1)

    responses = database.relationship("Response", backref="question", lazy=True)
    schedule_states = database.relationship("ScheduleState", backref="question", lazy=True)

    def get_option_text(self, option_letter):
        """
        Return the text of one option given its letter.

        Input:  option_letter, a string that is "A", "B", "C" or "D".
        Output: the matching option text, or an empty string if the
                letter is not recognised.
        """
        if option_letter == "A":
            return self.option_a
        elif option_letter == "B":
            return self.option_b
        elif option_letter == "C":
            return self.option_c
        elif option_letter == "D":
            return self.option_d
        else:
            return ""


class Response(database.Model):
    """
    One row = one answer that one student gave to one question.

    This is the history log. We use it to work out how well a student
    is doing in each topic.
    """

    __tablename__ = "responses"

    id = database.Column(database.Integer, primary_key=True)
    user_id = database.Column(database.Integer, database.ForeignKey("users.id"), nullable=False)
    question_id = database.Column(database.Integer, database.ForeignKey("questions.id"), nullable=False)
    was_correct = database.Column(database.Boolean, nullable=False)
    answered_at = database.Column(database.DateTime, nullable=False, default=datetime.now)


class ScheduleState(database.Model):
    """
    One row = the adaptive memory for one student on one question.

    'box' is the Leitner box number from 1 to 5. A low box means the
    student keeps getting the question wrong, so we should ask it often.
    A high box means they know it well, so we ask it rarely.

    'due_at' is the date and time when the question should next be asked.
    'times_seen' counts how many times the student has answered it.
    """

    __tablename__ = "schedule_states"

    id = database.Column(database.Integer, primary_key=True)
    user_id = database.Column(database.Integer, database.ForeignKey("users.id"), nullable=False)
    question_id = database.Column(database.Integer, database.ForeignKey("questions.id"), nullable=False)
    box = database.Column(database.Integer, nullable=False, default=1)
    due_at = database.Column(database.DateTime, nullable=False, default=datetime.now)
    times_seen = database.Column(database.Integer, nullable=False, default=0)