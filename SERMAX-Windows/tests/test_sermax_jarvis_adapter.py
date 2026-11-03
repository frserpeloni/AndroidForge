from sermax_jarvis_adapter import JarvisAdapter


class FakeJarvis:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.closed = False

    def ask(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return "Resposta local"

    def close(self):
        self.closed = True


def test_jarvis_uses_simple_agent_without_tools_or_memory():
    instances = []

    def factory(**kwargs):
        item = FakeJarvis(**kwargs)
        instances.append(item)
        return item

    adapter = JarvisAdapter(model="sermax", sdk_factory=factory)
    assert adapter.responder("Olá") == "Resposta local"
    sdk = instances[0]
    assert sdk.kwargs == {"engine_key": "ollama", "model": "sermax"}
    assert sdk.calls[0][1]["agent"] == "simple"
    assert sdk.calls[0][1]["tools"] == []
    assert sdk.calls[0][1]["context"] is False
    assert sdk.closed


def test_jarvis_rejects_empty_and_oversized_prompt():
    adapter = JarvisAdapter(sdk_factory=lambda **kwargs: FakeJarvis(**kwargs))
    for prompt in (" ", "x" * 4001):
        try:
            adapter.responder(prompt)
        except ValueError:
            pass
        else:
            raise AssertionError("prompt inválido foi aceito")
