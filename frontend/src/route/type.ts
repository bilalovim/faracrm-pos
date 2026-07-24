import { ComponentType, ReactNode } from 'react';

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
}
