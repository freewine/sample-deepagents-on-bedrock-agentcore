from harness.spec import AgentSpec
from tools import LOCAL_TOOLS


def test_local_tools_registry():
    assert LOCAL_TOOLS["add_numbers"].invoke({"a": 2, "b": 3}) == 5


def test_spec_defaults():
    spec = AgentSpec(name="x", system_prompt="p")
    assert spec.tools == ()
    assert spec.skills == ()
