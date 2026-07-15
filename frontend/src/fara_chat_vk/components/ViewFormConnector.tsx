import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { Button, Group, Modal, Text, Code } from '@mantine/core';
import { IconUserSearch } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';
import { notifications } from '@mantine/notifications';
import { useLazyGetConnectorSelfAccountQuery } from '@/services/api/chat';

/**
 * Расширение формы коннектора для ВКонтакте.
 *
 * Добавляется в таб "connection" — основные поля интеграции
 * (access_token, external_account_id, connector_url) видны только при
 * выборе типа коннектора "vk".
 *
 * access_token — ключ доступа СООБЩЕСТВА (Управление → Настройки → Работа с
 * API). external_account_id — числовой id сообщества (group_id); его можно
 * заполнить кнопкой "Получить данные сообщества" (метод groups.getById через
 * общий endpoint account/self).
 */
export function ViewFormConnectorVk() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [getSelfAccount, { isFetching }] =
    useLazyGetConnectorSelfAccountQuery();
  const [accountText, setAccountText] = useState<string>('');
  const [opened, { open, close }] = useDisclosure(false);

  if (form.values?.type !== 'vk') {
    return null;
  }

  const connectorId = form.values?.id;
  const isNewRecord = !connectorId;

  const handleFetchAccount = async () => {
    if (!connectorId) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message: t(
          'connector.account.saveFirst',
          'Сначала сохраните коннектор',
        ),
        color: 'red',
      });
      return;
    }

    try {
      const result = await getSelfAccount({
        connectorId: Number(connectorId),
      }).unwrap();
      const text =
        typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      setAccountText(text);
      open();
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t(
            'connector.account.fetchError',
            'Не удалось получить данные аккаунта',
          ),
        color: 'red',
      });
    }
  };

  return (
    <>
      <FormSection title={t('connector.groups.vk', 'ВКонтакте')} collapsible>
        <FormRow cols={1}>
          <FieldChar
            name="access_token"
            label={t('connector.fields.vkToken', 'Ключ доступа сообщества')}
            placeholder="vk1.a.XXXXXXXX..."
          />
        </FormRow>
        <FormRow cols={2}>
          <FieldChar
            name="external_account_id"
            label={t('connector.fields.vkGroupId', 'ID сообщества (group_id)')}
            placeholder="123456789"
          />
          <FieldChar
            name="connector_url"
            label={t('connector.fields.connectorUrl', 'URL API')}
            placeholder="https://api.vk.com/method"
          />
        </FormRow>
        <FormRow cols={1}>
          <FieldChar
            name="vk_confirmation"
            label={t(
              'connector.fields.vkConfirmation',
              'Строка подтверждения (Callback API)',
            )}
            placeholder="76c42d65"
          />
        </FormRow>
        <Group justify="flex-end" mt="xs">
          <Button
            leftSection={<IconUserSearch size={16} />}
            onClick={handleFetchAccount}
            loading={isFetching}
            disabled={isNewRecord}
            variant="light">
            {t(
              'connector.account.fetchSelfVk',
              'Получить данные сообщества VK',
            )}
          </Button>
        </Group>
        {isNewRecord && (
          <Text size="xs" c="dimmed" mt={4} ta="right">
            {t(
              'connector.account.saveFirstHint',
              'Сначала сохраните коннектор, чтобы сделать запрос',
            )}
          </Text>
        )}
      </FormSection>

      <Modal
        opened={opened}
        onClose={close}
        title={t('connector.account.modalTitleVk', 'Информация о сообществе VK')}
        size="lg">
        <Code
          block
          style={{
            maxHeight: 500,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
          {accountText}
        </Code>
      </Modal>
    </>
  );
}

/**
 * Webhook секция для ВКонтакте.
 * Использует общий компонент WebhookSection (как у Telegram/MAX).
 */
export function ViewFormConnectorVkWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'vk') {
    return null;
  }

  return <WebhookSection sourceName="VK" />;
}

/**
 * Пустой компонент для замены таба auth у ВКонтакте.
 * VK использует статический ключ доступа сообщества — отдельная авторизация
 * не нужна.
 */
export function ViewFormConnectorVkEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'vk') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.vk.noAuthRequired',
          'ВКонтакте использует ключ доступа сообщества для авторизации. Настройте его во вкладке "Подключение".',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения
registerExtension(
  'chat_connector',
  ViewFormConnectorVk,
  'after:FormTab:connection',
  ['access_token', 'external_account_id', 'connector_url', 'vk_confirmation'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorVkWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorVkEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorVk;
