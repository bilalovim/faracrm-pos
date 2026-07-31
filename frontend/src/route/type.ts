import { ComponentType, ReactNode } from 'react';
import { FilterExpression } from '@/services/api/crudTypes';

export interface RouteModelProps {
  name: string;
  list?: ComponentType;
  form?: ComponentType;
  kanban?: ComponentType;
  gantt?: ComponentType;
  icon?: ComponentType;
  children?: ReactNode;
}

export interface ViewFormProps {
  isCreateForm?: boolean;
  /** Форма открыта в попапе — колбэк закрытия модалки. */
  modalClose?: () => void;
  /** Быстрое создание Many2one из попапа: вернуть созданную запись
   *  вызывающему полю (оно подставит её значением). */
  onCreated?: (record: any) => void;
  /** Проброс для попапа создания O2M/M2M (ButtonModalCreate → <Form>). */
  relatedFieldO2M?: string;
  parentFieldName?: string;
  parentForm?: any;
  parentId?: number;
}

/**
 * Пропсы вью-списка. ViewWrapper рендерит список без пропсов, поэтому поле
 * опционально — вью лишь пробрасывает его в <List> (напр. при вложенном
 * использовании вне роутера).
 */
export interface ViewListProps {
  /** Необязательный доп. фильтр, пробрасывается в <List>. */
  filter?: FilterExpression;
}

/** Пропсы вью-канбана (по аналогии с ViewListProps). */
export interface ViewKanbanProps {
  filter?: FilterExpression;
}
