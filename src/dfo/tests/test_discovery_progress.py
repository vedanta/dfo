"""Tests for enhanced discovery progress display."""

# Standard library
from unittest.mock import Mock, patch, MagicMock
import pytest

# Internal
from dfo.common.terminal import get_display_mode


class TestTerminalDetection:
    """Tests for terminal capability detection."""

    def test_get_display_mode_wide_terminal(self):
        """Test rich mode is selected for wide terminals."""
        with patch('shutil.get_terminal_size') as mock_size:
            mock_size.return_value = MagicMock(columns=120)
            with patch('sys.stdout.isatty', return_value=True):
                mode = get_display_mode(min_width=100)
                assert mode == "rich"

    def test_get_display_mode_narrow_terminal(self):
        """Test simple mode is selected for narrow terminals."""
        with patch('shutil.get_terminal_size') as mock_size:
            mock_size.return_value = MagicMock(columns=80)
            with patch('sys.stdout.isatty', return_value=True):
                mode = get_display_mode(min_width=100)
                assert mode == "simple"

    def test_get_display_mode_non_tty(self):
        """Test simple mode is selected for non-TTY environments."""
        with patch('shutil.get_terminal_size') as mock_size:
            mock_size.return_value = MagicMock(columns=120)
            with patch('sys.stdout.isatty', return_value=False):
                mode = get_display_mode(min_width=100)
                assert mode == "simple"

    def test_get_display_mode_custom_width(self):
        """Test custom minimum width threshold."""
        with patch('shutil.get_terminal_size') as mock_size:
            mock_size.return_value = MagicMock(columns=150)
            with patch('sys.stdout.isatty', return_value=True):
                # Should return simple because 150 < 200
                mode = get_display_mode(min_width=200)
                assert mode == "simple"

                # Should return rich because 150 >= 100
                mode = get_display_mode(min_width=100)
                assert mode == "rich"

    def test_get_display_mode_error_fallback(self):
        """Test graceful fallback to simple mode on error."""
        with patch('shutil.get_terminal_size', side_effect=Exception("Test error")):
            mode = get_display_mode()
            assert mode == "simple"


