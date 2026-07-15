/**
 * PartnerChatPanel — чат с клиентом на форме записи (модель 1:1).
 *
 * У партнёра ОДИН внешний групповой чат. Панель резолвит его id по partner_id
 * (форма партнёра) или по lead.partner_id (форма лида) и показывает ОБЫЧНЫМ
 * чат-компонентом (ChatMessages + ChatInput) — никакой отдельной «ленты».
 * На форме лида исходящее тегируется lead_id (ChatInput.leadId) для привязки.
 *
 * Доступ — штатные правила чата (членство / team-правило): не член и не в
 * команде чата → GET сообщений вернёт пусто/403.
 *
 * Отличие от MessagesPanel («Заметки», внутренний record-чат): там заметки
 * команды, тут — переписка с клиентом по каналам.
 */

import { useEffect, useState } from 'react';
import { Loader, Center, Text, Stack, Button } from '@mantine/core';
import { IconMessagePlus } from '@tabler/icons-react';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';
import {
  useResolvePartnerChatQuery,
  useResolveLeadChatQuery,
  useGetChatQuery,
  useGetChatConnectorsQuery,
  useSetChatDefaultConnectorMutation,
  useCreatePartnerChatMutation,
} from '@/services/api/chat';
import { ChatMessages } from '@/fara_chat/components/ChatMessages';
import { ChatInput } from '@/fara_chat/components/ChatInput';

interface PartnerChatPanelProps {
  resModel: string;
  resId: number;
}

export function PartnerChatPanel({ resModel, resId }: PartnerChatPanelProps) {
  const isLead = resModel === 'leads';
  const session = useSelector(selectCurrentSession);
  const currentUserId = session?.user_id?.id || 0;
  const currentUserName = session?.user_id?.name || '';

  // На форме лида исходящее привязываем к этому лиду.
  const leadId = isLead ? resId : null;

  // 1. Резолвим id чата партнёра (без создания).
  const leadRes = useResolveLeadChatQuery({ leadId: resId }, { skip: !isLead });
  const partnerRes = useResolvePartnerChatQuery(
    { partnerId: resId },
    { skip: isLead },
  );
  const resolve = isLead ? leadRes : partnerRes;
  const chatId = resolve.data?.chat_id || undefined;
  // Партнёр для создания чата: на форме партнёра — сама запись, на лиде —
  // lead.partner_id (приходит в ответе резолва).
  const targetPartnerId = isLead
    ? (resolve.data?.partner_id ?? null)
    : resId;

  const [createPartnerChat, { isLoading: creating }] =
    useCreatePartnerChatMutation();
  const handleCreateChat = async () => {
    if (!targetPartnerId) return;
    try {
      await createPartnerChat({ partnerId: targetPartnerId }).unwrap();
      resolve.refetch();
    } catch (e) {
      console.error('Create partner chat failed:', e);
    }
  };

  // 2. Грузим Chat (нужен ChatMessages) — только если чат есть.
  const { data: chatData, isLoading: isChatLoading } = useGetChatQuery(
    { chatId: chatId || 0 },
    { skip: !chatId },
  );
  const chat = chatData?.data;

  // 3. Коннекторы чата (для выбора канала в ChatInput).
  const { data: connectorsData } = useGetChatConnectorsQuery(
    { chatId: chatId || 0 },
    { skip: !chatId },
  );
  const connectors = connectorsData?.data || [];
  const defaultConnectorId = connectorsData?.default_connector_id ?? null;
  const [selectedConnectorId, setSelectedConnectorId] = useState<
    number | null
  >(null);
  useEffect(() => {
    setSelectedConnectorId(defaultConnectorId);
  }, [chatId, defaultConnectorId]);

  const [saveDefaultConnector] = useSetChatDefaultConnectorMutation();

  if (resolve.isLoading || (chatId && isChatLoading)) {
    return (
      <Center py="xl" style={{ flex: 1 }}>
        <Loader size="sm" />
      </Center>
    );
  }

  // Чата ещё нет — предлагаем создать групповой чат (партнёр + текущий юзер).
  if (!chatId || !chat) {
    return (
      <Center py="xl" style={{ flex: 1 }}>
        <Stack align="center" gap="sm">
          <Text size="sm" c="dimmed">
            Нет переписки с клиентом
          </Text>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconMessagePlus size={16} />}
            loading={creating}
            disabled={!targetPartnerId}
            onClick={handleCreateChat}>
            Создать чат
          </Button>
        </Stack>
      </Center>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: '1 1 0%',
        minHeight: 0,
      }}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        <ChatMessages chat={chat} currentUserId={currentUserId} />
      </div>
      <div style={{ flexShrink: 0 }}>
        <ChatInput
          chatId={chatId}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          connectors={connectors}
          connectorId={selectedConnectorId ?? undefined}
          onConnectorSelect={setSelectedConnectorId}
          defaultConnectorId={defaultConnectorId}
          onSetDefaultConnector={cid =>
            saveDefaultConnector({ chatId, connectorId: cid })
          }
          leadId={leadId}
        />
      </div>
    </div>
  );
}

export default PartnerChatPanel;
