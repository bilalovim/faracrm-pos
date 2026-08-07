import { useMemo } from 'react';
import { Text, Anchor } from '@mantine/core';
import { useTranslation } from 'react-i18next';

interface NotificationBody {
  text: string;
  /** Относительная ссылка на источник, напр. «/sales/5» (или undefined). */
  url?: string;
}

/**
 * Разобрать «notification-формат» тела: JSON {text, url} — по аналогии с тем,
 * как email хранит {subject, html}, а system — {event, params}. url —
 * относительный путь на источник уведомления (/model/id). Фолбэк для старых
 * уведомлений без формата — весь body как текст, без ссылки.
 */
export function parseNotificationBody(body: string): NotificationBody {
  if (!body) return { text: '' };
  try {
    const data = JSON.parse(body);
    if (data && typeof data === 'object' && ('text' in data || 'url' in data)) {
      return { text: data.text || '', url: data.url || undefined };
    }
  } catch {
    // не наш JSON — старый формат (plain text)
  }
  return { text: body };
}

/**
 * Уведомление о дедлайне: текст + ссылка на источник, открывается в НОВОЙ
 * вкладке (target=_blank). Подпись ссылки локализуется (ns 'chat').
 */
export function NotificationMessageContent({ body }: { body: string }) {
  const { t } = useTranslation('chat');
  const { text, url } = useMemo(() => parseNotificationBody(body), [body]);

  return (
    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
      {text}
      {url && (
        <>
          {'\n'}
          <Anchor href={url} target="_blank" rel="noopener noreferrer">
            {t('notificationOpenSource')}
          </Anchor>
        </>
      )}
    </Text>
  );
}
