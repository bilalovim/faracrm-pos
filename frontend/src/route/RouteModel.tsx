import { Route, Routes } from 'react-router-dom';

import { RouteModelProps } from './type';
import { ViewWrapper } from '@/components/ViewWrapper';

export const Model = ({ 
  name, 
  list: List, 
  form: Form, 
  kanban: Kanban,
  gantt: Gantt,
}: RouteModelProps) => {
  return (
    <Routes>
      {/* Формы БЕЗ локального <Suspense>: ленивый чанк формы всплывает до
          единственного <Suspense> в FaraRouters, чтобы на переходе список
          удерживался затемнённым, пока форма грузится (а не подменялся
          локальным полноэкранным спиннером). */}
      <Route path="create/*" element={Form ? <Form /> : null} />
      <Route path=":id/*" element={Form ? <Form /> : null} />
      <Route
        path="/*"
        element={
          List ? (
            <ViewWrapper
              model={name}
              ListComponent={List}
              KanbanComponent={Kanban}
              GanttComponent={Gantt}
            />
          ) : null
        }
      />
    </Routes>
  );
};
