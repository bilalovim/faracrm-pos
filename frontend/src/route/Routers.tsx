import { Model } from './RouteModel';
import { Fara } from './Fara';
import { lazyNoSuspense } from './lazyNoSuspense';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { modelsConfig } from '@/config/models';
import { GenericList, GenericForm } from '@/components/Generic';
import { Loader, Center } from '@mantine/core';
import type { RootState } from '@/store/store';

// Ленивая загрузка кастомных страниц (без Suspense — см. lazyNoSuspense)
const ChatPageComponent = lazyNoSuspense(
  () => import('@/fara_chat/components/ChatPage'),
);

// Wrapper для ChatPage с props из Redux
const ChatPage = () => {
  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';
  const currentUserId = session?.user_id?.id || 0;
  const currentUserName = session?.user_id?.name || '';

  if (!token || !currentUserId) {
    return <PageLoader />;
  }

  return (
    <ChatPageComponent
      token={token}
      currentUserId={currentUserId}
      currentUserName={currentUserName}
    />
  );
};

// Компонент загрузки
const PageLoader = () => (
  <Center h="100%">
    <Loader size="lg" />
  </Center>
);

// Проверка наличия views
export const hasKanban = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.kanban;
};

export const hasGantt = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.gantt;
};

// Предварительно создаём ленивые компоненты один раз при инициализации модуля
// ВАЖНО: lazyNoSuspense() нельзя вызывать внутри рендер-функции — каждый вызов
// будет новым компонентом → размонтирование старого и монтирование заново
const modelComponents = Object.fromEntries(
  Object.entries(modelsConfig).map(([modelName, config]) => {
    const ListComponent = config.list
      ? lazyNoSuspense(config.list)
      : () => <GenericList model={modelName} fields={config.fields} />;

    const FormComponent = config.form
      ? lazyNoSuspense(config.form)
      : () => <GenericForm model={modelName} fields={config.fields} />;

    const KanbanComponent = config.kanban
      ? lazyNoSuspense(config.kanban)
      : undefined;

    const GanttComponent = config.gantt
      ? lazyNoSuspense(config.gantt)
      : undefined;

    return [modelName, { ListComponent, FormComponent, KanbanComponent, GanttComponent }];
  }),
);

// Экспорт для использования в других компонентах
export const getModelViews = (modelName: string) => {
  const components = modelComponents[modelName];
  if (!components) return null;

  return {
    list: components.ListComponent,
    form: components.FormComponent,
    kanban: components.KanbanComponent,
    gantt: components.GanttComponent,
  };
};

// Компонент с динамическими роутами моделей
const ModelRoutes = () => (
  <Fara>
    {Object.entries(modelComponents).map(([modelName, { ListComponent, FormComponent, KanbanComponent, GanttComponent }]) => (
      <Model
        key={modelName}
        name={modelName}
        list={ListComponent}
        form={FormComponent}
        kanban={KanbanComponent}
        gantt={GanttComponent}
      />
    ))}
  </Fara>
);

// Редирект на домашнюю страницу пользователя
const HomeRedirect = () => {
  const session = useSelector((state: RootState) => state.auth.session);
  const homePage = session?.user_id?.home_page;

  // Валидация: должен быть относительный маршрут (начинается с /)
  if (homePage && homePage.startsWith('/') && !homePage.includes('://')) {
    return <Navigate to={homePage} replace />;
  }

  return null;
};

// Главный роутер с кастомными страницами + модели
const FaraRouters = () => (
  <Routes>
    {/* Домашняя страница пользователя */}
    <Route path="/" element={<HomeRedirect />} />

    {/* Кастомные страницы (лоадер внутри ChatPage/ChatPageComponent) */}
    <Route path="chat/*" element={<ChatPage />} />

    {/* Все остальные роуты - модели */}
    <Route path="*" element={<ModelRoutes />} />
  </Routes>
);

export default FaraRouters;
