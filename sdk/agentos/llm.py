"""LLM inference — oneshot calls and agent loops.

    from agentos import llm

    result = llm.oneshot(prompt="Summarize this.", model="haiku")
    result = llm.agent(prompt="Review this code.", model="opus", tools=["Read", "Grep"])
"""

from agentos._bridge import dispatch


def oneshot(*, prompt, model="sonnet", system=None,
            max_tokens=4096, temperature=0) -> dict:
    """Single LLM call. No tools, no agent loop.

    The engine resolves the best provider for the requested model,
    calls its chat() operation, and returns the response.
    """
    messages = [{"role": "user", "content": prompt}]
    return dispatch("__llm_chat__", {
        "model": model,
        "messages": messages,
        "system": system or "",
        "max_tokens": max_tokens,
        "temperature": temperature,
    })


def agent(*, prompt, system="", model="sonnet", tools=None,
          files=None, max_iterations=20, temperature=0) -> dict:
    """Multi-turn agent loop with tool dispatch.

    The engine resolves the inference provider, builds tool definitions,
    runs the loop, logs the conversation, and returns the result.
    """
    return dispatch("__llm_agent__", {
        "prompt": prompt,
        "system": system,
        "model": model,
        "tools": tools or [],
        "files": files or [],
        "max_iterations": max_iterations,
        "temperature": temperature,
    })
