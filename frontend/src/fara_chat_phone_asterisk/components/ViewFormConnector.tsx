import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { PhoneConnectorActions } from '@/fara_chat/components/PhoneConnectorActions';
import { Text } from '@mantine/core';

// Поля коннектора Asterisk (нужны, чтобы форма их подгрузила): доступ к внешнему
// Asterisk-agent (REST, Basic-auth) + webhook приёма ARI-событий.
const ASTERISK_FIELDS = [
  'connector_url',
  'access_token',
  'refresh_token',
  'webhook_url',
  'webhook_state',
  'webhook_hash',
];

/**
 * Секция «Подключение» коннектора Asterisk / FreePBX.
 *
 * Транспорт один — внешний Asterisk-agent рядом с АТС: ARI-события он шлёт на
 * webhook FARA, историю (CDR), записи и номера FARA тянет из его REST API.
 */
export function ViewFormConnectorAsterisk() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.asterisk', 'Asterisk / FreePBX')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="connector_url"
          label={t('connector.fields.asteriskUrl', 'URL Asterisk-agent')}
          placeholder="http://host:8082"
        />
      </FormRow>
      <FormRow cols={2}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.asteriskLogin', 'Логин (Basic-auth)')}
        />
        <FieldChar
          name="refresh_token"
          label={t('connector.fields.asteriskPassword', 'Пароль (Basic-auth)')}
          type="password"
        />
      </FormRow>
      <Text size="xs" c="dimmed" mt={4}>
        {t(
          'connector.asterisk.webhookHint',
          'Укажите webhook-URL (вкладка «Webhooks») как адрес отправки ARI-событий в конфиге Asterisk-agent.',
        )}
      </Text>

      <PhoneConnectorActions />
    </FormSection>
  );
}

/** Webhook-секция Asterisk (агент шлёт сюда ARI-события). */
export function ViewFormConnectorAsteriskWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return <WebhookSection sourceName="Asterisk" />;
}

/** Пустой таб «Авторизация» — Asterisk использует Basic-auth из «Подключения». */
export function ViewFormConnectorAsteriskEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.asterisk.noAuthRequired',
          'Asterisk использует логин/пароль (Basic-auth) из вкладки «Подключение» для доступа к Asterisk-agent.',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения формы коннектора (гейт по type='phone_asterisk')
registerExtension(
  'chat_connector',
  ViewFormConnectorAsterisk,
  'after:FormTab:connection',
  ASTERISK_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorAsterisk;
