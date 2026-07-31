import { ActionIcon, Tooltip } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconBook } from '@tabler/icons-react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { resolveDocKey } from './docsIndex';
import { DocsDrawer } from './DocsDrawer';

/**
 * Кнопка-книга в шапке. Открывает панель документации на статье того раздела,
 * где сейчас находится пользователь (по первому сегменту маршрута / модели).
 */
export function DocsButton() {
  const { t } = useTranslation('docs');
  const [opened, { open, close }] = useDisclosure(false);
  const location = useLocation();

  // Ключ вычисляем при клике (через resolveDocKey в момент рендера drawer'а),
  // но передаём актуальный на текущий момент — location меняется вместе с URL.
  const { key, exact } = resolveDocKey(location.pathname);

  return (
    <>
      <Tooltip label={t('open')} position="bottom" withArrow>
        <ActionIcon
          variant="subtle"
          size="lg"
          radius="md"
          onClick={open}
          aria-label={t('open')}>
          <IconBook size={22} stroke={1.5} />
        </ActionIcon>
      </Tooltip>

      <DocsDrawer
        opened={opened}
        onClose={close}
        initialKey={key}
        initialExact={exact}
      />
    </>
  );
}

export default DocsButton;
