import { useMemo, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Group,
  Menu,
  Paper,
  ScrollArea,
  Text,
  TextInput,
} from '@mantine/core';
import {
  IconPlus,
  IconX,
  IconTrash,
  IconAlertTriangle,
} from '@tabler/icons-react';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';
import {
  useGetRouteModelFieldsQuery,
  FieldInfoResponse,
} from '@/services/api/crudApi';

/**
 * Конструктор шаблонов имён папок для маршрутов вложений.
 *
 * Идея: вместо ручного ввода конструкций вида "{id}-{name}" (где легко
 * ошибиться в имени поля или синтаксисе {}) пользователь СОБИРАЕТ шаблон из
 * «тегов» — валидных токенов. Токены-поля подтягиваются динамически из
 * выбранной в маршруте модели (связь model_id), поэтому выбрать можно только
 * СУЩЕСТВУЮЩИЕ поля.
 *
 * Два виджета на базе одного ядра:
 *  - FieldPatternRoot   — корневая папка. Статичный набор токенов ({model},
 *    {table}). Всегда режим тегов.
 *  - FieldPatternRecord — папка записи. Токены = поля выбранной модели +
 *    {id}, {zfill(id)}. Если модель НЕ выбрана (глобальный маршрут) —
 *    откат на обычный текстовый ввод (как было раньше).
 *
 * Значение поля в форме остаётся обычной строкой-шаблоном — сериализация
 * тегов ↔ строка происходит внутри виджета, бэкенд не меняется.
 */

// ---------------------------------------------------------------------------
// Модель сегментов
// ---------------------------------------------------------------------------

type Segment =
  | { kind: 'token'; value: string } // value без фигурных скобок, напр. "name"
  | { kind: 'literal'; value: string }; // произвольный разделитель, напр. "-"

interface TokenOption {
  /** Значение токена без скобок (напр. "name", "zfill(id)", "model"). */
  token: string;
  /** Подпись для чипа/меню. */
  label: string;
  /** Тип для окраски/группировки. */
  group?: string;
}

/** Разобрать строку-шаблон в сегменты. Токены — это {...}. */
const parsePattern = (pattern: string): Segment[] => {
  if (!pattern) return [];
  const segments: Segment[] = [];
  // Разбиваем, сохраняя разделители-токены {...}
  const parts = pattern.split(/(\{[^{}]+\})/g);
  for (const part of parts) {
    if (!part) continue;
    const m = part.match(/^\{([^{}]+)\}$/);
    if (m) {
      segments.push({ kind: 'token', value: m[1] });
    } else {
      segments.push({ kind: 'literal', value: part });
    }
  }
  return segments;
};

/** Собрать сегменты обратно в строку-шаблон. */
const serializePattern = (segments: Segment[]): string =>
  segments
    .map(s => (s.kind === 'token' ? `{${s.value}}` : s.value))
    .join('');

// Стандартные разделители-кнопки
const SEPARATORS: { value: string; label: string }[] = [
  { value: '-', label: '-' },
  { value: '_', label: '_' },
  { value: '/', label: '/' },
  { value: ' ', label: '␣' },
  { value: '.', label: '.' },
];

// ---------------------------------------------------------------------------
// Ядро конструктора
// ---------------------------------------------------------------------------

interface PatternBuilderCoreProps {
  name: string;
  label: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  /** Доступные токены (валидные значения). */
  options: TokenOption[];
  /** Подсвечивать ли «неизвестный» токен (не входящий в options) красным. */
  validateTokens?: boolean;
  helpText?: string;
}

