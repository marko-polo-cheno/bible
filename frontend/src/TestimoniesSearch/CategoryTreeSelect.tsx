import { useState, useCallback, useMemo } from 'react';
import {
  Popover, Button, Tree, Group, Checkbox, Text, Box, ScrollArea, ActionIcon,
  type TreeNodeData, type RenderTreeNodePayload,
} from '@mantine/core';
import { useTree } from '@mantine/core';

export interface CategoryNode {
  name: string;
  value: string;
  children: CategoryNode[];
}

interface CategoryTreeSelectProps {
  data: CategoryNode[];
  selectedValues: string[];
  onChange: (values: string[]) => void;
}

/** Convert backend CategoryNode[] to Mantine TreeNodeData[] */
function toTreeData(nodes: CategoryNode[]): TreeNodeData[] {
  return nodes.map(n => ({
    label: n.name,
    value: n.value,
    children: n?.children?.length > 0 ? toTreeData(n.children) : undefined,
  }));
}

/** Collect all leaf values (nodes with no children) from a CategoryNode tree */
function getAllLeafValues(nodes: CategoryNode[]): string[] {
  const leaves: string[] = [];
  for (const node of nodes) {
    const children = node.children ?? [];
    if (children.length === 0) {
      leaves.push(node.value);
    } else {
      leaves.push(...getAllLeafValues(children));
    }
  }
  return leaves;
}

/** Collect all values (both parents and leaves) from a CategoryNode tree */
function getAllValues(nodes: CategoryNode[]): string[] {
  const values: string[] = [];
  for (const node of nodes) {
    values.push(node.value);
    if (node?.children?.length > 0) {
      values.push(...getAllValues(node.children));
    }
  }
  return values;
}

/** Find a CategoryNode by value */
function findNode(nodes: CategoryNode[], value: string): CategoryNode | null {
  for (const node of nodes) {
    if (node.value === value) return node;
    if (node?.children?.length > 0) {
      const found = findNode(node.children, value);
      if (found) return found;
    }
  }
  return null;
}

/** Get all descendant values of a node (including itself) */
function getDescendantValues(node: CategoryNode): string[] {
  const values = [node.value];
  for (const child of (node.children ?? [])) {
    values.push(...getDescendantValues(child));
  }
  return values;
}

/** Get ancestor values for a given value */
function getAncestorValues(nodes: CategoryNode[], targetValue: string, path: string[] = []): string[] | null {
  for (const node of nodes) {
    if (node.value === targetValue) return path;
    if (node?.children?.length > 0) {
      const result = getAncestorValues(node.children, targetValue, [...path, node.value]);
      if (result) return result;
    }
  }
  return null;
}

/** Check state for a node: 'checked', 'indeterminate', or 'unchecked' */
function getCheckState(
  node: CategoryNode,
  selectedSet: Set<string>,
): 'checked' | 'indeterminate' | 'unchecked' {
  const children = node.children ?? [];
  if (children.length === 0) {
    return selectedSet.has(node.value) ? 'checked' : 'unchecked';
  }

  const childStates = children.map(c => getCheckState(c, selectedSet));
  const allChecked = childStates.every(s => s === 'checked');
  const anyChecked = childStates.some(s => s === 'checked' || s === 'indeterminate');

  if (allChecked) return 'checked';
  if (anyChecked) return 'indeterminate';
  return 'unchecked';
}

export default function CategoryTreeSelect({ data, selectedValues, onChange }: CategoryTreeSelectProps) {
  const [opened, setOpened] = useState(false);
  const tree = useTree({ multiple: true });

  const treeData = useMemo(() => toTreeData(data), [data]);
  const allLeafValues = useMemo(() => getAllLeafValues(data), [data]);
  const selectedSet = useMemo(() => new Set(selectedValues), [selectedValues]);

  const handleToggle = useCallback((value: string) => {
    const node = findNode(data, value);
    if (!node) return;

    const descendantLeaves = node?.children?.length > 0
      ? getAllLeafValues([node])
      : [node.value];

    const currentState = getCheckState(node, selectedSet);
    const newSelected = new Set(selectedValues);

    if (currentState === 'checked') {
      // Uncheck all descendants
      for (const v of descendantLeaves) newSelected.delete(v);
    } else {
      // Check all descendants
      for (const v of descendantLeaves) newSelected.add(v);
    }

    onChange(Array.from(newSelected));
  }, [data, selectedValues, selectedSet, onChange]);

  const handleSelectAll = useCallback(() => {
    onChange([...allLeafValues]);
  }, [allLeafValues, onChange]);

  const handleClearAll = useCallback(() => {
    onChange([]);
  }, [onChange]);

  const renderNode = useCallback(({ node, expanded, hasChildren, elementProps }: RenderTreeNodePayload) => {
    const catNode = findNode(data, node.value);
    const state = catNode ? getCheckState(catNode, selectedSet) : 'unchecked';

    return (
      <Group gap="xs" {...elementProps} onClick={undefined} wrap="nowrap">
        {hasChildren && (
          <ActionIcon
            size="xs"
            variant="subtle"
            color="gray"
            onClick={(e) => { e.stopPropagation(); tree.toggleExpanded(node.value); }}
          >
            <Text size="xs">{expanded ? '▼' : '▶'}</Text>
          </ActionIcon>
        )}
        {!hasChildren && <Box w={22} />}
        <Checkbox
          size="xs"
          checked={state === 'checked'}
          indeterminate={state === 'indeterminate'}
          onChange={() => handleToggle(node.value)}
          onClick={(e) => e.stopPropagation()}
        />
        <Text
          size="sm"
          style={{ cursor: 'pointer' }}
          onClick={() => handleToggle(node.value)}
        >
          {node.label}
        </Text>
      </Group>
    );
  }, [data, selectedSet, tree, handleToggle]);

  const selectedCount = selectedValues.length;
  const totalLeaves = allLeafValues.length;

  let buttonLabel = 'All categories';
  if (selectedCount > 0 && selectedCount < totalLeaves) {
    buttonLabel = `${selectedCount} categor${selectedCount === 1 ? 'y' : 'ies'} selected`;
  } else if (selectedCount === 0) {
    buttonLabel = 'All categories';
  }

  return (
    <Popover opened={opened} onChange={setOpened} position="bottom-start" width={360} shadow="md">
      <Popover.Target>
        <Button
          variant="default"
          size="sm"
          onClick={() => setOpened(o => !o)}
          styles={{ label: { fontWeight: 400 } }}
        >
          {buttonLabel}
        </Button>
      </Popover.Target>
      <Popover.Dropdown p="xs">
        <Group justify="space-between" mb="xs">
          <Text size="xs" c="dimmed">Filter by category</Text>
          <Group gap={4}>
            <Button size="compact-xs" variant="subtle" onClick={handleSelectAll}>Select all</Button>
            <Button size="compact-xs" variant="subtle" color="gray" onClick={handleClearAll}>Clear</Button>
          </Group>
        </Group>
        <ScrollArea.Autosize mah={400}>
          <Tree
            data={treeData}
            tree={tree}
            levelOffset="md"
            expandOnClick={false}
            renderNode={renderNode}
          />
        </ScrollArea.Autosize>
      </Popover.Dropdown>
    </Popover>
  );
}
