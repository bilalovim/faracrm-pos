import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { PhoneConnectorActions } from '@/fara_chat/components/PhoneConnectorActions';
import { Text } from '@mantine/core';

// Поля коннектора Sipuni (нужны, чтобы форма их подгрузила).
const SIPUNI_FIELDS = [
  'connector_url',
  'access_token',
  'refresh_token',
  'webhook_url',
  'webhook_state',
  'webhook_hash',
];

/**
 * Секция «Подключение» коннектора Sipuni.
 *
 * События звонков Sipuni шлёт на webhook FARA, историю/записи/операторов FARA
 * тянет из API по логину и паролю (запрос подписывается MD5).
 */
export function ViewFormConnectorSipuni() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_sipuni') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.sipuni', 'Sipuni')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="connector_url"
          label={t('connector.fields.sipuniUrl', 'URL API Sipuni')}
          placeholder="https://sipuni.com/api"
        />
      </FormRow>
      <FormRow cols={2}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.sipuniLogin', 'Логин Sipuni')}
        />
        <FieldChar
          name="refresh_token"
          label={t('connector.fields.sipuniPassword', 'Пароль Sipuni')}
          type="password"
        />
      </FormRow>
      <Text size="xs" c="dimmed" mt={4}>
        {t(
          'connector.sipuni.webhookHint',
          'Укажите webhook-URL (вкладка «Webhooks») в интеграциях личного кабинета Sipuni — API его не устанавливает.',
        )}
      </Text>

      <PhoneConnectorActions />
    </FormSection>
  );
}

/** Webhook-секция Sipuni (сюда приходят события звонков). */
export function ViewFormConnectorSipuniWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'phone_sipuni') {
    return null;
  }

  return <WebhookSection sourceName="Sipuni" />;
}

/** Пустой таб «Авторизация» — Sipuni подписывает запросы логином/паролем. */
export function ViewFormConnectorSipuniEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_sipuni') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.sipuni.noAuthRequired',
          'Sipuni использует логин и пароль из вкладки «Подключение» — ими подписывается каждый запрос к API.',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения формы коннектора (гейт по type='phone_sipuni')
registerExtension(
  'chat_connector',
  ViewFormConnectorSipuni,
  'after:FormTab:connection',
  SIPUNI_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorSipuniWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorSipuniEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorSipuni;
