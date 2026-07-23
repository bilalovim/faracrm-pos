/**
 * ColumnsMenu — выбор видимых колонок списка.
 *
 * Кнопка в тулбаре открывает поповер со всеми полями модели
 * (из GET /auto/{model}/fields). Галочка = колонка показана; стрелки —
 * порядок; «По умолчанию» — сброс к колонкам вью. Изменения применяются
 * к таблице сразу (onChange), а на сервер пишутся при закрытии (onClose).
 */
import { useMemo, useState } from 'react';
import {
  ActionIcon,
  Popover,
  Tooltip,
  TextInput,
  ScrollArea,
  Checkbox,
  Group,
  Text,
  Badge,
  Divider,
  Stack,
  Button,
} from '@mantine/core';
import {
  IconAdjustments,
  IconSearch,
  IconChevronUp,
  IconChevronDown,
  IconArrowBackUp,
} from '@tabler/icons-react';
import {
  useGetFieldsQuery,
  FieldInfoResponse,
} from '@/services/api/crudApi';

interface ColumnsMenuProps {
  model: string;
  /** Видимые колонки в порядке отображения. */
  selected: string[];
  /** Набор отличается от колонок вью по умолчанию. */
  isCustom: boolean;
  /** Живое изменение набора/порядка (мгновенно перестраивает таблицу). */
  onChange: (cols: string[]) => void;
  /** Сброс к колонкам вью по умолчанию. */
  onReset: () => void;
  /** Вызывается при закрытии меню — момент записи выбора на сервер. */
  onClose: () => void;
}

export function ColumnsMenu({
  model,
  selected,
  isCustom,
  onChange,
  onReset,
  onClose,
}: ColumnsMenuProps) {
  const [opened, setOpened] = useState(false);
  const [search, setSearch] = useState('');
  const { data: allFields } = useGetFieldsQuery(model);

  const fieldsByName = useMemo(() => {
    const map = new Map<string, FieldInfoResponse>();
    (allFields ?? []).forEach(f => map.set(f.name, f));
    return map;
  }, [allFields]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  // Поля модели, которых нет в видимых — их можно добавить.
  const available = useMemo(
    () =>
      (allFields ?? [])
        .map(f => f.name)
        .filter(name => !selectedSet.has(name)),
    [allFields, selectedSet],
  );

  const q = search.trim().toLowerCase();
  const matches = (name: string) => !q || name.toLowerCase().includes(q);

  const handleToggle = (name: string, checked: boolean) => {
    if (checked) {
      if (!selectedSet.has(name)) onChange([...selected, name]);
    } else {
      onChange(selected.filter(n => n !== name));
    }
  };

  const move = (index: number, dir: -1 | 1) => {
    const target = index + dir;
    if (target < 0 || target >= selected.length) return;
    const next = selected.slice();
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const handleOpenChange = (isOpen: boolean) => {
    setOpened(isOpen);
    if (!isOpen) {
      setSearch('');
      onClose(); // запись выбора на сервер (guard по dirty внутри)
    }
  };

  const typeBadge = (name: string) => {
    const t = fieldsByName.get(name)?.type;
    if (!t) return null;
    return (
      <Badge
        size="xs"
        variant="light"
        color="gray"
        style={{ textTransform: 'none' }}>
        {t}
      </Badge>
    );
  };

  const hasAvailableMatches = available.some(matches);

  return (
    <Popover
      opened={opened}
      onChange={handleOpenChange}
      position="bottom-start"
      shadow="md"
      withinPortal
      trapFocus>
      <Popover.Target>
        <Tooltip label="Настроить колонки">
          <ActionIcon
            variant={isCustom || opened ? 'light' : 'subtle'}
            color={isCustom ? 'blue' : 'gray'}
            size="md"
            onClick={() => handleOpenChange(!opened)}>
            <IconAdjustments size={18} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>

      <Popover.Dropdown p="xs" style={{ width: 320 }}>
        <Group justify="space-between" mb={6} wrap="nowrap">
          <Text size="sm" fw={600}>
            Колонки
          </Text>
          {isCustom && (
            <Button
              size="xs"
              px={6}
              variant="subtle"
              color="gray"
              leftSection={<IconArrowBackUp size={13} />}
              onClick={onReset}>
              По умолчанию
            </Button>
          )}
        </Group>

        <TextInput
          size="xs"
          mb={8}
          placeholder="Поиск поля..."
          leftSection={<IconSearch size={14} />}
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
        />

        {/* offsetScrollbars — скроллбар получает свой «жёлоб» справа и не
            перекрывает стрелки ▲▼ перестановки колонок. pr — небольшой
            зазор между контентом и жёлобом. */}
        <ScrollArea.Autosize mah={360} type="auto" offsetScrollbars="y">
          <Stack gap={2} pr={4}>
            {/* Показанные колонки — в порядке отображения + перестановка */}
            {selected.filter(matches).map(name => {
              const index = selected.indexOf(name);
              return (
                <Group key={name} gap={4} wrap="nowrap" justify="space-between">
                  <Checkbox
                    size="xs"
                    checked
                    onChange={e => handleToggle(name, e.currentTarget.checked)}
                    label={
                      <Group gap={6} wrap="nowrap">
                        <Text size="xs">{name}</Text>
                        {typeBadge(name)}
                      </Group>
                    }
                  />
                  <Group gap={0} wrap="nowrap">
                    <ActionIcon
                      size="xs"
                      variant="subtle"
                      color="gray"
                      disabled={index <= 0}
                      onClick={() => move(index, -1)}>
                      <IconChevronUp size={14} />
                    </ActionIcon>
                    <ActionIcon
                      size="xs"
                      variant="subtle"
                      color="gray"
                      disabled={index >= selected.length - 1}
                      onClick={() => move(index, 1)}>
                      <IconChevronDown size={14} />
                    </ActionIcon>
                  </Group>
                </Group>
              );
            })}

            {hasAvailableMatches && (
              <Divider my={4} label="Скрытые" labelPosition="center" />
            )}

            {/* Скрытые поля — можно добавить в таблицу */}
            {available.filter(matches).map(name => (
              <Checkbox
                key={name}
                size="xs"
                checked={false}
                onChange={e => handleToggle(name, e.currentTarget.checked)}
                label={
                  <Group gap={6} wrap="nowrap">
                    <Text size="xs" c="dimmed">
                      {name}
                    </Text>
                    {typeBadge(name)}
                  </Group>
                }
              />
            ))}

            {selected.length === 0 && !hasAvailableMatches && (
              <Text size="xs" c="dimmed" ta="center" py="sm">
                Нет полей
              </Text>
            )}
          </Stack>
        </ScrollArea.Autosize>
      </Popover.Dropdown>
    </Popover>
  );
}
