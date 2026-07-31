import { useEffect, useMemo, useState } from 'react';
import {
  Drawer,
  Group,
  TextInput,
  Button,
  Text,
  Box,
  ThemeIcon,
} from '@mantine/core';
import { IconBook2, IconSearch, IconArrowLeft } from '@tabler/icons-react';
import { useMediaQuery } from '@mantine/hooks';
import { useTranslation } from 'react-i18next';
import {
  getArticle,
  getGroupedArticles,
  type DocArticle,
} from './docsIndex';
import { DocsArticleView } from './DocsArticleView';
import classes from './Docs.module.css';

interface DocsDrawerProps {
  opened: boolean;
  onClose: () => void;
  /** Ключ статьи для текущего маршрута (контекстная справка). */
  initialKey: string;
  /** Есть ли у текущего маршрута собственная статья (иначе показан обзор). */
  initialExact: boolean;
}

export function DocsDrawer({
  opened,
  onClose,
  initialKey,
  initialExact,
}: DocsDrawerProps) {
  const { t } = useTranslation('docs');
  const isMobile = useMediaQuery('(max-width: 48em)');

  const [selectedKey, setSelectedKey] = useState(initialKey);
  const [search, setSearch] = useState('');
  const [showFallbackHint, setShowFallbackHint] = useState(false);
  // Мобильный мастер-деталь: показываем либо оглавление, либо статью.
  const [mobileView, setMobileView] = useState<'nav' | 'article'>('article');

  // При каждом открытии — синхронизируемся с текущим маршрутом.
  useEffect(() => {
    if (opened) {
      setSelectedKey(initialKey);
      setShowFallbackHint(!initialExact);
      setMobileView('article');
      setSearch('');
    }
  }, [opened, initialKey, initialExact]);

  const groups = useMemo(() => {
    const buckets = getGroupedArticles();
    const q = search.trim().toLowerCase();
    if (!q) return buckets;
    return buckets
      .map(b => ({
        ...b,
        articles: b.articles.filter(
          a =>
            a.title.toLowerCase().includes(q) ||
            a.summary.toLowerCase().includes(q),
        ),
      }))
      .filter(b => b.articles.length > 0);
  }, [search]);

  const article: DocArticle | undefined = getArticle(selectedKey);

  const handleSelect = (key: string) => {
    setSelectedKey(key);
    setShowFallbackHint(false);
    if (isMobile) setMobileView('article');
  };

  const handleSearchChange = (value: string) => {
    setSearch(value);
    // На мобильном при вводе показываем список результатов.
    if (isMobile && value) setMobileView('nav');
  };

  const navPane = (
    <Box className={classes.nav}>
      {groups.length === 0 ? (
        <Text c="dimmed" size="sm" p="xs">
          {t('searchEmpty')}
        </Text>
      ) : (
        groups.map(bucket => (
          <div key={bucket.group}>
            <div className={classes.groupLabel}>{t(bucket.labelKey)}</div>
            {bucket.articles.map(a => (
              <button
                key={a.key}
                type="button"
                title={a.summary}
                className={
                  a.key === selectedKey
                    ? `${classes.navItem} ${classes.navItemActive}`
                    : classes.navItem
                }
                onClick={() => handleSelect(a.key)}>
                {a.title}
              </button>
            ))}
          </div>
        ))
      )}
    </Box>
  );

  const contentPane = (
    <Box className={classes.content}>
      {isMobile && (
        <Button
          variant="subtle"
          size="compact-sm"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => setMobileView('nav')}
          mb="xs">
          {t('allTopics')}
        </Button>
      )}

      {showFallbackHint && (
        <Box className={classes.hint}>
          <Text size="sm" c="dimmed">
            {t('noArticleHint')}
          </Text>
        </Box>
      )}

      {article ? (
        <DocsArticleView article={article} />
      ) : (
        <Text c="dimmed">{t('noArticleHint')}</Text>
      )}
    </Box>
  );

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size={isMobile ? '100%' : 'min(960px, 100vw)'}
      title={
        <Group gap="xs">
          <ThemeIcon variant="light" radius="md" size="md">
            <IconBook2 size={18} />
          </ThemeIcon>
          <Text fw={600}>{t('title')}</Text>
        </Group>
      }
      overlayProps={{ backgroundOpacity: 0.35, blur: 2 }}
      styles={{
        content: { display: 'flex', flexDirection: 'column' },
        body: {
          flex: 1,
          minHeight: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
        },
      }}>
      <div className={classes.root}>
        <div className={classes.toolbar}>
          <TextInput
            value={search}
            onChange={e => handleSearchChange(e.currentTarget.value)}
            placeholder={t('searchPlaceholder')}
            leftSection={<IconSearch size={16} />}
            size="sm"
          />
        </div>

        <div className={classes.body}>
          {isMobile ? (
            mobileView === 'nav' ? (
              navPane
            ) : (
              contentPane
            )
          ) : (
            <>
              {navPane}
              {contentPane}
            </>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export default DocsDrawer;