function PatternBuilderCore({
  name,
  label,
  labelPosition,
  required,
  options,
  validateTokens = true,
  helpText,
}: PatternBuilderCoreProps) {
  const form = useFormContext();
  // Инициализируем сегменты из значения формы. Виджет рендерится уже после
  // инициализации формы (см. Form.tsx), а меняет это поле только он сам —
  // поэтому достаточно один раз прочитать значение в инициализаторе.
  const [segments, setSegments] = useState<Segment[]>(() => {
    const current = form.getValues()?.[name];
    return current !== undefined && current !== null
      ? parsePattern(String(current))
      : [];
  });
  const [menuSearch, setMenuSearch] = useState('');
  const [customLiteral, setCustomLiteral] = useState('');

  const apply = (next: Segment[]) => {
    setSegments(next);
    form.setFieldValue(name, serializePattern(next));
  };

  const addToken = (token: string) => {
    apply([...segments, { kind: 'token', value: token }]);
    setMenuSearch('');
  };
  const addLiteral = (value: string) => {
    if (!value) return;
    // Чистим фигурные скобки — литералы не должны их содержать (иначе
    // сломают разбор и снова получим ручной ввод {}).
    const clean = value.replace(/[{}]/g, '');
    if (!clean) return;
    apply([...segments, { kind: 'literal', value: clean }]);
    setCustomLiteral('');
  };
  const removeAt = (index: number) => {
    apply(segments.filter((_, i) => i !== index));
  };
  const editLiteral = (index: number, value: string) => {
    const clean = value.replace(/[{}]/g, '');
    apply(
      segments.map((s, i) =>
        i === index ? { kind: 'literal', value: clean } : s,
      ),
    );
  };

  const knownTokens = useMemo(
    () => new Set(options.map(o => o.token)),
    [options],
  );

  const filteredOptions = useMemo(() => {
    const q = menuSearch.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      o =>
        o.token.toLowerCase().includes(q) ||
        o.label.toLowerCase().includes(q),
    );
  }, [options, menuSearch]);

  const preview = serializePattern(segments);

  return (
    <FieldWrapper
      label={label}
      labelPosition={labelPosition}
      required={required}>
      <Box>
        <Paper withBorder p="xs" radius="md">
          {/* Собранные сегменты */}
          <Group gap={6} mih={34} align="center" wrap="wrap">
            {segments.length === 0 && (
              <Text size="sm" c="dimmed">
                Добавьте поля и разделители кнопками ниже
              </Text>
            )}
            {segments.map((seg, index) =>
              seg.kind === 'token' ? (
                <Badge
                  key={`t-${index}`}
                  size="lg"
                  variant="light"
                  color={
                    !validateTokens || knownTokens.has(seg.value)
                      ? 'blue'
                      : 'red'
                  }
                  leftSection={
                    validateTokens && !knownTokens.has(seg.value) ? (
                      <IconAlertTriangle size={12} />
                    ) : undefined
                  }
                  rightSection={
                    <ActionIcon
                      size="xs"
                      variant="transparent"
                      color="gray"
                      onClick={() => removeAt(index)}
                      aria-label="Удалить">
                      <IconX size={12} />
                    </ActionIcon>
                  }
                  style={{ textTransform: 'none' }}>
                  {`{${seg.value}}`}
                </Badge>
              ) : (
                <Group key={`l-${index}`} gap={2} align="center">
                  <TextInput
                    size="xs"
                    value={seg.value}
                    onChange={e =>
                      editLiteral(index, e.currentTarget.value)
                    }
                    styles={{
                      input: {
                        width: Math.max(28, seg.value.length * 9 + 18),
                        textAlign: 'center',
                        paddingLeft: 4,
                        paddingRight: 4,
                      },
                    }}
                  />
                  <ActionIcon
                    size="xs"
                    variant="subtle"
                    color="gray"
                    onClick={() => removeAt(index)}
                    aria-label="Удалить">
                    <IconX size={12} />
                  </ActionIcon>
                </Group>
              ),
            )}
          </Group>
        </Paper>

        {/* Панель добавления */}
        <Group gap="xs" mt="xs" align="center">
          <Menu shadow="md" width={260} position="bottom-start" withinPortal>
            <Menu.Target>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconPlus size={14} />}>
                Добавить поле
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Box px="xs" pt="xs">
                <TextInput
                  size="xs"
                  placeholder="Поиск поля..."
                  value={menuSearch}
                  onChange={e => setMenuSearch(e.currentTarget.value)}
                />
              </Box>
              <ScrollArea.Autosize mah={240} type="scroll">
                <Box p="xs">
                  {filteredOptions.length === 0 ? (
                    <Text size="xs" c="dimmed" ta="center" py="sm">
                      Ничего не найдено
                    </Text>
                  ) : (
                    filteredOptions.map(opt => (
                      <Menu.Item
                        key={opt.token}
                        onClick={() => addToken(opt.token)}
                        rightSection={
                          <Text size="xs" c="dimmed">
                            {`{${opt.token}}`}
                          </Text>
                        }>
                        {opt.label}
                      </Menu.Item>
                    ))
                  )}
                </Box>
              </ScrollArea.Autosize>
            </Menu.Dropdown>
          </Menu>

          {/* Быстрые разделители */}
          <Text size="xs" c="dimmed">
            Разделитель:
          </Text>
          {SEPARATORS.map(sep => (
            <Button
              key={sep.value}
              size="compact-xs"
              variant="default"
              onClick={() => addLiteral(sep.value)}>
              {sep.label}
            </Button>
          ))}

          {/* Свой текст-разделитель */}
          <TextInput
            size="xs"
            placeholder="свой текст"
            value={customLiteral}
            onChange={e => setCustomLiteral(e.currentTarget.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addLiteral(customLiteral);
              }
            }}
            styles={{ input: { width: 110 } }}
          />

          {segments.length > 0 && (
            <ActionIcon
              variant="subtle"
              color="red"
              onClick={() => apply([])}
              aria-label="Очистить"
              title="Очистить">
              <IconTrash size={16} />
            </ActionIcon>
          )}
        </Group>

        {/* Превью результата */}
        <Group gap={6} mt="xs" align="center">
          <Text size="xs" c="dimmed">
            Результат:
          </Text>
          <Text size="xs" ff="monospace">
            {preview || '—'}
          </Text>
        </Group>
        {helpText && (
          <Text size="xs" c="dimmed" mt={4}>
            {helpText}
          </Text>
        )}
      </Box>
    </FieldWrapper>
  );
}

