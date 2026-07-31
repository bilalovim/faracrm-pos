import { useState } from 'react';
import { Menu, Button, rem } from '@mantine/core';
import { IconTrash, IconPencil } from '@tabler/icons-react';
import { useDeleteBulkMutation } from '@/services/api/crudApi';
import { FaraRecord, GetListField } from '@/services/api/crudTypes';
import { MassActionModal } from './MassActionModal';

export function Actions({
  resource,
  selectedIds,
  fields = [],
  massActions = false,
  onClearSelection,
  onDeleteStart,
  onDeleteSuccess,
  onDeleteError,
}: {
  resource: string;
  selectedIds: FaraRecord[];
  /** Поля модели (из data.fields листа) — для выбора в массовом действии. */
  fields?: GetListField[];
  /** Показывать ли пункт массового действия. */
  massActions?: boolean;
  onClearSelection?: () => void;
  onDeleteStart?: () => void;
  onDeleteSuccess?: (count: number, undo?: () => void) => void;
  onDeleteError?: () => void;
}) {
  const [deleteBulk] = useDeleteBulkMutation();
  const [massOpen, setMassOpen] = useState(false);

  const handleDelete = async () => {
    const count = selectedIds.length;
    const idsToDelete = selectedIds.map(obj => obj.id);

    onDeleteStart?.();
    onClearSelection?.();

    // Вызываем success сразу - optimistic update уже произошёл
    onDeleteSuccess?.(count);

    // Запрос идёт в фоне
    deleteBulk({
      model: resource,
      ids: idsToDelete,
    })
      .unwrap()
      .catch(() => {
        onDeleteError?.();
      });
  };

  return (
    <>
      <Menu shadow="md" width={220}>
        <Menu.Target>
          <Button>Actions</Button>
        </Menu.Target>

        <Menu.Dropdown>
          {massActions && (
            <>
              <Menu.Label>Массовые действия</Menu.Label>
              <Menu.Item
                leftSection={
                  <IconPencil style={{ width: rem(14), height: rem(14) }} />
                }
                onClick={() => setMassOpen(true)}>
                Изменить поле ({selectedIds.length})
              </Menu.Item>
              <Menu.Divider />
            </>
          )}

          <Menu.Label>Danger zone</Menu.Label>
          <Menu.Item
            onClick={handleDelete}
            color="red"
            leftSection={
              <IconTrash style={{ width: rem(14), height: rem(14) }} />
            }>
            Delete records ({selectedIds.length})
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>

      {massActions && (
        <MassActionModal
          opened={massOpen}
          onClose={() => setMassOpen(false)}
          model={resource}
          fields={fields}
          selectedIds={selectedIds}
          onDone={() => {
            setMassOpen(false);
            onClearSelection?.();
          }}
        />
      )}
    </>
  );
}
