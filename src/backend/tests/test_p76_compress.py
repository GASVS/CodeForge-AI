"""P7.6 regression: _compress_history must work on real (non-empty) history.

Bug found during v1.0 gate verification (live UI chat): _estimate_tokens was
declared `async` but called synchronously inside sum(), so ANY non-empty
history raised TypeError ('int' + 'coroutine') and the stream died with
"Lost connection to the model while streaming".
"""
import main


def test_short_history_unchanged():
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    out, compressed = main._compress_history(history)
    assert out == history
    assert compressed is False


def test_long_history_compresses():
    # Each message ~2000 chars -> ~500 tokens; 30 msgs >> _MAX_HISTORY_TOKENS.
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i} " + ("x" * 2000)}
        for i in range(30)
    ]
    out, compressed = main._compress_history(history)
    assert compressed is True
    assert out[0]["role"] == "system"
    assert "compressed" in out[0]["content"].lower()
    # Kept the most recent turns verbatim.
    assert out[-1] == history[-1]
    assert len(out) <= main._KEEP_LAST_N_TURNS * 2 + 1


def test_empty_history_noop():
    out, compressed = main._compress_history([])
    assert out == []
    assert compressed is False
