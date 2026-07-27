import { Suspense, lazy, useMemo } from 'react';
import LoadingScreen from '@components/LoadingScreen/LoadingScreen';
import { useSelector } from 'react-redux';
import { selectIsLoggedIn } from '@/slices/authSlice';
import { SavedFiltersPreloader } from '@/components/SearchFilter';
import { LayoutThemeProvider, ModernLayout } from '@/components/ModernTheme';

// Компонент выбора layout в зависимости от темы.
//
// ВРЕМЕННО: классическая тема (ProtectedLayout) СКРЫТА у всех — рендерим
// только ModernLayout. Импорты ProtectedLayout и useLayoutTheme здесь убраны;
// сам ProtectedLayout и его инфраструктура (NavbarMenu, SidebarContext/
// SidebarToggle) в коде сохранены, просто больше не используются из точки
// входа. LayoutThemeProvider оставлен — контекст темы всё ещё нужен UserMenu.
//
// Чтобы вернуть classic — восстановить импорты и ветвление:
//   import ProtectedLayout from './ProtectedLayout/ProtectedLayout';
//   import { useLayoutTheme } from '@/components/ModernTheme';
//   const { layoutTheme } = useLayoutTheme();
//   if (layoutTheme === 'classic') return (<><SavedFiltersPreloader/><ProtectedLayout/></>);
function ThemedLayout() {
  return (
    <>
      <SavedFiltersPreloader />
      <ModernLayout />
    </>
  );
}

export function Layout() {
  const authenticated = useSelector(selectIsLoggedIn);
  const AppLayout = useMemo(() => {
    if (authenticated) {
      // Возвращаем компонент с провайдером темы
      return () => (
        <LayoutThemeProvider>
          <ThemedLayout />
        </LayoutThemeProvider>
      );
    }
    return lazy(() => import('@/fara_base/auth/SignIn'));
  }, [authenticated]);

  return (
    <Suspense
      fallback={
        <div className="flex flex-auto flex-col h-[100vh]">
          <LoadingScreen />
        </div>
      }>
      <AppLayout />
    </Suspense>
  );
}
