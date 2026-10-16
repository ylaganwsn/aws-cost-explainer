import pytest

from cost_explainer.handler import load_api_key


class FakeSsm:
    """Stands in for the boto3 SSM client so tests never touch AWS."""

    def __init__(self, value="the-key", fail=False):
        self.value = value
        self.fail = fail
        self.calls = []

    def get_parameter(self, Name, WithDecryption):
        self.calls.append((Name, WithDecryption))
        if self.fail:
            raise RuntimeError("boom")
        return {"Parameter": {"Value": self.value}}


def test_reads_key_from_ssm_with_decryption():
    env = {"GEMINI_KEY_PARAMETER": "/app/key"}
    ssm = FakeSsm()
    load_api_key(env, ssm)
    assert env["GEMINI_API_KEY"] == "the-key"
    assert ssm.calls == [("/app/key", True)]


@pytest.mark.parametrize(
    "env",
    [
        {"GEMINI_API_KEY": "already-set", "GEMINI_KEY_PARAMETER": "/app/key"},
        {"USE_LLM": "false", "GEMINI_KEY_PARAMETER": "/app/key"},
        {},
    ],
)
def test_does_not_call_ssm_when_not_needed(env):
    ssm = FakeSsm()
    load_api_key(env, ssm)
    assert ssm.calls == []


def test_ssm_failure_leaves_no_key_and_does_not_raise():
    env = {"GEMINI_KEY_PARAMETER": "/app/key"}
    load_api_key(env, FakeSsm(fail=True))
    assert "GEMINI_API_KEY" not in env