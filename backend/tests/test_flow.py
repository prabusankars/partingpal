from app.interview.engine import is_repeat, strip_marker
from app.interview.flow import Assessment, Directive, FlowState, advance
from app.interview.topics import TOPICS

LIMITS = dict(max_turns=20, max_followups=1)


def run(answers: list[Assessment], **limits):
    state, log = FlowState(), []
    for a in answers:
        t = advance(state, a, **{**LIMITS, **limits})
        log.append((t.directive, t.state.current_topic))
        state = t.state
        if t.directive is Directive.CLOSE:
            return state, log, t.completion_reason
    return state, log, None


def asked_topics(log):
    return [topic for directive, topic in log if directive is Directive.ASK_TOPIC]


def test_each_topic_asked_once_in_order_then_wrap_up_and_close():
    state, log, reason = run([Assessment()] * 20)
    assert asked_topics(log) == [t.id for t in TOPICS[1:]]
    assert log[-2][0] is Directive.WRAP_UP
    assert reason == "completed"
    assert state.user_turns == len(TOPICS) + 1
    assert set(state.covered) == {t.id for t in TOPICS}


def test_follow_ups_are_capped_then_topic_moves_on():
    vague = Assessment(answered=False)
    _, log, _ = run([vague, vague, vague])
    assert log[0] == (Directive.FOLLOW_UP, "reasons_for_leaving")
    assert log[1] == (Directive.ASK_TOPIC, "job_satisfaction")  # moved on despite a second vague answer
    assert log[2] == (Directive.FOLLOW_UP, "job_satisfaction")


def test_declined_topic_is_skipped_and_never_revisited():
    state, log, _ = run([Assessment(declined=True)] + [Assessment()] * 20)
    assert "reasons_for_leaving" in state.declined
    assert "reasons_for_leaving" not in asked_topics(log)


def test_topic_covered_in_passing_is_not_asked():
    state, log, _ = run([Assessment(also_covered=["compensation_benefits", "not_a_topic"])] + [Assessment()] * 20)
    assert "compensation_benefits" not in asked_topics(log)
    assert "not_a_topic" not in state.covered


def test_employee_can_end_any_time():
    _, log, reason = run([Assessment(), Assessment(wants_to_end=True)])
    assert log[-1][0] is Directive.CLOSE
    assert reason == "employee_ended"


def test_hard_turn_limit():
    vague = Assessment(answered=False)
    state, log, reason = run([vague] * 50, max_turns=6)
    assert state.user_turns == 6
    assert log[-2][0] is Directive.WRAP_UP
    assert reason == "turn_limit"


def test_repeat_detection_and_marker_stripping():
    assert is_repeat("Thanks. What made you decide to leave?", ["Hello! What made you decide to leave ?"])
    assert not is_repeat("How was your manager?", ["What made you decide to leave?"])
    assert strip_marker("Goodbye!\n[INTERVIEW_COMPLETE]") == ("Goodbye!", True)
