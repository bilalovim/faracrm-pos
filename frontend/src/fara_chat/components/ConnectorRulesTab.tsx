import { Alert, Badge, Code, Stack, Table, Text } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { registerExtension } from '@/shared/extensions';

/**
 * Вкладка «Правила работы» формы коннектора.
 *
 * Справка о том, как коннектор обрабатывает ВХОДЯЩИЕ сообщения: куда попадёт
 * сообщение, заведётся ли партнёр и лид. Правила одинаковы для ВСЕХ типов
 * коннекторов (логика живёт в общей входящей стратегии
 * backend/base/crm/chat/strategies/strategy.py::_process_incoming_message),
 * поэтому расширение регистрируется БЕЗ гейта по form.values.type — в отличие
 * от per-type расширений вида ViewFormConnector<Тип>.
 *
 * ПОЧЕМУ ЭТО РАСШИРЕНИЕ, А НЕ ПРОСТО JSX ВНУТРИ <FormTab> В ConnectorForm:
 * Form пересобирает всё дерево детей через getComponentsFromChildren
 * (components/Form/utils.tsx), и там ровно две принимающие ветки — layout-
 * компонент из белого списка LAYOUT_COMPONENTS либо <Field> с именем,
 * известным серверу. Ветки else нет: любой другой узел МОЛЧА выбрасывается.
 * Поэтому <Table>/<Alert>, написанные прямо в <FormTab>, не отрендерились бы
 * (живой пример такого мёртвого кода — <Alert> в fara_attachments/Form.tsx).
 * Расширения же рендерятся напрямую в TabContent (Form/Layout/FormTabs.tsx),
 * минуя эту фильтрацию, — здесь произвольный JSX работает.
 *
 * ВНИМАНИЕ ПРИ ПРАВКЕ ЛОГИКИ: таблица описывает поведение бэкенда и может с ним
 * разъехаться — она не генерируется из кода. Меняете _process_incoming_message
 * — поправьте и здесь.
 */
