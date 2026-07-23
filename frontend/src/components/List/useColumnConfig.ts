/**
 * useColumnConfig — per-user, per-model выбор колонок списка.
 *
 * Источник истины для рендера — `selected` (итоговый порядок видимых
 * колонок). По умолчанию это колонки вью (`defaultVisible`, из <Field>).
 * Если пользователь настроил колонки — берём его сохранённый набор с
 * сервера (модель column_settings).
 *
 * Живые правки применяются мгновенно (`setDraft` → таблица перестраивается),
 * а на сервер пишутся один раз при закрытии меню (`persistIfDirty`) —
 * так нет гонок create-дубликатов и лишних запросов на каждый чек-бокс.
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import {
  useGetColumnSettingsQuery,
  useCreateColumnSettingsMutation,
  useUpdateColumnSettingsMutation,
  useDeleteColumnSettingsMutation,
} from './columnSettingsApi';

export interface ColumnConfig {
  /** Итоговый список видимых колонок в порядке отображения. */
  selected: string[];
  /** Отличается ли текущий набор от колонок вью по умолчанию. */
  isCustom: boolean;
  /** Идёт первичная загрузка настройки с сервера. */
  isLoading: boolean;
  /** Живое изменение выбора (мгновенно перестраивает таблицу). */
  setDraft: (cols: string[]) => void;
  /** Записать текущий выбор на сервер, если он менялся с прошлого раза. */
  persistIfDirty: () => void;
  /** Вернуть колонки вью по умолчанию (удаляет строку на сервере). */
  reset: () => void;
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

export function useColumnConfig(
  model: string,
  defaultVisible: string[],
): ColumnConfig {
  const { data: row, isLoading } = useGetColumnSettingsQuery(model);
  const [createSettings] = useCreateColumnSettingsMutation();
  const [updateSettings] = useUpdateColumnSettingsMutation();
  const [deleteSettings] = useDeleteColumnSettingsMutation();

  // Колонки, сохранённые пользователем (или null, если не настраивал).
  const serverCols = useMemo<string[] | null>(() => {
    if (!row?.columns) return null;
    try {
      const parsed = JSON.parse(row.columns);
      if (!Array.isArray(parsed)) return null;
      return parsed.filter((x): x is string => typeof x === 'string');
    } catch {
      return null;
    }
  }, [row?.columns]);

  // Несохранённые правки текущей сессии. null = «правок нет».
  const [draft, setDraftState] = useState<string[] | null>(null);

  // id строки на сервере: из кеша ИЛИ из ответа create — чтобы второе
  // сохранение делало update, а не плодило дубликаты до рефетча.
  const [localRowId, setLocalRowId] = useState<number | undefined>(undefined);
  const rowId = row?.id ?? localRowId;

  const dirtyRef = useRef(false);

  const selected = draft ?? serverCols ?? defaultVisible;
  const isCustom = !arraysEqual(selected, defaultVisible);

  const setDraft = useCallback((cols: string[]) => {
    dirtyRef.current = true;
    setDraftState(cols);
  }, []);

  const persistIfDirty = useCallback(async () => {
    if (!dirtyRef.current || draft == null) return;
    dirtyRef.current = false;

    // Набор снова равен дефолту вью — отдельную запись не храним.
    if (arraysEqual(draft, defaultVisible)) {
      if (rowId) {
        const id = rowId;
        setLocalRowId(undefined);
        await deleteSettings({ id, model_name: model });
      }
      return;
    }

    const columns = JSON.stringify(draft);
    if (rowId) {
      await updateSettings({ id: rowId, model_name: model, columns });
    } else {
      const res = await createSettings({ model_name: model, columns })
        .unwrap()
        .catch(() => null);
      if (res?.id) setLocalRowId(res.id);
    }
  }, [
    draft,
    defaultVisible,
    rowId,
    model,
    createSettings,
    updateSettings,
    deleteSettings,
  ]);

  const reset = useCallback(async () => {
    dirtyRef.current = false;
    setDraftState(defaultVisible); // мгновенно вернуть дефолтные колонки
    const id = rowId;
    setLocalRowId(undefined);
    if (id) await deleteSettings({ id, model_name: model });
  }, [defaultVisible, rowId, model, deleteSettings]);

  return {
    selected,
    isCustom,
    isLoading,
    setDraft,
    persistIfDirty,
    reset,
  };
}
