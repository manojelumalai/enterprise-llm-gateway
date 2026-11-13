"""
RAG Triad Evaluation Harness: Context Relevance, Groundedness, and Answer Relevance.
Provides automated verification to prevent hallucinations and evaluate retrieval quality.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    context_relevance: float = Field(ge=0.0, le=1.0)
    groundedness: float = Field(ge=0.0, le=1.0)
    answer_relevance: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: dict[str, str] = Field(default_factory=dict)


class RAGTriadEvaluator:
    """
    Evaluates RAG pipelines against the standard "RAG Triad" metrics
    (context relevance, groundedness, answer relevance).

    This is a deterministic lexical-overlap heuristic (token set intersection),
    not an LLM judge: it is fast and dependency-free, good for CI smoke tests,
    but it cannot detect paraphrased groundedness or subtle hallucinations that
    share no words with the context. To swap in a real judge, replace the three
    `evaluate_*` methods with calls to an LLM (e.g. ask the model to score 0-1
    for each dimension with a rubric prompt) while keeping `evaluate()`'s
    composite-score/threshold logic unchanged.
    """

    def __init__(self, pass_threshold: float = 0.80) -> None:
        self.pass_threshold = pass_threshold

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
        stop_words = {
            "the",
            "and",
            "for",
            "that",
            "this",
            "with",
            "from",
            "are",
            "was",
            "were",
            "what",
            "where",
            "when",
            "which",
            "how",
            "why",
            "who",
            "can",
            "could",
            "would",
            "should",
            "will",
            "is",
            "in",
            "to",
            "of",
            "an",
            "on",
            "as",
            "at",
        }
        tokens = {w for w in words if w not in stop_words}
        return tokens if tokens else set(words)

    def evaluate_context_relevance(self, query: str, context: str) -> float:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return 1.0
        c_tokens = self._tokenize(context)
        intersection = q_tokens.intersection(c_tokens)
        return min(1.0, len(intersection) / len(q_tokens))

    def evaluate_groundedness(self, response: str, context: str) -> float:
        """
        Calculates lexical faithfulness: what fraction of key informative claims
        in the response appear in the retrieved context.
        """
        r_tokens = self._tokenize(response)
        if not r_tokens:
            return 1.0
        c_tokens = self._tokenize(context)
        grounded_tokens = r_tokens.intersection(c_tokens)
        return min(1.0, len(grounded_tokens) / len(r_tokens))

    def evaluate_answer_relevance(self, query: str, response: str) -> float:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return 1.0
        r_tokens = self._tokenize(response)
        relevance_overlap = q_tokens.intersection(r_tokens)
        return min(1.0, len(relevance_overlap) / len(q_tokens))

    def evaluate(self, query: str, context: str, response: str) -> EvaluationResult:
        cr = self.evaluate_context_relevance(query, context)
        gr = self.evaluate_groundedness(response, context)
        ar = self.evaluate_answer_relevance(query, response)

        # Composite weighted score (40% groundedness, 30% context, 30% answer)
        composite = (0.4 * gr) + (0.3 * cr) + (0.3 * ar)
        passed = (composite >= self.pass_threshold) and (gr >= 0.70)

        details = {
            "context_relevance_notes": f"Query terms matched: {cr * 100:.1f}%",
            "groundedness_notes": f"Grounded response terms: {gr * 100:.1f}%",
            "answer_relevance_notes": f"Intent coverage: {ar * 100:.1f}%",
        }

        return EvaluationResult(
            context_relevance=round(cr, 3),
            groundedness=round(gr, 3),
            answer_relevance=round(ar, 3),
            composite_score=round(composite, 3),
            passed=passed,
            details=details,
        )
