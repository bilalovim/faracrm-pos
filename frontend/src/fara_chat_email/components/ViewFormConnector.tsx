import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldInteger } from '@/components/Form/Fields/FieldInteger';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { Button, Group, Select } from '@mantine/core';
import { IconPlugConnected } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTestConnectorMutation } from '@/services/api/chat';

// Поля которые использует email расширение
const EMAIL_FIELDS = [
  'smtp_host',
  'smtp_port',
  'smtp_encryption',
  'imap_host',
  'imap_port',
  'imap_ssl',
  'email_username',
  'email_password',
  // Отправитель (From) — outbox-аккаунт. external_account_id при сохранении
  // создаёт chat_external_account (см. ChatConnector._ensure_outbox_account),
  // а его external_id становится From-адресом письма (email.strategy).
  'external_account_id',
  'email_from_name',
];

/**
 * Пресеты популярных email серверов
 */
const EMAIL_PRESETS = {
  gmail: {
    label: 'Gmail',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_encryption: 'starttls',
    imap_host: 'imap.gmail.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  yandex: {
    label: 'Yandex',
    smtp_host: 'smtp.yandex.ru',
    smtp_port: 465,
    smtp_encryption: 'ssl',
    imap_host: 'imap.yandex.ru',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  mailru: {
    label: 'Mail.ru',
    smtp_host: 'smtp.mail.ru',
    smtp_port: 465,
    smtp_encryption: 'ssl',
    imap_host: 'imap.mail.ru',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  outlook: {
    label: 'Outlook / Hotmail',
    smtp_host: 'smtp-mail.outlook.com',
    smtp_port: 587,
    smtp_encryption: 'starttls',
    imap_host: 'outlook.office365.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  office365: {
    label: 'Office 365',
    smtp_host: 'smtp.office365.com',
    smtp_port: 587,
    smtp_encryption: 'starttls',
    imap_host: 'outlook.office365.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  yahoo: {
    label: 'Yahoo',
    smtp_host: 'smtp.mail.yahoo.com',
    smtp_port: 465,
    smtp_encryption: 'ssl',
    imap_host: 'imap.mail.yahoo.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  icloud: {
    label: 'iCloud',
    smtp_host: 'smtp.mail.me.com',
    smtp_port: 587,
    smtp_encryption: 'starttls',
    imap_host: 'imap.mail.me.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  zoho: {
    label: 'Zoho Mail',
    smtp_host: 'smtp.zoho.com',
    smtp_port: 465,
    smtp_encryption: 'ssl',
    imap_host: 'imap.zoho.com',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
  custom: {
    label: 'Другой сервер',
    smtp_host: '',
    smtp_port: 587,
    smtp_encryption: 'starttls',
    imap_host: '',
    imap_port: 993,
    imap_ssl: 'ssl',
  },
} as const;

type PresetKey = keyof typeof EMAIL_PRESETS;

/**
 * Расширение формы коннектора для Email.
 * Добавляется в таб "connection".
 */
export function ViewFormConnectorEmail() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [testConnector, { isLoading: isTesting }] = useTestConnectorMutation();

  if (form.values?.type !== 'email') {
    return null;
  }

  const connectorId = form.values?.id;

  const handleTestConnection = async () => {
    // Проверка идёт по СОХРАНЁННЫМ настройкам коннектора, поэтому для
    // нового/изменённого коннектора сперва нужно сохранить форму.
    if (!connectorId) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.email.saveBeforeTest',
          'Сначала сохраните коннектор, затем проверьте соединение',
        ),
        color: 'yellow',
      });
      return;
    }

    try {
      const { data } = await testConnector({
        connectorId: Number(connectorId),
      }).unwrap();

      notifications.show({
        title: data.ok
          ? t('connector.email.testOk', 'Соединение установлено')
          : t('connector.email.testFail', 'Ошибка соединения'),
        message: data.message,
        color: data.ok ? 'green' : 'red',
        autoClose: data.ok ? 4000 : false,
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.email.testError', 'Не удалось проверить соединение'),
        color: 'red',
      });
    }
  };

  // Определяем текущий пресет на основе smtp_host
  const getCurrentPreset = (): PresetKey | null => {
    const smtpHost = form.values?.smtp_host;
    if (!smtpHost) return null;

    for (const [key, preset] of Object.entries(EMAIL_PRESETS)) {
      if (preset.smtp_host === smtpHost) {
        return key as PresetKey;
      }
    }
    return 'custom';
  };

  const handlePresetChange = (value: string | null) => {
    if (!value || value === 'custom') return;

    const preset = EMAIL_PRESETS[value as PresetKey];
    if (preset) {
      form.setFieldValue('smtp_host', preset.smtp_host);
      form.setFieldValue('smtp_port', preset.smtp_port);
      form.setFieldValue('smtp_encryption', preset.smtp_encryption);
      form.setFieldValue('imap_host', preset.imap_host);
      form.setFieldValue('imap_port', preset.imap_port);
      form.setFieldValue('imap_ssl', preset.imap_ssl);
    }
  };

  const presetOptions = Object.entries(EMAIL_PRESETS).map(([key, preset]) => ({
    value: key,
    label: preset.label,
  }));

  return (
    <>
      {/* Пресет */}
      <FormSection>
        <FormRow cols={1}>
          <Select
            label={t('connector.fields.emailPreset', 'Почтовый сервис')}
            placeholder={t(
              'connector.fields.emailPresetPlaceholder',
              'Выберите сервис для автозаполнения',
            )}
            data={presetOptions}
            value={getCurrentPreset()}
            onChange={handlePresetChange}
            searchable
            clearable
            nothingFoundMessage={t('common.nothingFound', 'Ничего не найдено')}
          />
        </FormRow>
      </FormSection>

      {/* SMTP */}
      <FormSection
        title={t('connector.groups.smtp', 'SMTP (отправка)')}
        collapsible>
        <FormRow cols={3}>
          <FieldChar
            name="smtp_host"
            label={t('connector.fields.smtpHost', 'Сервер')}
            placeholder="smtp.gmail.com"
          />
          <FieldInteger
            name="smtp_port"
            label={t('connector.fields.smtpPort', 'Порт')}
          />
          <FieldSelection
            name="smtp_encryption"
            label={t('connector.fields.smtpEncryption', 'Шифрование')}
          />
        </FormRow>
      </FormSection>

      {/* IMAP */}
      <FormSection
        title={t('connector.groups.imap', 'IMAP (получение)')}
        collapsible>
        <FormRow cols={3}>
          <FieldChar
            name="imap_host"
            label={t('connector.fields.imapHost', 'Сервер')}
            placeholder="imap.gmail.com"
          />
          <FieldInteger
            name="imap_port"
            label={t('connector.fields.imapPort', 'Порт')}
          />
          <FieldSelection
            name="imap_ssl"
            label={t('connector.fields.imapSsl', 'SSL')}
          />
        </FormRow>
      </FormSection>

      {/* Учётные данные */}
      <FormSection
        title={t('connector.groups.credentials', 'Учётные данные')}
        collapsible>
        <FormRow cols={2}>
          <FieldChar
            name="email_username"
            label={t('connector.fields.emailUsername', 'Email')}
            placeholder="user@gmail.com"
          />
          <FieldChar
            name="email_password"
            label={t('connector.fields.emailPassword', 'Пароль')}
            type="password"
          />
        </FormRow>
        <Group justify="flex-end" mt="sm">
          <Button
            variant="light"
            leftSection={<IconPlugConnected size={16} />}
            onClick={handleTestConnection}
            loading={isTesting}>
            {t('connector.email.testConnection', 'Проверить соединение')}
          </Button>
        </Group>
      </FormSection>

      {/* Отправитель (From) — outbox-аккаунт.
          Для email «от кого» не зависит от реального отправителя-сотрудника:
          это кастомный адрес. external_account_id при сохранении создаёт
          outbox-аккаунт, чей external_id уходит в заголовок From. Если пусто —
          From = email отправителя из «Учётных данных». */}
      <FormSection
        title={t('connector.groups.emailSender', 'Отправитель (From)')}
        collapsible>
        <FormRow cols={2}>
          <FieldChar
            name="external_account_id"
            label={t('connector.fields.emailFrom', 'Email отправителя (From)')}
            placeholder="noreply@company.com"
          />
          <FieldChar
            name="email_from_name"
            label={t('connector.fields.emailFromName', 'Имя отправителя')}
            placeholder="Company Support"
          />
        </FormRow>
      </FormSection>
    </>
  );
}

/**
 * Пустой компонент для замены таба auth у Email.
 */
export function ViewFormConnectorEmailEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'email') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t('connector.email.noAuthRequired')}
      </p>
    </FormSection>
  );
}

// Регистрируем внутри таба connection с полями
registerExtension(
  'chat_connector',
  ViewFormConnectorEmail,
  'inside:FormTab:connection',
  EMAIL_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorEmailEmptyAuth,
  'after:FormTab:auth',
);

registerExtension(
  'chat_connector',
  ViewFormConnectorEmailEmptyAuth,
  'after:FormTab:webhooks',
);

export default ViewFormConnectorEmail;
