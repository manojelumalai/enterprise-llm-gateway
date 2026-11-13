from llm_gateway.evals.triad import RAGTriadEvaluator


def test_rag_triad_evaluator_high_groundedness():
    evaluator = RAGTriadEvaluator(pass_threshold=0.75)

    query = "What is the maximum transfer limit for FAST in Singapore?"
    context = (
        "FAST allows real-time interbank fund transfers in Singapore "
        "with a maximum limit of 200,000 SGD per transaction."
    )
    response = "The maximum transfer limit for FAST transactions in Singapore is 200,000 SGD."

    res = evaluator.evaluate(query=query, context=context, response=response)

    assert res.passed is True
    assert res.groundedness >= 0.75
    assert res.context_relevance >= 0.70
    assert res.composite_score >= 0.75


def test_rag_triad_evaluator_hallucination_fails():
    evaluator = RAGTriadEvaluator(pass_threshold=0.80)

    query = "What is the capital of Singapore?"
    context = "Singapore is an island nation located at the southern tip of the Malay Peninsula."
    # Completely hallucinated / unsupported claim
    response = "The capital of Singapore is Tokyo, which has a population of 14 million people."

    res = evaluator.evaluate(query=query, context=context, response=response)

    assert res.passed is False
    assert res.groundedness < 0.50
