# =============================================================================
# reporting.py
# -----------------------------------------------------------------------------
# These functions work out how well students are doing. The only maths used
# here is counting and percentages, so it is easy to explain in the write-up.
# =============================================================================

from models import Response, Question, Topic


def calculate_topic_accuracy(user_id, topic_id):
    """
    Work out a student's percentage score in one topic.

    We look at every answer the student has given to questions in this topic,
    count how many were correct, and turn that into a percentage.

    Input:  user_id and topic_id, both integers.
    Output: a tuple (percentage, number_answered).
            percentage is a whole number 0 to 100.
            If the student has not answered anything yet, we return (0, 0).
    """
    # Get the id of every question in this topic.
    questions_in_topic = Question.query.filter_by(topic_id=topic_id).all()
    question_ids = []
    for question in questions_in_topic:
        question_ids.append(question.id)

    if len(question_ids) == 0:
        return (0, 0)

    # Get every answer this student gave to those questions.
    responses = Response.query.filter(
        Response.user_id == user_id,
        Response.question_id.in_(question_ids),
    ).all()

    number_answered = len(responses)
    if number_answered == 0:
        return (0, 0)

    number_correct = 0
    for response in responses:
        if response.was_correct:
            number_correct = number_correct + 1

    percentage = round((number_correct / number_answered) * 100)
    return (percentage, number_answered)


def get_focus_areas(user_id):
    """
    Build a list of the student's topics, weakest first, so they know what
    to revise next.

    Input:  user_id, an integer.
    Output: a list of dictionaries. Each dictionary has 'topic_name',
            'percentage' and 'number_answered'. Topics the student has
            never answered are left out. The list is sorted with the
            lowest percentage first.
    """
    all_topics = Topic.query.all()
    focus_list = []

    for topic in all_topics:
        percentage, number_answered = calculate_topic_accuracy(user_id, topic.id)
        if number_answered > 0:
            focus_list.append(
                {
                    "topic_name": topic.name,
                    "percentage": percentage,
                    "number_answered": number_answered,
                }
            )

    # Sort so the weakest topic (lowest percentage) comes first.
    # We use a simple key function rather than anything clever.
    def get_percentage(item):
        return item["percentage"]

    focus_list.sort(key=get_percentage)
    return focus_list