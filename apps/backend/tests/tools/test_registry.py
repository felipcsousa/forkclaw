import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.tools.registry import EditFileTool
from app.tools.base import ToolExecutionContext, ToolResult

def test_edit_file_tool_replace_single():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    file_path = workspace_root / "test.txt"
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    # Needs to return a Mock object for resolve_path that has a read_text method
    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.read_text.return_value = "hello world hello world"
    mock_target.relative_to.return_value = "test.txt"

    context.resolve_path = MagicMock(return_value=mock_target)

    tool = EditFileTool()

    # Execute
    result = tool.execute(
        context=context,
        arguments={
            "path": "test.txt",
            "find": "world",
            "replace": "friend",
            "replace_all": False,
        }
    )

    # Verify
    mock_target.write_text.assert_called_once_with("hello friend hello world", encoding="utf-8")
    assert result.output_data == {"replaced_all": False}


def test_edit_file_tool_replace_all():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    file_path = workspace_root / "test.txt"
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    # Needs to return a Mock object for resolve_path that has a read_text method
    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.read_text.return_value = "hello world hello world"
    mock_target.relative_to.return_value = "test.txt"

    context.resolve_path = MagicMock(return_value=mock_target)

    tool = EditFileTool()

    # Execute
    result = tool.execute(
        context=context,
        arguments={
            "path": "test.txt",
            "find": "world",
            "replace": "friend",
            "replace_all": True,
        }
    )

    # Verify
    mock_target.write_text.assert_called_once_with("hello friend hello friend", encoding="utf-8")
    assert result.output_data == {"replaced_all": True}


def test_edit_file_tool_file_not_found():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    file_path = workspace_root / "test.txt"
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    mock_target = MagicMock()
    mock_target.exists.return_value = False
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = EditFileTool()

    # Execute and Verify
    with pytest.raises(FileNotFoundError, match="Target file does not exist"):
        tool.execute(
            context=context,
            arguments={
                "path": "test.txt",
                "find": "world",
                "replace": "friend",
                "replace_all": False,
            }
        )

def test_edit_file_tool_text_not_found():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    file_path = workspace_root / "test.txt"
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.read_text.return_value = "hello universe"
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = EditFileTool()

    # Execute and Verify
    with pytest.raises(ValueError, match="Search text was not found in the file"):
        tool.execute(
            context=context,
            arguments={
                "path": "test.txt",
                "find": "world",
                "replace": "friend",
                "replace_all": False,
            }
        )


from app.tools.registry import ListFilesTool

def test_list_directory_tool():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    # Mock entries
    dir_entry = MagicMock()
    dir_entry.name = "a_dir"
    dir_entry.is_dir.return_value = True
    dir_entry.relative_to.return_value = "a_dir"

    file_entry = MagicMock()
    file_entry.name = "b_file.txt"
    file_entry.is_dir.return_value = False
    file_entry.relative_to.return_value = "b_file.txt"

    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.is_dir.return_value = True
    mock_target.iterdir.return_value = [dir_entry, file_entry]

    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ListFilesTool()

    # Execute
    result = tool.execute(
        context=context,
        arguments={
            "path": ".",
        }
    )

    # Verify
    assert result.output_data == {"count": 2}
    assert "dir: a_dir" in result.output_text
    assert "file: b_file.txt" in result.output_text

def test_list_directory_tool_not_found():
    context = MagicMock(spec=ToolExecutionContext)
    mock_target = MagicMock()
    mock_target.exists.return_value = False
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ListFilesTool()
    with pytest.raises(FileNotFoundError, match="Target directory does not exist"):
        tool.execute(context=context, arguments={"path": "."})

def test_list_directory_tool_not_a_dir():
    context = MagicMock(spec=ToolExecutionContext)
    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.is_dir.return_value = False
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ListFilesTool()
    with pytest.raises(NotADirectoryError, match="Target path is not a directory"):
        tool.execute(context=context, arguments={"path": "."})


from app.tools.registry import ReadFileTool

