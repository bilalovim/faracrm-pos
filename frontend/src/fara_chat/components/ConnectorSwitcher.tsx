import { ChatConnectorDetail } from '@/services/api/chat';
import { ActionIcon, Box, Menu, Tooltip, Text } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { connectorIcon, connectorColors } from './connectorMeta';

export type ConnectorOption = ChatConnectorDetail;

interface ConnectorSwitcherProps {
  connectors: ChatConnectorDetail[];
  selectedConnectorId: number | null;
  onSelect: (connectorId: number | null) => void;
  /** Коннектор по умолчанию (галочка). null = internal. */
  defaultConnectorId?: number | null;
  /** Сохранить выбор по умолчанию (per-user). Без него галочки нет. */
  onSetDefault?: (connectorId: number | null) => void;
  disabled?: boolean;
}

/**
 * Переключатель коннектора — иконка канала в стиле микрофона/скрепки:
 * variant="subtle" (без фона и границы), поэтому не выделяется в ряду ввода.
 * Клик открывает меню выбора канала (как «скрепка» открывает меню вложений).
 * Стрелки нет намеренно — она ломала центрирование и добавляла «кнопочность».
 */
export function ConnectorSwitcher({
  connectors,
  selectedConnectorId,
  onSelect,
  defaultConnectorId,
  onSetDefault,
  disabled,
}: ConnectorSwitcherProps) {
  const { t } = useTranslation('chat');

  const selectedConnector =
    connectors.find(c => c.connector_id === selectedConnectorId) ||
    connectors[0];

  if (!selectedConnector) {
    return null;
  }

  const type = selectedConnector.connector_type;

  // Один коннектор — просто иконка канала, без выбора.
  if (connectors.length <= 1) {
    return (
      <Tooltip label={selectedConnector.connector_name}>
        <ActionIcon
          variant="subtle"
          size="lg"
          color={connectorColors[type] || 'gray'}
          disabled>
          {connectorIcon(type, 16)}
        </ActionIcon>
      </Tooltip>
    );
  }

  return (
    <Menu position="top-start" withArrow disabled={disabled}>
      <Menu.Target>
        <Tooltip label={t('selectConnector')}>
          <ActionIcon
            variant="subtle"
            size="lg"
            color={connectorColors[type] || 'gray'}>
            {connectorIcon(type, 16)}
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{t('sendVia')}</Menu.Label>
        {connectors.map(connector => {
          const cid = connector.connector_id ?? null;
          const isSelected = cid === selectedConnectorId;
          const isDefault = cid === (defaultConnectorId ?? null);
          return (
            <Menu.Item
              key={cid ?? 'internal'}
              leftSection={connectorIcon(connector.connector_type, 16)}
              // Клик по строке — выбрать только для текущего сообщения.
              onClick={() => onSelect(cid)}
              color={
                isSelected
                  ? connectorColors[connector.connector_type]
                  : undefined
              }
              rightSection={
                onSetDefault ? (
                  // Галочка справа — сохранить как «по умолчанию» (per-user).
                  // Отдельное действие: stopPropagation, чтобы не сработал выбор.
                  <Tooltip
                    label={
                      isDefault
                        ? t('defaultConnector', 'По умолчанию')
                        : t('setDefaultConnector', 'Сделать по умолчанию')
                    }
                    position="left"
                    withArrow>
                    <Box
                      component="span"
                      role="button"
                      aria-label={t(
                        'setDefaultConnector',
                        'Сделать по умолчанию',
                      )}
                      onClick={e => {
                        e.stopPropagation();
                        onSetDefault(cid);
                      }}
                      style={{
                        display: 'inline-flex',
                        cursor: 'pointer',
                        color: isDefault
                          ? 'var(--mantine-color-green-6)'
                          : 'var(--mantine-color-gray-5)',
                        opacity: isDefault ? 1 : 0.5,
                      }}>
                      <IconCheck size={16} />
                    </Box>
                  </Tooltip>
                ) : undefined
              }>
              <Text size="sm" fw={isSelected ? 600 : 400}>
                {connector.connector_name}
              </Text>
            </Menu.Item>
          );
        })}
      </Menu.Dropdown>
    </Menu>
  );
}

export default ConnectorSwitcher;
