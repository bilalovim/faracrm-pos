import { Tabs, Title, Text, Box } from '@mantine/core';
import {
  IconFileText,
  IconVideo,
  IconPlayerPlayFilled,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { remarkCallouts } from './remarkCallouts';
import type { DocArticle, DocVideo } from './docsIndex';
import classes from './Docs.module.css';

// Внешние ссылки открываем в новой вкладке с безопасным rel.
const markdownComponents: Components = {
  a({ href, children }) {
    const external = !!href && /^https?:\/\//i.test(href);
    return external ? (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ) : (
      <a href={href}>{children}</a>
    );
  },
};

const remarkPlugins = [remarkGfm, remarkCallouts];

/** Одна карточка видео. Пустой url → плейсхолдер «готовится». */
function VideoCard({ video }: { video: DocVideo }) {
  const { t } = useTranslation('docs');
  const hasUrl = !!video.url;

  const inner = (
    <>
      <Box className={classes.videoIcon}>
        <IconPlayerPlayFilled size={18} />
      </Box>
      <Box className={classes.videoMeta}>
        <div className={classes.videoTitle}>{video.title}</div>
        <div className={classes.videoSub}>
          {hasUrl ? video.duration || t('videoWatch') : t('videoSoon')}
        </div>
      </Box>
    </>
  );

  if (!hasUrl) {
    return (
      <div className={`${classes.videoCard} ${classes.videoSoon}`}>{inner}</div>
    );
  }

  return (
    <a
      className={classes.videoCard}
      href={video.url}
      target="_blank"
      rel="noopener noreferrer">
      {inner}
    </a>
  );
}

export function DocsArticleView({ article }: { article: DocArticle }) {
  const { t } = useTranslation('docs');

  return (
    <>
      <Title order={2} size="h3" mb="sm">
        {article.title}
      </Title>

      <Tabs defaultValue="text" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="text" leftSection={<IconFileText size={16} />}>
            {t('tabText')}
          </Tabs.Tab>
          <Tabs.Tab value="video" leftSection={<IconVideo size={16} />}>
            {t('tabVideo')}
            {article.videos.length > 0 ? ` (${article.videos.length})` : ''}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="text">
          <div className={classes.article}>
            <Markdown remarkPlugins={remarkPlugins} components={markdownComponents}>
              {article.body}
            </Markdown>
          </div>
        </Tabs.Panel>

        <Tabs.Panel value="video">
          {article.videos.length === 0 ? (
            <Text c="dimmed" size="sm">
              {t('videoEmpty')}
            </Text>
          ) : (
            <div className={classes.videoList}>
              {article.videos.map((v, i) => (
                <VideoCard key={i} video={v} />
              ))}
            </div>
          )}
        </Tabs.Panel>
      </Tabs>
    </>
  );
}

export default DocsArticleView;