def test_read_file_tool():
    # Setup
    workspace_root = Path("/tmp/test_workspace")
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.is_file.return_value = True
    mock_target.read_text.return_value = "file contents here"

    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ReadFileTool()

    # Execute
    result = tool.execute(
        context=context,
        arguments={
            "path": "test.txt",
        }
    )

    # Verify
    assert result.output_text == "file contents here"
    assert result.output_data == {"path": str(mock_target.relative_to.return_value)}

def test_read_file_tool_not_found():
    context = MagicMock(spec=ToolExecutionContext)
    mock_target = MagicMock()
    mock_target.exists.return_value = False
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ReadFileTool()
    with pytest.raises(FileNotFoundError, match="Target file does not exist"):
        tool.execute(context=context, arguments={"path": "test.txt"})

def test_read_file_tool_not_a_file():
    context = MagicMock(spec=ToolExecutionContext)
    mock_target = MagicMock()
    mock_target.exists.return_value = True
    mock_target.is_file.return_value = False
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = ReadFileTool()
    with pytest.raises(IsADirectoryError, match="Target path is not a file"):
        tool.execute(context=context, arguments={"path": "test.txt"})

from app.tools.registry import WriteFileTool

def test_write_file_tool():
    workspace_root = Path("/tmp/test_workspace")
    context = MagicMock(spec=ToolExecutionContext)
    context.workspace_root = workspace_root

    mock_target = MagicMock()
    mock_target.relative_to.return_value = "test.txt"
    context.resolve_path = MagicMock(return_value=mock_target)

    tool = WriteFileTool()

    result = tool.execute(
        context=context,
        arguments={
            "path": "test.txt",
            "content": "new file content"
        }
    )

    mock_target.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_target.write_text.assert_called_once_with("new file content", encoding="utf-8")
    assert result.output_data == {"bytes": len("new file content".encode("utf-8"))}
    assert "Wrote" in result.output_text


from app.tools.registry import ClipboardReadTool, ClipboardWriteTool
from unittest.mock import patch

