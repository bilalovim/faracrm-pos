import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
  FormSection,
} from '@/components/Form/Layout';
import {
  IconSettings,
  IconKey,
  IconHistory,
  IconLink,
  IconWebhook,
  IconUsers,
  IconFilter,
  IconBook,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
// Импорт ради side-effect: registerExtension на модульном уровне наполняет
// реестр ДО рендера формы. Вкладка «Правила работы» общая для всех типов, а
// значит регистрируется здесь, а не в per-type fara_chat_* (те гейтятся по
// form.values.type и показали бы её только своему коннектору).
import './ConnectorRulesTab';

/**
 * Базовая форма коннектора чата.
 *
 * Содержит только общие поля для всех типов коннекторов.
 * Специфичные поля (Telegram, Avito, Email и т.д.) добавляются через
 * расширения (registerExtension в соответствующем fara_chat_<type>).
 * WebhookSection добавляется через расширение в таб webhooks.
 */
export function ConnectorForm(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form model="chat_connector" {...props}>
      {/* Основная информация */}
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('connector.fields.name')} />
          <Field name="active" label={t('connector.fields.active')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="type" label={t('connector.fields.type')} />
          <Field
            name="contact_type_id"
            label={t('connector.fields.contactType')}
          />
          <Field name="category" label={t('connector.fields.category')} />
        </FormRow>
        <FormRow cols={1}>
          {/* Outbox-аккаунт: запись chat_external_account, через которую
              идёт интеграция. Создаётся автоматически в backend.create()
              при заполнении external_account_id; здесь показываем "куда
              привязан коннектор" — read-only, не computed. */}
          <Field
            name="outbox_account_id"
            label={t('connector.fields.outboxAccount', 'Outbox account')}
            readOnly
          />
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="connection">
        {/* Подключение */}
        <FormTab
          name="connection"
          label={t('connector.tabs.connection')}
          icon={<IconLink size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Правила работы — справка, одинаковая для всех типов коннекторов.
            Тело ПУСТОЕ намеренно: контент приходит расширением
            ConnectorRulesTab. Написать <Table>/<Alert> прямо здесь нельзя —
            Form пересобирает детей через getComponentsFromChildren
            (components/Form/utils.tsx), который принимает только layout-
            компоненты из белого списка и <Field> с известным серверу именем;
            ветки else нет, всё остальное молча выбрасывается. */}
        <FormTab
          name="rules"
          label={t('connector.tabs.rules', 'Правила работы')}
          icon={<IconBook size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Руководители */}
        <FormTab
          name="managers"
          label={t('connector.tabs.managers', 'Руководители')}
          icon={<IconUsers size={16} />}>
          <Field
            name="manager_ids"
            label={t('connector.fields.managers', 'Руководители')}>
            <Field name="id" />
            <Field name="name" />
            <Field name="login" />
          </Field>
        </FormTab>

        {/* Webhooks — контент добавляется через WebhookSection расширение */}
        <FormTab
          name="webhooks"
          label={t('connector.tabs.webhooks', 'Webhooks')}
          icon={<IconWebhook size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Авторизация */}
        <FormTab
          name="auth"
          label={t('connector.tabs.auth')}
          icon={<IconKey size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Настройки CRM / лидогенерация */}
        <FormTab
          name="crm"
          label={t('connector.tabs.crm')}
          icon={<IconSettings size={16} />}>
          <FormSection title={t('connector.groups.leadSettings')}>
            <FormRow cols={2}>
              {/* Команда-владелец создаваемых чатов (team-scoped доступ:
                  chat.team_id ← connector.team_id при создании чата). */}
              <Field
                name="team_id"
                label={t('connector.fields.team', 'Команда')}
              />
            </FormRow>
            <FormRow cols={2}>
              <Field name="lead_type" label={t('connector.fields.leadType')} />
              <Field
                name="lead_stage_id"
                label={t('connector.fields.leadStage', 'Lead Stage (default)')}
              />
            </FormRow>
            <FormRow cols={2}>
              <Field
                name="lead_generation"
                label={t(
                  'connector.fields.leadGeneration',
                  'Enable lead generation',
                )}
              />
              <Field
                name="lead_distribution"
                label={t(
                  'connector.fields.leadGenerationDistribution',
                  'Apply routing rules',
                )}
              />
              {/* <Field
                name="lead_set_date_deadline"
                label={t(
                  'connector.fields.leadSetDateDeadline',
                  'Set expected closing date',
                )}
              /> */}
            </FormRow>
          </FormSection>
        </FormTab>

        {/* Правила маршрутизации лидов */}
        <FormTab
          name="routing"
          label={t('connector.tabs.routing', 'Routing rules')}
          icon={<IconFilter size={16} />}>
          <FormSection
            title={t('connector.groups.routingRules', 'Lead routing rules')}>
            <Field
              name="routing_rule_ids"
              label={t('connector.fields.routingRules', 'Routing rules')}>
              <Field name="sequence" />
              <Field name="name" />
              <Field name="field_name" />
              <Field name="condition" />
              <Field name="value" />
              <Field name="user_id" />
              <Field name="team_id" />
              <Field name="active" />
            </Field>
          </FormSection>
        </FormTab>

        {/* История */}
        <FormTab
          name="logs"
          label={t('connector.tabs.logs')}
          icon={<IconHistory size={16} />}>
          <FormSection title={t('connector.groups.lastResponse')}>
            <FormRow cols={1}>
              <Field
                name="last_response"
                label={t('connector.fields.lastResponse')}
              />
            </FormRow>
          </FormSection>

          <FormSection title={t('connector.groups.timestamps')}>
            <FormRow cols={2}>
              <Field
                name="create_datetime"
                label={t('connector.fields.createDate')}
              />
              <Field
                name="update_datetime"
                label={t('connector.fields.writeDate')}
              />
              <Field name="id" />
            </FormRow>
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ConnectorForm;