// ---------------------------------------------------------------------------
// Виджет: шаблон КОРНЕВОЙ папки (статичный набор токенов)
// ---------------------------------------------------------------------------

const ROOT_TOKENS: TokenOption[] = [
  { token: 'model', label: 'Модель (имя)', group: 'static' },
  { token: 'table', label: 'Таблица', group: 'static' },
];

export function FieldPatternRoot(props: {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
}) {
  const { name, label = name, labelPosition, required } = props;
  return (
    <PatternBuilderCore
      name={name}
      label={label}
      labelPosition={labelPosition}
      required={required}
      options={ROOT_TOKENS}
      validateTokens
      helpText="Только валидные токены: {model} — имя модели, {table} — имя таблицы."
    />
  );
}

// ---------------------------------------------------------------------------
// Виджет: шаблон папки ЗАПИСИ (поля выбранной модели + id/zfill)
// ---------------------------------------------------------------------------

// Типы полей, пригодные как имя папки (скалярные). Связи/коллекции исключаем.
const SCALAR_TYPES = new Set([
  'Char',
  'TranslatedChar',
  'Text',
  'Integer',
  'Float',
  'Decimal',
  'Boolean',
  'Date',
  'Datetime',
  'Time',
  'Selection',
]);

const RECORD_STATIC_TOKENS: TokenOption[] = [
  { token: 'id', label: 'ID записи', group: 'static' },
  { token: 'zfill(id)', label: 'ID с ведущими нулями', group: 'static' },
];

/** Достать env-имя модели из значения связи model_id формы. */
const modelNameFromValue = (mid: any): string | null =>
  mid && typeof mid === 'object' ? (mid.name ?? null) : null;

export function FieldPatternRecord(props: {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
}) {
  const { name, label = name, labelPosition, required } = props;
  const form = useFormContext();

  const [modelName, setModelName] = useState<string | null>(() =>
    modelNameFromValue(form.getValues()?.model_id),
  );

  // form.watch вызывается во время рендера (правило Mantine v7): подписка на
  // изменение выбранной модели, чтобы переподтянуть её поля.
  form.watch('model_id', ({ value }: { value: any }) => {
    setModelName(modelNameFromValue(value));
  });

  const { data: fields } = useGetRouteModelFieldsQuery(modelName as string, {
    skip: !modelName,
  });

  const options: TokenOption[] = useMemo(() => {
    const fieldTokens: TokenOption[] = (fields || [])
      .filter((f: FieldInfoResponse) => SCALAR_TYPES.has(f.type))
      .map((f: FieldInfoResponse) => ({
        token: f.name,
        label: f.name,
        group: 'field',
      }));
    return [...RECORD_STATIC_TOKENS, ...fieldTokens];
  }, [fields]);

  // Модель НЕ выбрана → глобальный маршрут: поля модели неизвестны, поэтому
  // оставляем обычный текстовый ввод (как было раньше).
  if (!modelName) {
    return (
      <FieldWrapper
        label={label}
        labelPosition={labelPosition}
        required={required}>
        <TextInput
          key={form.key(name)}
          {...form.getInputProps(name)}
          placeholder="Напр. {id}-{name}"
        />
        <Text size="xs" c="dimmed" mt={4}>
          Выберите модель выше, чтобы собирать шаблон из её полей.
        </Text>
      </FieldWrapper>
    );
  }

  return (
    <PatternBuilderCore
      name={name}
      label={label}
      labelPosition={labelPosition}
      required={required}
      options={options}
      validateTokens
      helpText="Токены — поля выбранной модели, плюс {id} и {zfill(id)}."
    />
  );
}
