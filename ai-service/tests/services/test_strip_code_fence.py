"""strip_code_fence: structured output wrapped in ```json fences (Anthropic) must validate."""

from app.services.llm_service import strip_code_fence


def test_plain_json_is_untouched():
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'


def test_json_fence_is_removed():
    assert strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_bare_fence_with_surrounding_whitespace():
    assert strip_code_fence('\n```\n{\n  "a": 1\n}\n```\n') == '{\n  "a": 1\n}'


def test_text_around_fence_is_not_stripped():
    text = 'Aqui va:\n```json\n{"a": 1}\n```'
    assert strip_code_fence(text) == text