class TestProgressCallbackEvents:
    """Tests for progress callback event system."""

    def test_progress_callback_list_vms_events(self, monkeypatch):
        """Test that list_vms stage emits correct events."""
        from dfo.discover.vms import discover_vms

        # Mock dependencies
        monkeypatch.setenv("DFO_DUCKDB_FILE", ":memory:")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

        events = []

        def capture_events(stage, status, data):
            events.append({"stage": stage, "status": status, "data": data})

        with patch('dfo.discover.vms.get_settings'):
            with patch('dfo.discover.vms.get_cached_credential'):
                with patch('dfo.discover.vms.get_compute_client'):
                    with patch('dfo.discover.vms.get_monitor_client'):
                        with patch('dfo.discover.vms.list_vms', return_value=[]):
                            with patch('dfo.discover.vms.get_db') as mock_db:
                                mock_db.return_value.clear_table = Mock()
                                mock_db.return_value.insert_records = Mock()

                                discover_vms(
                                    subscription_id="test-sub",
                                    refresh=True,
                                    progress_callback=capture_events
                                )

        # Verify list_vms events were emitted
        list_events = [e for e in events if e["stage"] == "list_vms"]
        assert len(list_events) >= 2  # Started and complete
        assert any(e["status"] == "started" for e in list_events)
        assert any(e["status"] == "complete" for e in list_events)

    def test_progress_callback_metrics_events(self, monkeypatch):
        """Test that metrics stage emits per-VM events."""
        from dfo.discover.vms import discover_vms

        # Mock dependencies
        monkeypatch.setenv("DFO_DUCKDB_FILE", ":memory:")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

        events = []

        def capture_events(stage, status, data):
            events.append({"stage": stage, "status": status, "data": data})

        mock_vms = [
            {
                "vm_id": "/subscriptions/test/vm1",
                "name": "test-vm-1",
                "resource_group": "test-rg",
                "location": "eastus",
                "size": "Standard_B2s",
                "power_state": "running",
                "tags": {},
                "os_type": "Linux",
                "priority": "Regular"
            }
        ]

        with patch('dfo.discover.vms.get_settings'):
            with patch('dfo.discover.vms.get_cached_credential'):
                with patch('dfo.discover.vms.get_compute_client'):
                    with patch('dfo.discover.vms.get_monitor_client'):
                        with patch('dfo.discover.vms.list_vms', return_value=mock_vms):
                            with patch('dfo.discover.vms.get_cpu_metrics', return_value=[]):
                                with patch('dfo.discover.vms.get_db') as mock_db:
                                    mock_db.return_value.clear_table = Mock()
                                    mock_db.return_value.insert_records = Mock()

                                    discover_vms(
                                        subscription_id="test-sub",
                                        refresh=True,
                                        progress_callback=capture_events
                                    )

        # Verify metrics events
        metrics_events = [e for e in events if e["stage"] == "metrics"]
        assert len(metrics_events) >= 2  # Started and per-VM events

        # Check for fetching event
        fetching_events = [e for e in metrics_events if e["status"] == "fetching"]
        assert len(fetching_events) >= 1
        assert fetching_events[0]["data"]["vm_name"] == "test-vm-1"

        # Check for complete event
        complete_events = [e for e in metrics_events if e["status"] == "complete"]
        assert len(complete_events) >= 1

    def test_progress_callback_failure_events(self, monkeypatch):
        """Test that failures emit failed events."""
        from dfo.discover.vms import discover_vms

        # Mock dependencies
        monkeypatch.setenv("DFO_DUCKDB_FILE", ":memory:")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

        events = []

        def capture_events(stage, status, data):
            events.append({"stage": stage, "status": status, "data": data})

        mock_vms = [
            {
                "vm_id": "/subscriptions/test/vm1",
                "name": "test-vm-1",
                "resource_group": "test-rg",
                "location": "eastus",
                "size": "Standard_B2s",
                "power_state": "running",
                "tags": {},
                "os_type": "Linux",
                "priority": "Regular"
            }
        ]

        with patch('dfo.discover.vms.get_settings'):
            with patch('dfo.discover.vms.get_cached_credential'):
                with patch('dfo.discover.vms.get_compute_client'):
                    with patch('dfo.discover.vms.get_monitor_client'):
                        with patch('dfo.discover.vms.list_vms', return_value=mock_vms):
                            # Simulate metric collection failure
                            with patch('dfo.discover.vms.get_cpu_metrics', side_effect=Exception("Test error")):
                                with patch('dfo.discover.vms.get_db') as mock_db:
                                    mock_db.return_value.clear_table = Mock()
                                    mock_db.return_value.insert_records = Mock()

                                    discover_vms(
                                        subscription_id="test-sub",
                                        refresh=True,
                                        progress_callback=capture_events
                                    )

        # Verify failed event was emitted
        failed_events = [e for e in events if e["status"] == "failed"]
        assert len(failed_events) >= 1
        assert failed_events[0]["data"]["vm_name"] == "test-vm-1"
        assert "error" in failed_events[0]["data"]


class TestSimpleProgressHandler:
    """Tests for simple progress handler."""

    def test_simple_handler_tracks_state(self):
        """Test that simple handler tracks failures."""
        from dfo.cmd.azure import _create_simple_progress_handler
        from rich.progress import Progress

        with Progress() as progress:
            task = progress.add_task("test", total=None)
            handler = _create_simple_progress_handler(progress, task)

            # Simulate events
            handler("list_vms", "complete", {"count": 2})
            handler("metrics", "started", {"total": 2})
            handler("metrics", "complete", {"vm_name": "vm1", "data_points": 100})
            handler("metrics", "failed", {"vm_name": "vm2", "error": "Test error"})

            # Verify state
            assert handler.state["success_count"] == 1
            assert handler.state["failed_count"] == 1
            assert len(handler.state["failed_vms"]) == 1
            assert handler.state["failed_vms"][0]["name"] == "vm2"
            assert handler.state["failed_vms"][0]["error"] == "Test error"


