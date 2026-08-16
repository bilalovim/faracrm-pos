// Copyright 2025 FARA CRM
// Экран «Звонки» — обычные list/form модели `call` (как у остальных моделей).
//
// Раньше это была кастомная страница CallsPage со своей таблицей, фильтрами и
// пагинацией. Теперь список даёт общий <List> (колонки настраиваются, фильтры
// общие, сохранённые фильтры работают), а телефонное оформление колонок живёт
// в Cell-компонентах (CallCells). Сводка над таблицей считается на бэке по
// текущему фильтру — см. CallStats.

import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import RelationCell from '@/components/ListCells/RelationCell';
import { DateTimeCell } from '@/components/ListCells';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { ViewFormProps, ViewListProps } from '@/route/type';
import { FilterExpression } from '@/services/api/crudTypes';
import {
  IconPhone,
  IconUsers,
  IconFileText,
  IconPlayerPlay,
} from '@tabler/icons-react';
import {
  CallDirectionCell,
  CallDispositionCell,
  CallDurationCell,
  CallInternalCell,
  CallRecordCell,
  CallRecord,
} from './CallCells';
import { CallStats } from './CallStats';
import { mergeFilters } from '@/components/SearchFilter/useFilteredSearchQuery';

// Мягко удалённые звонки (active=false) в реестр не показываем — тот же
// фильтр уходит и в сводку, чтобы цифры совпадали с таблицей.
const ACTIVE_ONLY: FilterExpression = [['active', '=', true]];

// === List ===
export function ViewListCall({ filter }: ViewListProps = {}) {
  const { t } = useTranslation('chat');
  // Один и тот же фильтр для таблицы и для сводки — иначе цифры в плашках
  // считались бы не по той выборке, что видно в списке.
  const listFilter = mergeFilters(ACTIVE_ONLY, filter);

  return (
    <>
      <CallStats filter={listFilter} />
      <List<CallRecord>
        model="call"
        order="desc"
        sort="started_at"
        filter={listFilter}
        massActions={false}>
        <Field
          name="started_at"
          label={t('calls.time', 'Время')}
          render={value => <DateTimeCell value={value} />}
        />
        <Field
          name="direction"
          label={t('calls.direction', 'Направление')}
          fields={['disposition']}
          render={(_value, record) => <CallDirectionCell record={record} />}
        />
        <Field
          name="number_from"
          label={t('calls.numberFrom', 'Откуда')}
          render={value => value || '—'}
        />
        <Field
          name="number_to"
          label={t('calls.numberTo', 'Куда')}
          render={value => value || '—'}
        />
        <Field
          name="phone_number_id"
          label={t('calls.line', 'Наша линия')}
          render={value => <RelationCell value={value} model="phone_number" />}
        />
        <Field
          name="partner_id"
          label={t('calls.partner', 'Партнёр')}
          render={value => <RelationCell value={value} model="partners" />}
        />
        <Field
          name="lead_id"
          label={t('calls.lead', 'Лид')}
          render={value => <RelationCell value={value} model="leads" />}
        />
        <Field
          name="disposition"
          label={t('calls.disposition', 'Статус')}
          render={value => <CallDispositionCell value={value} />}
        />
        <Field
          name="is_internal"
          label={t('calls.internalShort', 'Внутр.')}
          render={value => <CallInternalCell value={value} />}
        />
        <Field
          name="duration_talk"
          label={t('calls.duration', 'Длит.')}
          render={value => <CallDurationCell value={value} />}
        />
        <Field
          name="record_id"
          label={t('calls.record', 'Запись')}
          render={(_value, record) => <CallRecordCell record={record} />}
        />
        {/* Запрашиваются, но по умолчанию скрыты — можно включить в меню колонок */}
        <Field name="connector_id" label={t('fields.connector_id')} hidden />
        <Field
          name="duration"
          label={t('calls.durationTotal', 'Всего, сек')}
          hidden
        />
        <Field
          name="uniqueid"
          label={t('calls.uniqueid', 'ID звонка')}
          hidden
        />
      </List>
    </>
  );
}

// === Form ===
export function ViewFormCall(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form<CallRecord> model="call" {...props}>
      <FormSection
        title={t('calls.groups.call', 'Звонок')}
        icon={<IconPhone size={18} />}>
        <FormRow cols={2}>
          <Field name="started_at" label={t('calls.time', 'Время')} />
          <Field name="direction" label={t('calls.direction', 'Направление')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="disposition" label={t('calls.disposition', 'Статус')} />
          <Field
            name="is_internal"
            label={t('calls.internal', 'Внутренний')}
          />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="duration"
            label={t('calls.durationTotal', 'Всего, сек')}
          />
          <Field
            name="duration_talk"
            label={t('calls.durationTalk', 'Разговор, сек')}
          />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('calls.groups.parties', 'Стороны')}
        icon={<IconUsers size={18} />}>
        <FormRow cols={2}>
          <Field name="number_from" label={t('calls.numberFrom', 'Откуда')} />
          <Field name="number_to" label={t('calls.numberTo', 'Куда')} />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="phone_number_id"
            label={t('calls.line', 'Наша линия')}
          />
          <Field name="partner_id" label={t('calls.partner', 'Партнёр')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="lead_id" label={t('calls.lead', 'Лид')} />
          <Field name="connector_id" label={t('fields.connector_id')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('calls.groups.record', 'Запись разговора')}
        icon={<IconPlayerPlay size={18} />}>
        <Field name="record_id" label={t('calls.record', 'Запись')} />
      </FormSection>

      <FormSection
        title={t('calls.groups.raw', 'Служебное')}
        icon={<IconFileText size={18} />}>
        <FormRow cols={2}>
          <Field name="uniqueid" label={t('calls.uniqueid', 'ID звонка')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
        <Field name="raw" label={t('calls.raw', 'Сырой CDR')} />
      </FormSection>
    </Form>
  );
}
