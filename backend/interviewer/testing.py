"""Deterministic stand-in for a chat model: lets you run the whole graph offline and in CI.

Implements just the slice of the LangChain API the nodes use: `.with_structured_output(schema).invoke(messages)`.
Grading heuristic (offline demo only): longer answers score higher, so you can watch difficulty adapt.
"""
import re

from .schemas import (
    AnswerEvaluation, FinalAnalysis, GeneratedQuestion, QuestionCheck, ResumeExperience, ResumeProfile,
)


class FakeLLM:
    def with_structured_output(self, schema):
        return _FakeRunnable(schema)


class _FakeRunnable:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages):
        user = messages[1][1]  # the original human message (retries append after it)
        if self.schema is GeneratedQuestion:
            topic = re.search(r"Topic: (.+)", user).group(1).strip()
            level = re.search(r"Target difficulty: (\d)", user).group(1)
            return GeneratedQuestion(
                question=f"(Level {level}) Walk me through a key concept in {topic}.",
                reference_answer="The core mechanism explained clearly, followed by its trade-offs and edge cases.",
                key_points=["Core mechanism", "Trade-offs and edge cases"],
                resume_anchor="Your most recent role" if "<resume>" in user else "",
            )
        if self.schema is AnswerEvaluation:
            answer = re.search(r"<candidate_answer>\n(.*?)\n</candidate_answer>", user, re.S).group(1)
            words = len(answer.split())
            score = 0 if words == 0 else 2 if words < 15 else 6 if words < 40 else 9
            partial = 15 <= words < 40
            return AnswerEvaluation(
                reasoning="Offline heuristic based on answer length.",
                correctness=score,
                depth=max(0, score - 1),
                communication=score,
                covered_points=["Core mechanism"] if score >= 6 else [],
                missed_points=[] if score >= 9 else ["Trade-offs and edge cases"],
                misconceptions=[],
                feedback=f"Answer length suggests a {score}/10 response (offline heuristic).",
                needs_follow_up=partial,
                follow_up_question="Can you go deeper on the trade-offs?" if partial else None,
            )
        if self.schema is QuestionCheck:
            return QuestionCheck(is_correct=True)
        if self.schema is FinalAnalysis:
            return FinalAnalysis(
                summary="Offline demo analysis generated without an LLM.",
                strengths=["Completed the interview loop"],
                weaknesses=["Depth on trade-offs"],
                study_plan=["Practice articulating trade-offs for each design choice"],
            )
        if self.schema is ResumeProfile:
            text = re.search(r"<resume_text>\n(.*?)\n</resume_text>", user, re.S).group(1)
            known = ["Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "SQL", "PostgreSQL", "MongoDB", "Redis",
                     "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Kafka", "Spark", "FastAPI", "Django", "Go", "C++",
                     "TensorFlow", "PyTorch", "Git", "Linux", "GraphQL"]
            skills = [k for k in known if re.search(rf"(?<![A-Za-z]){re.escape(k)}(?![A-Za-z])", text, re.I)]
            return ResumeProfile(
                name=(text.strip().splitlines() or ["Candidate"])[0][:60],
                headline="Offline demo summary of the resume.",
                suggested_role="Software Engineer",
                skills=skills[:12] or ["Python"],
                experience=[ResumeExperience(company="Your company", title="Engineer",
                                             highlights=["Built and shipped features"], technologies=skills[:4])],
            )
        raise ValueError(f"FakeLLM has no behaviour for {self.schema}")