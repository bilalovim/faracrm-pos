/**
 * Расширение формы Sale из модуля contract.
 *
 * Добавляет поле `contract_id` (Many2one на Contract) в табе
 * «Доп. Информация» формы заказа. Backend-сторона — миксин
 * SaleContractMixin (см. backend/base/crm/contract/models/sale_ext.py),
 * который через @extend(Sale) добавляет FK-колонку contract_id в
 * таблицу sales.
 *
 * Подключение: см. fara_contract/index.ts (side-effect импорт этого
 * файла) и config/models.ts (modelsConfig.sales.extensions).
 *
 * Аналог chat_telegram / chat_avito / chat_email, которые таким же
 * способом расширяют форму ChatConnector.
 */

import { FieldMany2one } from '@/components/Form/Fields/FieldMany2one';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconFileInvoice } from '@tabler/icons-react';
import { registerExtension } from '@/shared/extensions';
import { Triplet } from '@/services/api/crudTypes';

/**
 * домен для contract_id, показываем только договоры того же
 * контрагента и той же компании, что выбраны в заказе.
 */
const getContractFilter = (values: Record<string, any>): Triplet[] => {
  const domain: Triplet[] = [];
  const partnerId = values?.partner_id?.id;
  const companyId = values?.company_id?.id;
  if (partnerId) domain.push(['partner_id', '=', partnerId]);
  if (companyId) domain.push(['company_id', '=', companyId]);
  return domain;
};

export function ViewFormSaleContract() {
  // Внутри extension'а dispatch <Field> → конкретный компонент НЕ
  // работает: getComponentsFromChildren обрабатывает только children
  // корневой <Form>, а extension рендерится как готовый React-узел
  // внутри TabContent (см. FormTabs.tsx). Поэтому используем прямой
  // импорт компонента — так же делают chat_telegram/avito/email
  // (везде <FieldChar>, <FieldBoolean> напрямую, а не <Field>).
  return (
    <FormSection title="Договор" icon={<IconFileInvoice size={18} />}>
      <FormRow cols={2}>
        <FieldMany2one
          name="contract_id"
          label="Договор"
          filter={getContractFilter}
        />
      </FormRow>
    </FormSection>
  );
}

// Регистрируем расширение для модели `sales`. Позиция — после контента
// таба "info" (в нём уже лежат company_id/active/origin); смысловое
// место для договора — рядом с этими «дополнительными» полями.
//
// Список fields обязателен: Form.tsx при сборе fieldsList объединяет
// поля из children с полями из getExtensionFields(model), иначе
// contract_id не попадёт в запрос /sales/{id} и /default_values,
// а Many2one не сможет отрисоваться (нет metadata).
registerExtension('sales', ViewFormSaleContract, 'after:FormTab:info', [
  'contract_id',
]);
