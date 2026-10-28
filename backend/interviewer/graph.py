from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import InterviewNodes, route_after_adapt, route_after_answer
from .state import InterviewState


def build_graph(llm, checkpointer=None):
    """Compile the interview state machine.

        setup -> generate_question -> await_answer --(/end)--------------------> final_report -> END
                      ^                    |  ^                                     ^
                      |                    v  |                                     |
                      |             evaluate_answer                                 |
                      |                    v  |                                     |
                      |             adapt_difficulty --(max questions reached)------+
                      |                    |
                      +--(next question)---+--(needs follow-up)--> ask_follow_up --+
    """
    n = InterviewNodes(llm)
    g = StateGraph(InterviewState)

    g.add_node("setup", n.setup)
    g.add_node("generate_question", n.generate_question)
    g.add_node("await_answer", n.await_answer)
    g.add_node("evaluate_answer", n.evaluate_answer)
    g.add_node("adapt_difficulty", n.adapt_difficulty)
    g.add_node("ask_follow_up", n.ask_follow_up)
    g.add_node("final_report", n.final_report)

    g.add_edge(START, "setup")
    g.add_edge("setup", "generate_question")
    g.add_edge("generate_question", "await_answer")
    g.add_conditional_edges(
        "await_answer", route_after_answer, {"evaluate_answer": "evaluate_answer", "final_report": "final_report"}
    )
    g.add_edge("evaluate_answer", "adapt_difficulty")
    g.add_conditional_edges(
        "adapt_difficulty",
        route_after_adapt,
        {"ask_follow_up": "ask_follow_up", "generate_question": "generate_question", "final_report": "final_report"},
    )
    g.add_edge("ask_follow_up", "await_answer")
    g.add_edge("final_report", END)

    # A checkpointer is what makes interrupt()/resume work: state is saved per thread_id.
    return g.compile(checkpointer=checkpointer or MemorySaver())
