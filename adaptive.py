# =============================================================================
# adaptive.py
# -----------------------------------------------------------------------------
# This file contains the adaptive algorithm. It is the most important part of
# the project and the part we explain most carefully in the write-up.
#
# The idea (called the "Leitner system"):
#   - Every question a student sees lives in a "box" numbered 1 to 5.
#   - A new or badly known question sits in box 1 and is asked often.
#   - Each time the student answers correctly, the question moves up a box
#     and is then left alone for longer.
#   - If the student gets it wrong, it drops straight back to box 1.
#
# On top of the boxes we add a "weighting" step so that, when choosing the
# next question, weak and overdue questions are far more likely to be picked
# than questions the student already knows.
# =============================================================================

import random
from datetime import datetime, timedelta

from models import database, ScheduleState

# ----- Named constants (no "magic numbers" hidden in the code) ---------------

LOWEST_BOX = 1
HIGHEST_BOX = 5

# How long to wait before asking a question again, measured in days,
# for each box. Box 1 is due straight away (0 days). Each box up roughly
# doubles the wait, which is what spaced repetition is.
WAIT_IN_DAYS_FOR_BOX = {
    1: 0,
    2: 1,
    3: 3,
    4: 7,
    5: 16,
}

# A question that is due (or overdue) is much more important to ask, so we
# multiply its weight by this number.
OVERDUE_WEIGHT_MULTIPLIER = 3


def get_or_create_schedule_state(user_id, question_id):
    """
    Find the schedule state for one student on one question. If it does not
    exist yet (the student has never seen this question), create a new one
    in box 1, due immediately.

    Input:  user_id and question_id, both integers.
    Output: a ScheduleState object.
    """
    state = ScheduleState.query.filter_by(
        user_id=user_id, question_id=question_id
    ).first()

    if state is None:
        state = ScheduleState(
            user_id=user_id,
            question_id=question_id,
            box=LOWEST_BOX,
            due_at=datetime.now(),
            times_seen=0,
        )
        database.session.add(state)
        database.session.commit()

    return state


def calculate_weight(state):
    """
    Work out how strongly we want to ask one question, as a whole number.
    A bigger number means "ask this one sooner".

    Rule 1: the lower the box, the less well the student knows it, so the
            higher the weight. We do this with (HIGHEST_BOX + 1 - box),
            which gives box 1 a weight of 5 and box 5 a weight of 1.
    Rule 2: if the question is due or overdue, multiply the weight so it
            jumps to the front of the queue.

    Input:  state, a ScheduleState object.
    Output: an integer weight (always at least 1).
    """
    base_weight = (HIGHEST_BOX + 1) - state.box

    now = datetime.now()
    if state.due_at <= now:
        weight = base_weight * OVERDUE_WEIGHT_MULTIPLIER
    else:
        weight = base_weight

    return weight


def choose_next_question(user_id, questions):
    """
    Choose the next question to ask a student, using weighted random
    selection. Weak and overdue questions are far more likely to be chosen,
    but every question keeps a small chance, so revision stays varied.

    Input:  user_id, an integer.
            questions, a list of Question objects (all from one topic).
    Output: one Question object, or None if the list was empty.
    """
    if len(questions) == 0:
        return None

    # Step 1: work out the weight for every question and add up the total.
    weighted_questions = []
    total_weight = 0
    for question in questions:
        state = get_or_create_schedule_state(user_id, question.id)
        weight = calculate_weight(state)
        weighted_questions.append((question, weight))
        total_weight = total_weight + weight

    # Step 2: pick a random target number between 0 and the total weight.
    target = random.uniform(0, total_weight)

    # Step 3: walk through the questions adding up weights until we pass the
    # target. The question we stop on is the one we have chosen. This is the
    # standard way to do weighted random selection by hand.
    running_total = 0
    for question, weight in weighted_questions:
        running_total = running_total + weight
        if running_total >= target:
            return question

    # If rounding ever leaves us here, return the last question as a fallback.
    return weighted_questions[-1][0]


def update_schedule_after_answer(state, was_correct):
    """
    Update one schedule state after the student has answered the question.

    If the answer was correct, move the question up one box (but never above
    the highest box) and set its next due date further into the future.
    If the answer was wrong, drop it back to box 1 so it is asked again soon.

    Input:  state, a ScheduleState object.
            was_correct, True or False.
    Output: nothing is returned; the state is changed and saved.
    """
    if was_correct:
        if state.box < HIGHEST_BOX:
            state.box = state.box + 1
    else:
        state.box = LOWEST_BOX

    # Look up how long to wait for the new box, then set the due date.
    wait_in_days = WAIT_IN_DAYS_FOR_BOX[state.box]
    state.due_at = datetime.now() + timedelta(days=wait_in_days)

    state.times_seen = state.times_seen + 1

    database.session.commit()