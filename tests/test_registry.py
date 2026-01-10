"""Tests for Registry."""

import pytest
import anyio
from src.fauxtp import register, unregister, whereis, registered, PID
from src.fauxtp.primitives.mailbox import Mailbox
import uuid


class TestRegistry:
    """Test Registry functionality."""
    
    def setup_method(self):
        """Clear registry before each test."""
        from src.fauxtp.registry.local import _global_registry
        _global_registry._names.clear()
    
    def test_register_process(self):
        """Test registering a process."""
        mailbox = Mailbox()
        pid = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        
        result = register("test_process", pid)
        assert result is True
        
        # Try to register same name again
        result = register("test_process", pid)
        assert result is False
    
    def test_whereis(self):
        """Test looking up a process."""
        mailbox = Mailbox()
        pid = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        
        # Not registered yet
        assert whereis("test_process") is None
        
        # Register and look up
        register("test_process", pid)
        found_pid = whereis("test_process")
        assert found_pid == pid
    
    def test_unregister(self):
        """Test unregistering a process."""
        mailbox = Mailbox()
        pid = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        
        register("test_process", pid)
        assert whereis("test_process") == pid
        
        result = unregister("test_process")
        assert result is True
        assert whereis("test_process") is None
        
        # Try to unregister again
        result = unregister("test_process")
        assert result is False
    
    def test_registered(self):
        """Test listing all registered names."""
        mailbox = Mailbox()
        pid1 = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        pid2 = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        
        register("process1", pid1)
        register("process2", pid2)
        
        names = registered()
        assert "process1" in names
        assert "process2" in names
        assert len(names) == 2
    
    def test_multiple_processes(self):
        """Test registry with multiple processes."""
        mailbox = Mailbox()
        pids = [PID(_id=uuid.uuid4(), _mailbox=mailbox) for _ in range(5)]
        
        # Register all
        for i, pid in enumerate(pids):
            assert register(f"process_{i}", pid) is True
        
        # Look them all up
        for i, pid in enumerate(pids):
            assert whereis(f"process_{i}") == pid
        
        # Unregister one
        assert unregister("process_2") is True
        assert whereis("process_2") is None
        
        # Others should still be there
        assert whereis("process_0") == pids[0]
        assert whereis("process_4") == pids[4]