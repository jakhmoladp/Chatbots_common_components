"""The chatbot brain -- deliberately a stub.

The six modules are a *translation layer*. This file is the seam where a real
chatbot goes. It always sees English in and returns English out, so swapping
it for an LLM, a RAG pipeline, or a rules engine changes nothing else.

Replace `reply()` with a real implementation when you are ready. Everything
around it -- detection, both translation directions, speech in and out -- keeps
working unchanged.
"""

from __future__ import annotations

_CANNED: list[tuple[tuple[str, ...], str]] = [
    (("hello", "hi", "hey", "greetings"), "Hello. How can I help you today?"),
    (("how are you",), "I am well, thank you for asking. What can I do for you?"),
    (("your name", "who are you"), "I am a translation demo bot. I speak through translation."),
    (("thank", "thanks"), "You are very welcome."),
    (("bye", "goodbye", "see you"), "Goodbye. Talk to you soon."),
    (("help",), "Type or speak in any supported language and I will reply in the one you picked."),
]


def reply(english_text: str) -> str:
    """Take an English message, return an English response.

    The contract matters more than the implementation: English in, English out.
    Keep it that way and modules 4 and 5 never need to change.
    """
    if not english_text or not english_text.strip():
        return "I did not catch that. Could you say it again?"

    lowered = english_text.lower()

    for triggers, response in _CANNED:
        if any(trigger in lowered for trigger in triggers):
            return response

    if lowered.rstrip().endswith("?"):
        return (
            "That is a good question. This demo bot has no real knowledge yet -- "
            "swap the reply() function in bot.py for an LLM call and it will."
        )

    return (
        f"You said: {english_text.strip()} "
        "(This is a placeholder reply. See bot.py to make it a real chatbot.)"
    )
