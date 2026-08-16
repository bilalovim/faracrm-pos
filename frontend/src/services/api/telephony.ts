// Copyright 2025 FARA CRM
// Telephony API — сводка по звонкам для экрана «Звонки».
//
// Сам реестр звонков читается обычным авто-CRUD (/auto/call/search) — экран
// это стандартный list/form модели `call`. Здесь только аналитика, которую
// нельзя посчитать по странице таблицы.
//
// Инжектим эндпоинт в общий crudApi (как chat.ts), чтобы не трогать store.

import { crudApi } from './crudApi';
import { FilterExpression } from './crudTypes';

export interface CallsStatsParams {
  /** Фильтр таблицы (тот же, что уходит в /auto/call/search). */
  filter?: FilterExpression;
}

export interface CallsStats {
  total: number;
  answered: number;
  missed: number;
  incoming: number;
  outgoing: number;
}

const telephonyApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getCallsStats: build.query<CallsStats, CallsStatsParams>({
      query: ({ filter }) => ({
        method: 'POST',
        url: 'telephony/calls/stats',
        body: { filter },
      }),
      // Сводка обязана меняться вместе с таблицей: правка/создание звонка
      // инвалидирует список модели — тем же тегом инвалидируется и она.
      providesTags: [{ type: 'call', id: 'LIST' }],
    }),
  }),
});

export const { useGetCallsStatsQuery } = telephonyApi;
