// Copyright 2025 FARA CRM
// Всплывашка-карточка звонка. Слушает WS-события пайплайна звонка
// (call.incoming / call.ended) и показывает информационную карточку оператору.
//
// Сам звонок при этом отображается в чате партнёра как сообщение-звонок
// (CallMessageContent + аудиозапись) — это делает существующий рендер чата.
// Здесь только «всплывашка» поверх интерфейса, как просили.
//
// Монтируется один раз в ModernLayout (внутри ChatWebSocketProvider).

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Paper,
  Group,
  Text,
  ThemeIcon,
  ActionIcon,
  Anchor,
} from '@mantine/core';
import {
  IconPhoneIncoming,
  IconPhoneOutgoing,
  IconX,
} from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useChatWebSocketContext } from '@/fara_chat/context';

interface CallCard {
  direction?: string;
  disposition?: string;
  number?: string;
  name?: string;
  partner_id?: number | null;
  lead_id?: number | null;
  connector_type?: string;
}

/** Сколько карточка висит минимум — чтобы короткий звонок не мигнул. */
const MIN_VISIBLE_MS = 10_000;
/** Страховка на случай, если call.ended потерялся: разговор столько не длится. */
const AUTO_HIDE_MS = 30 * 60_000;

export function IncomingCallCard() {
  const { addMessageListener } = useChatWebSocketContext();
  const [call, setCall] = useState<CallCard | null>(null);
  const [endedNumber, setEndedNumber] = useState<string | null>(null);
  const shownAt = useRef(0);

  const dismiss = useCallback(() => setCall(null), []);

  // Подписка на события звонка из общего WS чата.
  useEffect(() => {
    return addMessageListener((msg: any) => {
      if (msg?.type === 'call.incoming' && msg.call) {
        shownAt.current = Date.now();
        setEndedNumber(null);
        setCall(msg.call);
      } else if (msg?.type === 'call.ended' && msg.call?.number) {
        setEndedNumber(msg.call.number);
      }
    });
  }, [addMessageListener]);

  // Пока разговор идёт — карточка висит. Закончился — досиживает
  // MIN_VISIBLE_MS от момента показа.
  useEffect(() => {
    if (!call) return;
    const finished = endedNumber === call.number;
    const delay = finished
      ? Math.max(0, MIN_VISIBLE_MS - (Date.now() - shownAt.current))
      : AUTO_HIDE_MS;
    const t = setTimeout(() => setCall(null), delay);
    return () => clearTimeout(t);
  }, [call, endedNumber]);

  if (!call) return null;

  const isIncoming = call.direction === 'incoming';
  const Icon = isIncoming ? IconPhoneIncoming : IconPhoneOutgoing;
  const title = isIncoming ? 'Входящий звонок' : 'Исходящий звонок';
  const answered = call.disposition === 'answered';

  const target = call.lead_id
    ? `/leads/${call.lead_id}`
    : call.partner_id
      ? `/partners/${call.partner_id}`
      : null;
  const targetLabel = call.lead_id ? 'Открыть лид' : 'Открыть партнёра';

  return (
    <Paper
      shadow="md"
      p="md"
      radius="md"
      withBorder
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        width: 320,
        zIndex: 3000,
      }}>
      <Group justify="space-between" wrap="nowrap" mb={6}>
        <Group gap={10} wrap="nowrap">
          <ThemeIcon
            size={40}
            radius="xl"
            variant="light"
            color={answered ? 'green' : 'blue'}>
            <Icon size={22} />
          </ThemeIcon>
          <div>
            <Text fw={600} size="sm">
              {title}
            </Text>
            <Text size="xs" c="dimmed">
              {answered ? 'Разговор' : 'Дозвон…'}
              {call.connector_type ? ` · ${call.connector_type}` : ''}
            </Text>
          </div>
        </Group>
        <ActionIcon variant="subtle" color="gray" onClick={dismiss}>
          <IconX size={16} />
        </ActionIcon>
      </Group>

      <Text fw={500}>{call.name || call.number || '—'}</Text>
      {call.number && call.name && (
        <Text size="xs" c="dimmed">
          {call.number}
        </Text>
      )}

      {target && (
        <Anchor
          component={Link}
          to={target}
          size="sm"
          onClick={dismiss}
          mt={8}
          style={{ display: 'inline-block' }}>
          {targetLabel}
        </Anchor>
      )}
    </Paper>
  );
}

export default IncomingCallCard;
