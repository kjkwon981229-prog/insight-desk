# Failure policy

A tool/provider exception or ambiguous output must never erase an already-established event. Helper failures return no additional signal and allow existing deterministic fail-safe policy to continue; they do not trigger global abort or paid fallback.
