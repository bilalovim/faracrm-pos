/**
 * API для пользовательских настроек колонок списков (per-user, per-model).
 *
 * Одна запись column_settings = набор видимых колонок конкретного
 * пользователя для конкретной модели. Правила доступа на бэке отдают
 * только СВОИ строки, поэтому поиск по model_name всегда возвращает
 * настройку текущего пользователя (или ничего).
 */
import { crudApi } from '@/services/api/crudApi';

export interface ColumnSettingDTO {
  id: number;
  model_name: string;
  /** JSON-массив имён полей в порядке отображения. */
  columns: string;
}

const columnSettingsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Получить настройку колонок текущего пользователя для модели.
    // Возвращает одну запись (или null, если пользователь не настраивал).
    getColumnSettings: build.query<ColumnSettingDTO | null, string>({
      query: modelName => ({
        url: '/auto/column_settings/search',
        method: 'POST',
        body: {
          fields: ['id', 'model_name', 'columns'],
          filter: [['model_name', '=', modelName]],
          limit: 1,
        },
      }),
      transformResponse: (response: { data: ColumnSettingDTO[] }) =>
        response.data?.[0] ?? null,
      providesTags: (result, error, modelName) => [
        { type: 'ColumnSettings', id: modelName },
      ],
    }),

    // Создать настройку колонок (user_id проставит бэк дефолтом из сессии).
    createColumnSettings: build.mutation<
      { id: number },
      { model_name: string; columns: string }
    >({
      query: data => ({
        url: '/auto/column_settings',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, data) => [
        { type: 'ColumnSettings', id: data.model_name },
      ],
    }),

    // Обновить существующую настройку.
    updateColumnSettings: build.mutation<
      void,
      { id: number; model_name: string; columns: string }
    >({
      query: ({ id, columns }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'PUT',
        body: { columns },
      }),
      invalidatesTags: (result, error, { model_name }) => [
        { type: 'ColumnSettings', id: model_name },
      ],
    }),

    // Удалить настройку (сброс к колонкам вью по умолчанию).
    deleteColumnSettings: build.mutation<
      void,
      { id: number; model_name: string }
    >({
      query: ({ id }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, { model_name }) => [
        { type: 'ColumnSettings', id: model_name },
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetColumnSettingsQuery,
  useCreateColumnSettingsMutation,
  useUpdateColumnSettingsMutation,
  useDeleteColumnSettingsMutation,
} = columnSettingsApi;