export function ConnectorRulesTab() {
  const { t } = useTranslation('chat');

  const rows: {
    event: string;
    link: string;
    target: string;
    lead: string;
    accent?: boolean;
  }[] = [
    {
      event: t(
        'connector.rules.rows.newClient.event',
        'Незнакомый адрес пишет первым',
      ),
      link: t('connector.rules.by.none', '—'),
      target: t(
        'connector.rules.rows.newClient.target',
        'Создаётся партнёр, открывается его чат',
      ),
      lead: t('connector.rules.lead.yes', 'Партнёр и лид'),
    },
    {
      event: t(
        'connector.rules.rows.clientReplies.event',
        'Клиент отвечает на наше письмо',
      ),
      link: t('connector.rules.by.thread', 'по переписке'),
      target: t(
        'connector.rules.rows.clientReplies.target',
        'В тот чат, из которого писали',
      ),
      lead: t('connector.rules.lead.byRules', 'По правилам лидогенерации'),
    },
    {
      event: t(
        'connector.rules.rows.clientNew.event',
        'Знакомый пишет заново, не ответом',
      ),
      link: t('connector.rules.by.address', 'по адресу'),
      target: t('connector.rules.rows.clientNew.target', 'Его чат'),
      lead: t('connector.rules.lead.byRules', 'По правилам лидогенерации'),
    },
    {
      event: t(
        'connector.rules.rows.weWriteClient.event',
        'Оператор пишет клиенту первым',
      ),
      link: t('connector.rules.by.none', '—'),
      target: t(
        'connector.rules.rows.weWriteClient.target',
        'Ответ придёт в этот же чат',
      ),
      lead: '—',
    },
    {
      event: t(
        'connector.rules.rows.staffCold.event',
        'Сотрудник пишет на общий адрес, переписки с ним ещё нет',
      ),
      link: t('connector.rules.by.none', '—'),
      target: t(
        'connector.rules.rows.staffCold.target',
        'Ничего не происходит — сообщение пропускается',
      ),
      lead: t('connector.rules.lead.no', 'Ничего не создаётся'),
      accent: true,
    },
    {
      event: t(
        'connector.rules.rows.staffReplies.event',
        'Мы написали сотруднику, он ответил',
      ),
      link: t('connector.rules.by.thread', 'по переписке'),
      target: t(
        'connector.rules.rows.staffReplies.target',
        'В тот чат, из которого писали — даже если чатов с ним несколько',
      ),
      lead: t('connector.rules.lead.no', 'Ничего не создаётся'),
      accent: true,
    },
  ];

  return (
    <Stack gap="md">
      <Alert
        icon={<IconInfoCircle size={16} />}
        title={t('connector.rules.title', 'Как обрабатывается входящее')}
        color="blue">
        <Text size="sm">
          {t(
            'connector.rules.summary',
            'Если сообщение — ответ на наше, оно ложится в тот чат, из которого мы писали. Иначе чат ищется по адресу отправителя. Если и переписки нет — незнакомый адрес становится клиентом, а адрес нашего сотрудника пропускается.',
          )}
        </Text>
      </Alert>

      <Table striped withTableBorder withColumnBorders>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('connector.rules.col.event', 'Событие')}</Table.Th>
            <Table.Th>
              {t('connector.rules.col.by', 'Как определяем чат')}
            </Table.Th>
            <Table.Th>
              {t('connector.rules.col.target', 'Куда попадёт')}
            </Table.Th>
            <Table.Th>
              {t('connector.rules.col.lead', 'Партнёр / лид')}
            </Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r, i) => (
            <Table.Tr key={i}>
              <Table.Td>
                <Text size="sm" fw={r.accent ? 600 : 400}>
                  {r.event}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {r.link}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{r.target}</Text>
              </Table.Td>
              <Table.Td>
                <Badge
                  size="sm"
                  variant="light"
                  color={
                    r.lead === '—'
                      ? 'gray'
                      : r.lead.includes('лид')
                        ? 'green'
                        : 'gray'
                  }>
                  {r.lead}
                </Badge>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Text size="xs" c="dimmed">
        {t(
          'connector.rules.note',
          'Сотрудник — это тот, чей адрес заведён контактом пользователя CRM. Партнёр и лид на сотрудника не заводятся никогда. Адрес коннектора общий, поэтому написавший на него сотрудник не адресуется никому конкретному — переписку с ним нужно начинать со стороны CRM.',
        )}
      </Text>
      <Text size="xs" c="dimmed">
        {t(
          'connector.rules.noteThread',
          '«По переписке» работает только у почты: письмо несёт в заголовках отметку, на что оно отвечает. У мессенджеров этого нет и не нужно — там с человеком один диалог, и его задаёт сама площадка.',
        )}
      </Text>
      <Text size="xs" c="dimmed">
        {t('connector.rules.contactTypeHint', 'Тип контакта коннектора:')}{' '}
        <Code>contact_type_id</Code>{' '}
        {t(
          'connector.rules.contactTypeHint2',
          '— по нему адрес входящего сопоставляется с контактом.',
        )}
      </Text>
    </Stack>
  );
}

// displayName обязателен: registerExtension дедупит в dev по displayName||name,
// а прод-минификация уничтожает .name (см. комментарий в shared/extensions).
ConnectorRulesTab.displayName = 'ConnectorRulesTab';

// БЕЗ гейта по типу и БЕЗ списка полей: вкладка одинакова для всех коннекторов
// (правила общие, живут в chat/strategies/strategy.py), а своих полей модели у
// неё нет — только справка. Поэтому регистрируем здесь, в общем fara_chat, а не
// в per-type модуле: fara_chat_* каждый гейтится на form.values.type и показал
// бы вкладку только своему типу.
registerExtension('chat_connector', ConnectorRulesTab, 'inside:FormTab:rules');
