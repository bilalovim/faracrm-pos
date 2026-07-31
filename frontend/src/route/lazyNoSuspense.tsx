import { ComponentType, useEffect, useState } from 'react';
import { Center, Loader } from '@mantine/core';

const DefaultFallback = () => (
  <Center h="100%" mih={200}>
    <Loader size="lg" />
  </Center>
);

/**
 * Замена React.lazy БЕЗ Suspense.
 *
 * ЗАЧЕМ. React 19 троттлит раскрытие Suspense-заглушки: внутренний
 * FALLBACK_THROTTLE_MS = 300 мс. Даже если чанк готов за ~20 мс, fallback
 * висит ~300 мс — раскрытие «пачкуется», чтобы не мигать (facebook/react
 * #31819, #31697). На React 18 такого нет. Отсюда регресс навигации 170→420 мс.
 *
 * РЕШЕНИЕ. Грузим чанк вручную (динамический import + useState) и прячем
 * лоадер сразу, как только модуль загружен — никакого Suspense, никакого
 * троттла. Модуль кешируется в замыкании, поэтому повторный вход в раздел
 * рендерится мгновенно, без мигания.
 *
 * ВАЖНО. Возвращённый компонент НЕ suspend'ится, поэтому любые внешние
 * <Suspense> вокруг него становятся инертными (их заглушка не показывается) —
 * их можно оставить как есть.
 *
 * Как и React.lazy, вызывать нужно ОДИН раз на модуле (не внутри рендера),
 * иначе каждый рендер = новый компонент → размонтирование/перемонтирование.
 */
export function lazyNoSuspense<P extends object>(
  factory: () => Promise<{ default: ComponentType<P> }>,
  Fallback: ComponentType = DefaultFallback,
): ComponentType<P> {
  // Кеш на уровне модуля (замыкание): один чанк грузится один раз.
  let cached: ComponentType<P> | null = null;
  let pending: Promise<ComponentType<P>> | null = null;

  return function LazyNoSuspense(props: P) {
    // Если чанк уже загружен (повторный вход) — стартуем сразу с компонентом.
    // ВАЖНО: () => cached, а НЕ cached. useState трактует переданную функцию
    // как ленивый инициализатор и ВЫЗЫВАЕТ её; компонент — это функция, поэтому
    // useState(cached) вызвал бы компонент и положил в state JSX-объект →
    // <Loaded/> стал бы объектом → React error #130.
    const [Loaded, setLoaded] = useState<ComponentType<P> | null>(() => cached);

    useEffect(() => {
      if (cached) {
        if (!Loaded) setLoaded(() => cached);
        return;
      }
      let alive = true;
      if (!pending) {
        pending = factory()
          .then(m => (cached = m.default))
          .catch(err => {
            pending = null; // разрешаем повторную попытку при следующем маунте
            throw err;
          });
      }
      pending
        .then(comp => {
          if (alive) setLoaded(() => comp);
        })
        .catch(err => {
          // eslint-disable-next-line no-console
          console.error('[lazyNoSuspense] не удалось загрузить чанк:', err);
        });
      return () => {
        alive = false;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return Loaded ? <Loaded {...props} /> : <Fallback />;
  };
}
