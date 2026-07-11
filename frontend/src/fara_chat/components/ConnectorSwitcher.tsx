import { ChatConnectorDetail } from '@/services/api/chat';
import { ActionIcon, Menu, Tooltip, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { connectorIcon, connectorColors } from './connectorMeta';

export type ConnectorOption = ChatConnectorDetail;

interface ConnectorSwitcherProps {
  connectors: ChatConnectorDetail[];
  selectedConnectorId: number | null;
  onSelect: (connectorId: number | null) => void;
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
        {connectors.map(connector => (
          <Menu.Item
            key={connector.connector_id ?? 'internal'}
            leftSection={connectorIcon(connector.connector_type, 16)}
            onClick={() => onSelect(connector.connector_id)}
            color={
              connector.connector_id === selectedConnectorId
                ? connectorColors[connector.connector_type]
                : undefined
            }>
            <Text
              size="sm"
              fw={connector.connector_id === selectedConnectorId ? 600 : 400}>
              {connector.connector_name}
            </Text>
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

export default ConnectorSwitcher;
