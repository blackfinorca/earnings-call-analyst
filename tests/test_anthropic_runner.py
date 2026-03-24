import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "backend" / "research_app" / "anthropic_runner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("anthropic_runner", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, stop_reason, text):
        self.stop_reason = stop_reason
        self.content = [_FakeBlock(text)]
        self.usage = None


class _FakeStream:
    def __init__(self, response):
        self.response = response
        self.text_stream = [response.content[0].text]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self):
        return self.response


class _FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self.responses.pop(0))


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


class AnthropicRunnerTests(unittest.TestCase):
    def test_run_message_loop_resumes_after_pause_turn(self):
        module = load_module()
        client = _FakeClient(
            [
                _FakeResponse("pause_turn", "thinking"),
                _FakeResponse("end_turn", "done"),
            ]
        )

        response = module.run_message_loop(
            client=client,
            model="model",
            system_prompt="system",
            user_message="user",
            max_tokens=100,
            temperature=0.0,
            tools=[{"name": "web_search"}],
            max_pause_turns=2,
            max_retries=1,
            base_delay=0.0,
            max_delay=0.0,
        )

        self.assertEqual(response.stop_reason, "end_turn")
        self.assertEqual(len(client.messages.calls), 2)
        resumed_messages = client.messages.calls[1]["messages"]
        self.assertEqual(resumed_messages[-1]["role"], "assistant")
        self.assertEqual(module.extract_text_response(response), "done")


if __name__ == "__main__":
    unittest.main()
