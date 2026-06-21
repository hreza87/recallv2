# =============================================================================
# seed_data.py
# -----------------------------------------------------------------------------
# When the database is brand new it is empty, which makes the app hard to try
# out. This function adds two demo accounts, a few topics and some sample
# questions so there is something to see straight away.
#
# It only adds the data if the database is still empty, so it is safe to run
# every time the app starts.
# =============================================================================

from werkzeug.security import generate_password_hash

from models import database, User, Topic, Question


def add_sample_question(topic, text, a, b, c, d, correct, difficulty):
    """
    A small helper that builds one Question and adds it to the database
    session. It does not save on its own; the caller saves at the end.

    Input:  topic, a Topic object the question belongs to.
            text, the question wording.
            a, b, c, d, the four option texts.
            correct, the letter of the correct option.
            difficulty, a number 1 to 3.
    Output: nothing is returned.
    """
    question = Question(
        topic_id=topic.id,
        question_text=text,
        option_a=a,
        option_b=b,
        option_c=c,
        option_d=d,
        correct_option=correct,
        difficulty=difficulty,
    )
    database.session.add(question)


def seed_database_if_empty():
    """
    Add demo data, but only if there are no users yet.

    Input:  nothing.
    Output: nothing is returned. The database may be changed and saved.
    """
    existing_users = User.query.count()
    if existing_users > 0:
        return

    # --- Two demo accounts. Passwords are hashed, never stored as plain text.
    teacher = User(
        username="teacher",
        password_hash=generate_password_hash("teacher123"),
        role="teacher",
    )
    student = User(
        username="student",
        password_hash=generate_password_hash("student123"),
        role="student",
    )
    database.session.add(teacher)
    database.session.add(student)

    # --- A few topics.
    networks = Topic(name="Networks")
    algorithms = Topic(name="Algorithms")
    data_representation = Topic(name="Data Representation")
    database.session.add(networks)
    database.session.add(algorithms)
    database.session.add(data_representation)

    # We must save here so the topics get their id numbers before we add
    # questions that point at them.
    database.session.commit()

    # --- Sample questions for each topic.
    add_sample_question(
        networks,
        "What does LAN stand for?",
        "Local Area Network",
        "Large Access Node",
        "Linked Array Network",
        "Logical Address Name",
        "A",
        1,
    )
    add_sample_question(
        networks,
        "Which device connects two different networks together?",
        "A switch",
        "A router",
        "A repeater",
        "A hub",
        "B",
        2,
    )
    add_sample_question(
        algorithms,
        "What is the worst-case time complexity of a linear search?",
        "O(1)",
        "O(log n)",
        "O(n)",
        "O(n squared)",
        "C",
        2,
    )
    add_sample_question(
        algorithms,
        "Which algorithm repeatedly splits a sorted list in half to find a value?",
        "Bubble sort",
        "Linear search",
        "Binary search",
        "Merge sort",
        "C",
        1,
    )
    add_sample_question(
        data_representation,
        "How many bits are there in one byte?",
        "4",
        "8",
        "16",
        "32",
        "B",
        1,
    )
    add_sample_question(
        data_representation,
        "What is the denary (decimal) value of the binary number 1010?",
        "5",
        "8",
        "10",
        "12",
        "C",
        2,
    )

    database.session.commit()