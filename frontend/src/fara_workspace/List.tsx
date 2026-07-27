import type { FaraRecord } from '@/services/api/crudTypes';
import { useTranslation } from 'react-i18next';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';

// Список «Рабочих мест» (цифровых рабочих мест). Обычная generic-таблица:
// имя + набор приложений (app_ids) + порядок/активность. Управление —
// у администратора (ACL workspace=FULL только у system_admin).
export function ViewListWorkspace() {
  const { t } = useTranslation('workspace');

  return (
    <List<FaraRecord> model="workspace" order="asc" sort="sequence">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="app_ids" label={t('fields.app_ids')} />
      <Field name="sequence" label={t('fields.sequence')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

export default ViewListWorkspace;
