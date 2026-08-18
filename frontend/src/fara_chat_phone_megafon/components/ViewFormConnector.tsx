import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { PhoneConnectorActions } from '@/fara_chat/components/PhoneConnectorActions';
import { Text } from '@mantine/core';

// Поля коннектора МегаФон ВАТС (нужны, чтобы форма их подгрузила).
const MEGAFON_FIELDS = [
  'connector_url',
  'access_token',
  'webhook_url',
  'webhook_state',
  'webhook_hash',
];

/**
 * Секция «Подключение» коннектора МегаФон ВАТС.
 *
 * События звонков ВАТС шлёт на webhook FARA, историю/записи/пользователей FARA
 * тянет из REST API по ключу X-API-KEY.
 */
export function ViewFormConnectorMegafon() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_megafon') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.megafon', 'МегаФон ВАТС')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="connector_url"
          label={t('connector.fields.megafonUrl', 'URL API ВАТС')}
          placeholder="https://vpbx.megafon.ru/crmapi/v1"
        />
      </FormRow>
      <FormRow cols={1}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.megafonApiKey', 'API-ключ (X-API-KEY)')}
          type="password"
        />
      </FormRow>
      <Text size="xs" c="dimmed" mt={4}>
        {t(
          'connector.megafon.webhookHint',
          'Укажите webhook-URL (вкладка «Webhooks») в личном кабинете ВАТС как адрес отправки событий звонков.',
        )}
      </Text>

      <PhoneConnectorActions />
    </FormSection>
  );
}

/** Webhook-секция МегаФон (сюда приходят команды event / history). */
export function ViewFormConnectorMegafonWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'phone_megafon') {
    return null;
  }

  return <WebhookSection sourceName="MegaFon" />;
}

/** Пустой таб «Авторизация» — МегаФон использует API-ключ из «Подключения». */
export function ViewFormConnectorMegafonEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_megafon') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.megafon.noAuthRequired',
          'МегаФон ВАТС использует API-ключ из вкладки «Подключение» (заголовок X-API-KEY).',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения формы коннектора (гейт по type='phone_megafon')
registerExtension(
  'chat_connector',
  ViewFormConnectorMegafon,
  'after:FormTab:connection',
  MEGAFON_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMegafonWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMegafonEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorMegafon;
