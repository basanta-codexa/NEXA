"""Streaming contract tests for LLM clients and the agent engine."""

from __future__ import annotations

from types import SimpleNamespace as NS

from engine.agent_engine import AgentEngine
from llm.fake_client import FakeLLMClient
from llm.llm_client import LLMClient
from schemas import AgentConfig


def test_fake_client_streams_content_in_deltas():
    client = FakeLLMClient(model_name="fake", canned_response="Hello streaming world")

    chunks = list(client.chat_stream([{"role": "user", "content": "hi"}]))

    assert "".join(chunk["content"] for chunk in chunks) == "Hello streaming world"
    assert len(chunks) > 1


def test_default_chat_stream_falls_back_to_non_streaming_chat():
    class PlainClient(LLMClient):
        def generate(self, system_prompt, user_message):
            return "x"

        def chat(self, messages, tools=None):
            return {"content": "hi", "usage": {"input_tokens": 1, "output_tokens": 2}}

    events = list(PlainClient("stub").chat_stream([{"role": "user", "content": "x"}]))

    assert events == [
        {"content": "hi", "usage": {"input_tokens": 1, "output_tokens": 2}}
    ]


class _StreamingLLM:
    def chat_stream(self, messages, tools=None):
        yield {"content": "Hello "}
        yield {"content": "world"}
        yield {"usage": {"input_tokens": 4, "output_tokens": 2}}


def test_engine_run_stream_yields_text_then_final_result():
    engine = AgentEngine(
        config=AgentConfig(model_name="stub"),
        llm_client=_StreamingLLM(),
    )

    events = list(engine.run_stream("hi"))

    assert [event["content"] for event in events if event["type"] == "text"] == [
        "Hello ",
        "world",
    ]
    done = events[-1]
    assert done["type"] == "done"
    assert done["result"]["response"] == "Hello world"
    assert done["result"]["usage"] == {"input_tokens": 4, "output_tokens": 2}


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        self.closed = True


class _FakeOpenAIClient:
    def __init__(self, stream):
        self.chat = NS(completions=NS(create=lambda **kwargs: stream))


def test_openai_stream_accumulates_partial_tool_arguments():
    from llm.openai_client import OpenAIClient

    def tool_delta(index, *, call_id=None, name=None, arguments=None):
        return NS(
            index=index,
            id=call_id,
            function=NS(name=name, arguments=arguments),
        )

    stream = _FakeStream(
        [
            NS(choices=[NS(delta=NS(content="Checking "), finish_reason=None)]),
            NS(choices=[NS(delta=NS(content="order."), finish_reason=None)]),
            NS(
                choices=[
                    NS(
                        delta=NS(
                            content=None,
                            tool_calls=[
                                tool_delta(
                                    0,
                                    call_id="call_1",
                                    name="get_order_status",
                                    arguments='{"order_id": ',
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            ),
            NS(
                choices=[
                    NS(
                        delta=NS(
                            content=None,
                            tool_calls=[
                                tool_delta(0, arguments="101}")
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                usage=NS(prompt_tokens=10, completion_tokens=5),
            ),
        ]
    )

    client = OpenAIClient("gpt-test")
    client._client = _FakeOpenAIClient(stream)

    events = list(client.chat_stream([{"role": "user", "content": "status?"}]))

    assert "".join(e["content"] for e in events if "content" in e) == "Checking order."
    tool_event = next(e for e in events if "tool_calls" in e)
    assert tool_event["tool_calls"][0] == {
        "id": "call_1",
        "name": "get_order_status",
        "arguments": {"order_id": 101},
    }
    assert any(e.get("usage", {}).get("input_tokens") == 10 for e in events)
    assert stream.closed is True
