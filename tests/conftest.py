"""Level 2 is offline. Archive checks are opt-in, with missing inputs failing closed."""
import socket
import pytest

@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('LIVE_NETWORK_FORBIDDEN_IN_TESTS')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)

@pytest.fixture(autouse=True)
def protect_repository_evidence(monkeypatch):
    """Tests may write only temporary paths, never this checkout's evidence."""
    import builtins
    import io
    import os
    import sqlite3
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    protected = {'DATASETS','FORWARD_RESEARCH','PAPER_RESEARCH','RESEARCH_MEMORY',
                 'PAPER_TRADING','PORTFOLIO_MEMORY','journal','DAILY_REPORTS',
                 'RESEARCH_REPORTS','DECISION_REGISTRY','CAPITAL_EFFICIENCY'}
    def is_protected(path):
        if isinstance(path, int): return False
        try:
            parts = Path(path).resolve().relative_to(root).parts
            return bool(parts) and parts[0] in protected
        except (ValueError, TypeError): return False
    def wrap_open(original):
        def guarded(file, mode='r', *args, **kwargs):
            if any(x in mode for x in 'wax+') and is_protected(file):
                raise AssertionError('TEST_WRITE_TO_REPOSITORY_EVIDENCE:'+str(file))
            return original(file, mode, *args, **kwargs)
        return guarded
    monkeypatch.setattr(builtins, 'open', wrap_open(builtins.open))
    monkeypatch.setattr(io, 'open', wrap_open(io.open))
    original_connect = sqlite3.connect
    def connect(database, *args, **kwargs):
        # Archive tests are allowed to inspect production state, never mutate it.
        if not str(database).startswith('file:') and is_protected(database):
            database = Path(database).resolve().as_uri()+'?mode=ro'
            kwargs['uri'] = True
        return original_connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', connect)