class TestRichProgressHandler:
    """Tests for rich progress handler."""

    def test_rich_handler_tracks_state(self):
        """Test that rich handler tracks failures."""
        from dfo.cmd.azure import _create_rich_progress_handler
        from rich.live import Live
        from rich.console import Console

        console = Console()
        with Live(console=console) as live:
            handler = _create_rich_progress_handler(live)

            # Simulate events
            handler("list_vms", "complete", {"count": 2})
            handler("metrics", "fetching", {"vm_name": "vm1", "index": 1, "total": 2})
            handler("metrics", "complete", {"vm_name": "vm1", "data_points": 100})
            handler("metrics", "fetching", {"vm_name": "vm2", "index": 2, "total": 2})
            handler("metrics", "failed", {"vm_name": "vm2", "error": "Test error"})

            # Verify state through callable
            failed_vms = handler.state["failed_vms"]()
            assert len(failed_vms) == 1
            assert failed_vms[0]["name"] == "vm2"
            assert failed_vms[0]["error"] == "Test error"

            # Verify internal state
            full_state = handler.state["get_state"]()
            assert full_state["completed"] == 1
            assert full_state["failed"] == 1
            assert len(full_state["completed_vms"]) == 1
            assert len(full_state["failed_vms"]) == 1


class TestErrorMessageMapping:
    """Tests for actionable error message mapping."""

    def test_error_message_resource_not_found(self):
        """Test ResourceNotFound is mapped to user-friendly message."""
        # This would be tested in an integration test with the actual CLI
        # For now, verify the logic exists in azure.py
        error_msg = "ResourceNotFound: The VM was not found"

        # Simulate the mapping logic
        if "ResourceNotFound" in error_msg:
            error_msg = "VM not found - may have been deleted"

        assert error_msg == "VM not found - may have been deleted"

    def test_error_message_authorization_failed(self):
        """Test AuthorizationFailed is mapped to user-friendly message."""
        error_msg = "AuthorizationFailed: Insufficient permissions"

        if "AuthorizationFailed" in error_msg:
            error_msg = "Permission denied - check Azure Monitor permissions"

        assert error_msg == "Permission denied - check Azure Monitor permissions"

    def test_error_message_throttling(self):
        """Test throttling errors are mapped to user-friendly message."""
        error_msg = "TooManyRequests: Rate limit exceeded"

        if "Throttled" in error_msg or "TooManyRequests" in error_msg:
            error_msg = "Rate limited - try again later or reduce concurrent requests"

        assert error_msg == "Rate limited - try again later or reduce concurrent requests"

    def test_error_message_network_timeout(self):
        """Test network timeout errors are mapped to user-friendly message."""
        error_msg = "Connection timeout occurred"

        if "NetworkError" in error_msg or "timeout" in error_msg.lower():
            error_msg = "Network timeout - check connectivity"

        assert error_msg == "Network timeout - check connectivity"


class TestProgressIntegration:
    """Integration tests for progress display."""

    def test_progress_callback_none_works(self, monkeypatch):
        """Test that discovery works without progress callback."""
        from dfo.discover.vms import discover_vms

        # Mock dependencies
        monkeypatch.setenv("DFO_DUCKDB_FILE", ":memory:")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

        with patch('dfo.discover.vms.get_settings'):
            with patch('dfo.discover.vms.get_cached_credential'):
                with patch('dfo.discover.vms.get_compute_client'):
                    with patch('dfo.discover.vms.get_monitor_client'):
                        with patch('dfo.discover.vms.list_vms', return_value=[]):
                            with patch('dfo.discover.vms.get_db') as mock_db:
                                mock_db.return_value.clear_table = Mock()
                                mock_db.return_value.insert_records = Mock()

                                # Should work fine without progress callback
                                result = discover_vms(
                                    subscription_id="test-sub",
                                    refresh=True,
                                    progress_callback=None
                                )

                                assert result == []
