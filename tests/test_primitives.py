"""Tests for primitive types (PID, Ref, Mailbox, Pattern matching)."""

import pytest
import anyio
from src.fauxtp.primitives.pid import PID, Ref
from src.fauxtp.primitives.mailbox import Mailbox, ReceiveTimeout
from src.fauxtp.primitives.pattern import ANY, IGNORE, match_pattern


pytestmark = pytest.mark.anyio


class TestPID:
    """Test PID functionality."""
    
    def test_pid_creation(self):
        """Test PID can be created."""
        mailbox = Mailbox()
        import uuid
        pid = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        assert pid is not None
        assert pid._mailbox is mailbox
    
    def test_pid_hashable(self):
        """Test PIDs can be used as dict keys."""
        mailbox = Mailbox()
        import uuid
        pid1 = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        pid2 = PID(_id=uuid.uuid4(), _mailbox=mailbox)
        
        d = {pid1: "value1", pid2: "value2"}
        assert d[pid1] == "value1"
        assert d[pid2] == "value2"
    
    def test_pid_equality(self):
        """Test PID equality based on UUID."""
        mailbox = Mailbox()
        import uuid
        id1 = uuid.uuid4()
        pid1 = PID(_id=id1, _mailbox=mailbox)
        pid2 = PID(_id=id1, _mailbox=mailbox)
        
        assert pid1 == pid2


class TestRef:
    """Test Ref functionality."""
    
    def test_ref_creation(self):
        """Test Ref generates unique IDs."""
        ref1 = Ref()
        ref2 = Ref()
        assert ref1 != ref2
        assert ref1._id != ref2._id
    
    def test_ref_hashable(self):
        """Test Refs can be used as dict keys."""
        ref1 = Ref()
        ref2 = Ref()
        d = {ref1: "value1", ref2: "value2"}
        assert d[ref1] == "value1"


class TestMailbox:
    """Test Mailbox functionality."""
    
    async def test_mailbox_put_and_receive(self):
        """Test basic put and receive."""
        mailbox = Mailbox()
        
        await mailbox.put("test_message")
        
        result = await mailbox.receive(
            (ANY, lambda msg: msg),
            timeout=1.0
        )
        
        assert result == "test_message"
    
    async def test_mailbox_pattern_matching(self):
        """Test pattern-matched receive."""
        mailbox = Mailbox()
        
        await mailbox.put(("add", 5))
        await mailbox.put(("multiply", 3))
        
        # Match first message
        result = await mailbox.receive(
            (("add", ANY), lambda n: ("add", n)),
            timeout=1.0
        )
        assert result == ("add", 5)
        
        # Match second message
        result = await mailbox.receive(
            (("multiply", ANY), lambda n: ("multiply", n)),
            timeout=1.0
        )
        assert result == ("multiply", 3)
    
    async def test_mailbox_timeout(self):
        """Test receive timeout."""
        mailbox = Mailbox()
        
        with pytest.raises(ReceiveTimeout):
            await mailbox.receive(
                ((ANY,), lambda msg: msg),
                timeout=0.1
            )
    
    async def test_mailbox_selective_receive(self):
        """Test selective receive (skip non-matching messages)."""
        mailbox = Mailbox()
        
        await mailbox.put(("type_a", 1))
        await mailbox.put(("type_b", 2))
        await mailbox.put(("type_a", 3))
        
        # Should find first type_a message
        result = await mailbox.receive(
            (("type_a", ANY), lambda n: n),
            timeout=1.0
        )
        assert result == 1
        
        # type_b should still be in mailbox
        result = await mailbox.receive(
            (("type_b", ANY), lambda n: n),
            timeout=1.0
        )
        assert result == 2


class TestPatternMatching:
    """Test pattern matching functionality."""
    
    def test_match_any(self):
        """Test ANY pattern matches everything."""
        assert match_pattern("hello", ANY) == ("hello",)
        assert match_pattern(123, ANY) == (123,)
        assert match_pattern(None, ANY) == (None,)
    
    def test_match_ignore(self):
        """Test IGNORE pattern matches but doesn't extract."""
        assert match_pattern("hello", IGNORE) == ()
        assert match_pattern(123, IGNORE) == ()
    
    def test_match_type(self):
        """Test type matching."""
        assert match_pattern("hello", str) == ("hello",)
        assert match_pattern(123, int) == (123,)
        assert match_pattern("hello", int) is None
    
    def test_match_literal(self):
        """Test literal value matching."""
        assert match_pattern("ping", "ping") == ()
        assert match_pattern("ping", "pong") is None
        assert match_pattern(42, 42) == ()
    
    def test_match_tuple_structure(self):
        """Test tuple structure matching."""
        # Simple tuple
        result = match_pattern(("ping", 123), ("ping", ANY))
        assert result == (123,)
        
        # Nested tuple
        result = match_pattern(
            ("data", "key", {"value": 1}),
            ("data", str, dict)
        )
        assert result == ("key", {"value": 1})
        
        # Length mismatch
        assert match_pattern(("a", "b"), ("a", "b", "c")) is None
    
    def test_match_tuple_with_ignore(self):
        """Test tuple matching with IGNORE."""
        result = match_pattern(
            ("command", "arg1", "arg2"),
            ("command", IGNORE, ANY)
        )
        assert result == ("arg2",)
    
    def test_match_complex_pattern(self):
        """Test complex nested patterns."""
        message = ("request", ("get", "user", 123), "metadata")
        pattern = ("request", ("get", str, int), ANY)
        
        result = match_pattern(message, pattern)
        assert result == ("user", 123, "metadata")
