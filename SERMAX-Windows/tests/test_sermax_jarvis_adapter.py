import unittest
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


class TestJarvisAdapter(unittest.TestCase):
    def test_uses_orchestrator_with_explicit_safe_tools_and_without_memory(self):
        instances = []

        def factory(**kwargs):
            item = FakeJarvis(**kwargs)
            instances.append(item)
            return item

        adapter = JarvisAdapter(model="sermax", sdk_factory=factory)
        self.assertEqual(adapter.responder("Olá"), "Resposta local")
        sdk = instances[0]
        self.assertEqual(sdk.kwargs, {"engine_key": "ollama", "model": "sermax"})
        self.assertEqual(sdk.calls[0][1]["agent"], "orchestrator")
        self.assertEqual(sdk.calls[0][1]["tools"], ["calculator", "think"])
        self.assertFalse(sdk.calls[0][1]["context"])
        self.assertTrue(sdk.closed)

    def test_simple_agent_receives_no_tools(self):
        instances = []
        def factory(**kwargs):
            item = FakeJarvis(**kwargs)
            instances.append(item)
            return item
        adapter = JarvisAdapter(agent="simple", sdk_factory=factory)
        self.assertEqual(adapter.responder("Olá"), "Resposta local")
        self.assertEqual(instances[0].calls[0][1]["agent"], "simple")
        self.assertEqual(instances[0].calls[0][1]["tools"], [])

    def test_rejects_unknown_agent(self):
        with self.assertRaises(ValueError):
            JarvisAdapter(agent="native_react")

    def test_rejects_empty_and_oversized_prompt(self):
        adapter = JarvisAdapter(sdk_factory=lambda **kwargs: FakeJarvis(**kwargs))
        for prompt in (" ", "x" * 4001):
            with self.assertRaises(ValueError):
                adapter.responder(prompt)


if __name__ == "__main__":
    unittest.main()