def test_clipboard_read_mac():
    with patch("platform.system", return_value="Darwin"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "copied text"

        tool = ClipboardReadTool()
        result = tool.execute(context=MagicMock(), arguments={})

        mock_run.assert_called_once_with(
            ["pbpaste"], check=True, capture_output=True, text=True
        )
        assert result.output_text == "copied text"
        assert result.output_data is None

def test_clipboard_read_windows():
    with patch("platform.system", return_value="Windows"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "windows text"

        tool = ClipboardReadTool()
        result = tool.execute(context=MagicMock(), arguments={})

        mock_run.assert_called_once_with(
            ["powershell", "-Command", "Get-Clipboard"],
            check=True, capture_output=True, text=True
        )
        assert result.output_text == "windows text"

def test_clipboard_read_unsupported():
    with patch("platform.system", return_value="Linux"):
        tool = ClipboardReadTool()
        with pytest.raises(NotImplementedError, match="Clipboard read is only implemented for macOS and Windows"):
            tool.execute(context=MagicMock(), arguments={})

def test_clipboard_write_mac():
    with patch("platform.system", return_value="Darwin"), \
         patch("subprocess.run") as mock_run:

        tool = ClipboardWriteTool()
        result = tool.execute(context=MagicMock(), arguments={"content": "new text"})

        mock_run.assert_called_once_with(
            ["pbcopy"], input="new text", check=True, text=True
        )
        assert "Wrote" in result.output_text

def test_clipboard_write_windows():
    with patch("platform.system", return_value="Windows"), \
         patch("subprocess.run") as mock_run:

        tool = ClipboardWriteTool()
        result = tool.execute(context=MagicMock(), arguments={"content": "win text"})

        mock_run.assert_called_once_with(
            ["powershell", "-Command", "Set-Clipboard"],
            input="win text", check=True, text=True
        )
        assert "Wrote" in result.output_text

def test_clipboard_write_unsupported():
    with patch("platform.system", return_value="Linux"):
        tool = ClipboardWriteTool()
        with pytest.raises(NotImplementedError, match="Clipboard write is only implemented for macOS and Windows"):
            tool.execute(context=MagicMock(), arguments={"content": "text"})


from app.tools.registry import WebSearchTool

def test_web_search_cached():
    context = MagicMock(spec=ToolExecutionContext)
    context.cache_store = MagicMock()
    context.cache_store.get_json.return_value = {
        "provider": "brave",
        "query": "test query",
        "results": [{"title": "Test Title", "url": "https://test.com", "snippet": "Test snippet"}],
    }

    tool = WebSearchTool()
    result = tool.execute(
        context=context,
        arguments={"query": "test query"}
    )

    assert result.output_data["cached"] is True
    assert result.output_data["provider"] == "brave"
    assert "Test Title" in result.output_text
    context.cache_store.get_json.assert_called_once()

@patch("app.tools.registry.BraveWebSearchProvider")
def test_web_search_uncached(mock_provider_class):
    mock_provider = MagicMock()
    mock_provider_class.return_value = mock_provider

    mock_response = MagicMock()
    mock_response.provider = "brave"
    mock_response.query = "test query"

    mock_result = MagicMock()
    mock_result.title = "Uncached Title"
    mock_result.url = "https://uncached.com"
    mock_result.snippet = "Uncached snippet"
    mock_response.results = [mock_result]

    mock_provider.search.return_value = mock_response

    context = MagicMock(spec=ToolExecutionContext)
    context.cache_store = MagicMock()
    context.cache_store.get_json.return_value = None
    context.runtime_settings = {"tool_timeout_seconds": "15.0", "web_search_cache_ttl_seconds": "900"}

    tool = WebSearchTool()
    result = tool.execute(
        context=context,
        arguments={"query": "test query"}
    )

    assert result.output_data["cached"] is False
    assert result.output_data["provider"] == "brave"
    assert "Uncached Title" in result.output_text

    context.cache_store.get_json.assert_called_once()
    context.cache_store.set_json.assert_called_once()
    mock_provider.search.assert_called_once_with("test query", 5)


from app.tools.registry import WebFetchTool

def test_web_fetch_cached():
    context = MagicMock(spec=ToolExecutionContext)
    context.cache_store = MagicMock()
    context.runtime_settings = {"web_fetch_default_max_chars": "8000"}
    context.cache_store.get_json.return_value = {
        "url": "https://test.com",
        "final_url": "https://test.com",
        "extract_mode": "text",
        "content": "Test content",
    }

    tool = WebFetchTool()
    result = tool.execute(
        context=context,
        arguments={"url": "https://test.com", "extract_mode": "text"}
    )

    assert result.output_data["cached"] is True
    assert result.output_text == "Test content"
    context.cache_store.get_json.assert_called_once()

@patch("app.tools.registry.fetch_web_document")
def test_web_fetch_uncached(mock_fetch):
    mock_fetch.return_value = {
        "url": "https://test.com",
        "final_url": "https://test.com",
        "extract_mode": "text",
        "content": "Fetched content",
    }

    context = MagicMock(spec=ToolExecutionContext)
    context.cache_store = MagicMock()
    context.cache_store.get_json.return_value = None
    context.runtime_settings = {
        "web_fetch_default_max_chars": "8000",
        "tool_timeout_seconds": "15.0",
        "web_fetch_max_response_bytes": "524288",
        "web_fetch_cache_ttl_seconds": "900",
    }

    tool = WebFetchTool()
    result = tool.execute(
        context=context,
        arguments={"url": "https://test.com"}
    )

    assert result.output_data["cached"] is False
    assert result.output_text == "Fetched content"

    mock_fetch.assert_called_once_with(
        url="https://test.com",
        extract_mode="markdown",
        max_chars=8000,
        timeout_seconds=15.0,
        max_response_bytes=524288,
    )
    context.cache_store.get_json.assert_called_once()
    context.cache_store.set_json.assert_called_once()


from app.tools.registry import SpawnSubagentTool, ListSubagentsTool, GetSubagentTool, CancelSubagentTool

def test_spawn_subagent_tool():
    tool = SpawnSubagentTool()
    with pytest.raises(RuntimeError, match="spawn_subagent is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

def test_list_subagents_tool():
    tool = ListSubagentsTool()
    with pytest.raises(RuntimeError, match="list_subagents is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

def test_get_subagent_tool():
    tool = GetSubagentTool()
    with pytest.raises(RuntimeError, match="get_subagent is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

def test_cancel_subagent_tool():
    tool = CancelSubagentTool()
    with pytest.raises(RuntimeError, match="cancel_subagent is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

from app.tools.registry import AcpEnableTool, AcpDisableTool, AcpStatusTool

def test_acp_enable_tool():
    tool = AcpEnableTool()
    with pytest.raises(RuntimeError, match="acp_enable is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

def test_acp_disable_tool():
    tool = AcpDisableTool()
    with pytest.raises(RuntimeError, match="acp_disable is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})

def test_acp_status_tool():
    tool = AcpStatusTool()
    with pytest.raises(RuntimeError, match="acp_status is service-backed and must be executed via ToolService."):
        tool.execute(context=MagicMock(), arguments={})


from app.tools.registry import ToolRegistry

def test_tool_registry():
    registry = ToolRegistry()
    mock_tool = MagicMock()
    mock_tool.descriptor.name = "test_tool"
    mock_tool.descriptor.description = "Test description"
    mock_tool.descriptor.parameters = {"type": "object"}

    registry.register(mock_tool)

    # get
    assert registry.get("test_tool") == mock_tool
    with pytest.raises(KeyError, match="Unknown tool: missing_tool"):
        registry.get("missing_tool")

    # list
    assert registry.list() == [mock_tool]

    # describe (openai format)
    openai_desc = registry.describe(format="openai")
    assert len(openai_desc) == 1
    assert openai_desc[0] == {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "Test description",
            "parameters": {"type": "object"},
        }
    }

    # describe (anthropic format)
    anthropic_desc = registry.describe(format="anthropic")
    assert len(anthropic_desc) == 1
    assert anthropic_desc[0] == {
        "name": "test_tool",
        "description": "Test description",
        "input_schema": {"type": "object"},
    }


from app.tools.registry import _require_string, _read_optional_int, _read_extract_mode, _format_search_results

def test_require_string():
    assert _require_string({"key": "value"}, "key") == "value"
    with pytest.raises(ValueError, match="Missing required string argument: missing"):
        _require_string({}, "missing")

def test_read_optional_int():
    assert _read_optional_int({"key": 5}, "key", default=10, minimum=1, maximum=20) == 5
    assert _read_optional_int({"key": "15"}, "key", default=10, minimum=1, maximum=20) == 15
    assert _read_optional_int({}, "missing", default=10, minimum=1, maximum=20) == 10

    # bounds checking
    assert _read_optional_int({"key": 0}, "key", default=10, minimum=1, maximum=20) == 1
    assert _read_optional_int({"key": 25}, "key", default=10, minimum=1, maximum=20) == 20

    with pytest.raises(ValueError, match="Invalid integer argument: key"):
        _read_optional_int({"key": "not-an-int"}, "key", default=10, minimum=1, maximum=20)

def test_read_extract_mode():
    assert _read_extract_mode(None) == "markdown"
    assert _read_extract_mode("markdown") == "markdown"
    assert _read_extract_mode("text") == "text"

    with pytest.raises(ValueError, match="extract_mode must be either `markdown` or `text`"):
        _read_extract_mode("invalid")

def test_format_search_results():
    # Empty/invalid
    assert _format_search_results([]) == "No results found."
    assert _format_search_results(None) == "No results found."

    # Valid results
    results = [
        {"title": "Title 1", "url": "https://url1.com", "snippet": "Snippet 1"},
        {"title": "", "url": "https://url2.com", "snippet": "Snippet 2"},
        "invalid item", # should be skipped
        {"title": "Title 3"}, # partial
    ]

    formatted = _format_search_results(results)
    assert "1. Title 1" in formatted
    assert "https://url1.com" in formatted
    assert "Snippet 1" in formatted

    assert "2. Untitled result" in formatted
    assert "https://url2.com" in formatted

    assert "4. Title 3" in formatted
