import importlib.util, os, pytest
HERE=os.path.dirname(__file__); p=os.path.join(HERE,"..","scripts","pi_event_adapter.py")
s=importlib.util.spec_from_file_location("adapter",p); adapter=importlib.util.module_from_spec(s); s.loader.exec_module(adapter)

def test_measures_only_allowed_pi_events_and_tokens():
    got=adapter.measured_events(['{"type":"tool_execution_start","toolName":"read"}','{"type":"message_end","message":{"usage":{"input":4,"output":2}}}','{"type":"turn_end"}'], {"turns":1,"tools":1,"subprocesses":1,"input_tokens":5,"output_tokens":3})
    assert got == {"turns":1,"tools":1,"subprocesses":1,"input_tokens":4,"output_tokens":2}

@pytest.mark.parametrize("line", ['{"type":"tool_execution_start","toolName":"bash"}', '[]', '{'])
def test_rejects_disallowed_or_invalid_events(line):
    with pytest.raises(ValueError): adapter.measured_events([line], {"turns":1,"tools":1,"subprocesses":1,"input_tokens":5,"output_tokens":3})
