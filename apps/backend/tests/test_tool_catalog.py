from __future__ import annotations

from unittest.mock import Mock, patch

from app.tools.base import ToolDescriptor
from app.tools.catalog import ToolCatalogEntry, build_tool_catalog, catalog_entry_from_descriptor


def test_catalog_entry_from_descriptor() -> None:
    descriptor = ToolDescriptor(
        name="test_tool",
        label="Test Tool",
        description="A test tool",
        group="group:fs",
        risk="low",
        status="enabled",
        parameters={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        requires_workspace=True,
    )

    entry = catalog_entry_from_descriptor(descriptor)

    assert isinstance(entry, ToolCatalogEntry)
    assert entry.id == "test_tool"
    assert entry.label == "Test Tool"
    assert entry.description == "A test tool"
    assert entry.group == "group:fs"
    assert entry.group_label == "Filesystem"  # from GROUP_LABELS mapping
    assert entry.risk == "low"
    assert entry.status == "enabled"
    assert entry.input_schema == {"type": "object", "properties": {}}
    assert entry.output_schema == {"type": "object", "properties": {}}
    assert entry.requires_workspace is True


@patch("app.tools.catalog.build_tool_registry")
def test_build_tool_catalog(mock_build_registry: Mock) -> None:
    # Setup mock registry with out-of-order tools
    mock_registry = Mock()
    mock_build_registry.return_value = mock_registry

    tool1 = Mock()
    tool1.descriptor = ToolDescriptor(
        name="zzz_tool",
        label="Z Tool",
        description="Z",
        group="group:automation",
        risk="high",
        status="enabled",
        parameters={},
        requires_workspace=False,
    )

    tool2 = Mock()
    tool2.descriptor = ToolDescriptor(
        name="aaa_tool",
        label="A Tool",
        description="A",
        group="group:web",
        risk="low",
        status="experimental",
        parameters={},
        requires_workspace=False,
    )

    # Return them in an order that is not alphabetical by id
    mock_registry.list.return_value = [tool1, tool2]

    # Execute
    catalog = build_tool_catalog()

    # Verify
    assert len(catalog) == 2
    assert isinstance(catalog[0], ToolCatalogEntry)
    assert isinstance(catalog[1], ToolCatalogEntry)

    # Check that items are sorted by id (name)
    assert catalog[0].id == "aaa_tool"
    assert catalog[1].id == "zzz_tool"

    # Verify attributes of sorted items
    assert catalog[0].group_label == "Web"
    assert catalog[1].group_label == "Automation"

    mock_build_registry.assert_called_once()
    mock_registry.list.assert_called_once()
