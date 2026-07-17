import { useMemo, useState } from 'react';
import {
  Stack,
  Text,
  UnstyledButton,
  Group,
  ActionIcon,
  Menu,
  Badge,
} from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  IconMessage,
  IconMessages,
  IconUsers,
  IconUser,
  IconFolder,
  IconPlus,
  IconDotsVertical,
  IconPencil,
  IconTrash,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMail,
  IconMessageCircle,
} from '@tabler/icons-react';
import {
  useSearchQuery,
  useDeleteBulkMutation,
} from '@/services/api/crudApi';
import { ChatFolder, useGetFolderUnreadQuery } from '@/services/api/chat';
import { FolderModal } from '@/fara_chat/components/FolderModal';
import avitoIconUrl from '@/fara_chat_avito/assets/avito.svg';
import { MaxIcon } from '@/fara_chat_max_bot/components/MaxIcon';
import { VkIcon } from '@/fara_chat_vk/components/VkIcon';
import classes from './ChatSidebar.module.css';

// Папки чатов = записи модели chat_folder (общий auto-CRUD). Правила доступа
// на бэке отдают свои + глобальные (user_id IS NULL) папки:
//   • обычные — «Все»/«Личные»/«Группы» (kind) + пользовательские (свои);
//   • коннекторные — по одной на коннектор (connector_id) → отдельная секция
//     «Внешние», имя и иконка берутся у самого коннектора (резолв на фронте).

const AvitoIcon = () => (
  <img
    src={avitoIconUrl}
    width={18}
    height={18}
    alt="Avito"
    draggable={false}
    style={{ display: 'block' }}
  />
);

// Иконки по типу коннектора — те же, что в ConnectorFilter/у самих коннекторов.
const CONNECTOR_ICONS: Record<string, React.ReactNode> = {
  telegram: <IconBrandTelegram size={18} />,
  whatsapp: <IconBrandWhatsapp size={18} />,
  whatsapp_chatapp: <IconBrandWhatsapp size={18} />,
  email: <IconMail size={18} />,
  avito: <AvitoIcon />,
  max_bot: <MaxIcon />,
  max_business: <MaxIcon />,
  vk: <VkIcon size={18} />,
};

const FOLDER_FIELDS = [
  'id',
  'name',
  'icon',
  'color',
  'sequence',
  'domain',
  'kind',
  'connector_id',
  'user_id',
];

// Глобальная папка = без владельца (user_id NULL). Many2one приходит как
// объект {id,...} или null.
function isGlobal(f: any): boolean {
  const u = f?.user_id;
  return u == null || (typeof u === 'object' && u.id == null);
}

// id коннектора из Many2one поля (объект {id,name} или голый id).
function connectorId(f: any): number | null {
  const c = f?.connector_id;
  if (c == null) return null;
  return typeof c === 'object' ? c.id ?? null : c;
}

// Иконка обычной (не коннекторной) папки.
function builtinIcon(f: any): React.ReactNode {
  switch (f?.kind) {
    case 'group':
      return <IconUsers size={18} />;
    case 'all':
      // «Все» (внутренние) — два бабла, чтобы отличалось от «Личные».
      return <IconMessages size={18} />;
    case 'direct':
    case 'internal':
      return <IconMessage size={18} />;
    case 'external_all':
      return <IconUsers size={18} />;
    case 'external_mine':
      return <IconUser size={18} />;
    default:
      return <IconFolder size={18} />;
  }
}

export function ChatSidebar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname + location.search;

  const { data } = useSearchQuery({
    model: 'chat_folder',
    fields: FOLDER_FIELDS,
    filter: [],
    limit: 100,
  });
  // Коннекторы (через общий auto-CRUD /auto/chat_connector) — резолвим имя
  // и тип (для иконки) папки коннектора. GET /connectors на бэке нет.
  const { data: connectorsData } = useSearchQuery({
    model: 'chat_connector',
    fields: ['id', 'type', 'name', 'active', 'category'],
    filter: [],
    limit: 200,
  });
  const [deleteBulk] = useDeleteBulkMutation();

  // Непрочитанные по папкам — считаются на бэке на лету. { "<folder_id>": count }
  // только для count>0.
  //
  // refetchOnMountOrArgChange ОБЯЗАТЕЛЕН, иначе счётчики папок отставали от
  // верхнего бабла. Причина в разнице механизмов: верхний бабл читает getChats
  // и патчится хирургически (updateQueryData на каждом WS-событии, подписчик не
  // нужен), а этот запрос обновляется через инвалидацию тега FOLDER_UNREAD →
  // refetch, который срабатывает ТОЛЬКО при активной подписке. Пока входящие
  // шли кроном, а сайдбар был не смонтирован, инвалидация «сгорала» без
  // подписчика; при возврате в пределах keepUnusedDataFor (30с) RTK отдавал
  // устаревший кэш без перезапроса. Флаг форсит свежий счёт на каждый монтаж.
  const { data: unreadData } = useGetFolderUnreadQuery(undefined, {
    refetchOnMountOrArgChange: true,
  });
  const unreadByFolder = unreadData?.data || {};

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ChatFolder | null>(null);

  const connMap = useMemo(() => {
    const m = new Map<
      number,
      { type: string; name: string; active: boolean; category: string }
    >();
    for (const c of ((connectorsData?.data as unknown) as any[]) || []) {
      m.set(c.id, {
        type: c.type,
        name: c.name,
        active: c.active,
        category: c.category,
      });
    }
    return m;
  }, [connectorsData]);

  const allFolders = useMemo(
    () =>
      [...(((data?.data as unknown) as any[]) || [])].sort(
        (a, b) => (a.sequence || 0) - (b.sequence || 0),
      ),
    [data],
  );

  // Три секции: внутренние (Все/Личные/Группы + пользовательские), внешние
  // (быстрые папки external_all/external_mine), каналы (папки коннекторов).
  const EXTERNAL_KINDS = new Set(['external_all', 'external_mine']);
  const nonConnectorFolders = allFolders.filter(f => !connectorId(f));
  const externalFolders = nonConnectorFolders.filter(f =>
    EXTERNAL_KINDS.has(f?.kind),
  );
  const regularFolders = nonConnectorFolders.filter(
    f => !EXTERNAL_KINDS.has(f?.kind),
  );
  // Папку коннектора показываем только если сам коннектор АКТИВЕН и это не
  // notification-канал (web_push — уведомления, а не чат). Иначе в сайдбаре
  // висели папки выключенных и уведомительных коннекторов. Коннектор, которого
  // нет в connMap (удалён / не загрузился), тоже прячем.
  const connectorFolders = allFolders.filter(f => {
    const cid = connectorId(f);
    if (!cid) return false;
    const c = connMap.get(cid);
    return !!c && c.active && c.category !== 'notification';
  });

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };
  const openEdit = (f: any) => {
    setEditing(f);
    setModalOpen(true);
  };
  const handleDelete = (f: any) => {
    deleteBulk({ model: 'chat_folder', ids: [f.id] });
    if (currentPath === `/chat?folder_id=${f.id}`) navigate('/chat');
  };

  const renderFolder = (
    folder: any,
    iconNode: React.ReactNode,
    label: string,
  ) => {
    const to = `/chat?folder_id=${folder.id}`;
    const active = currentPath === to;
    // Меню (изменить/удалить) только у своих папок; глобальные — без меню.
    const editable = !isGlobal(folder);
    const unread = unreadByFolder[String(folder.id)] || 0;

    return (
      <Group key={folder.id} gap={2} wrap="nowrap">
        <UnstyledButton
          className={`${classes.item} ${classes.internal}`}
          data-active={active || undefined}
          style={{ flex: 1 }}
          onClick={() => navigate(to)}>
          <Group gap="sm" wrap="nowrap">
            {iconNode}
            <Text size="sm" fw={active ? 600 : 400} truncate style={{ flex: 1 }}>
              {label}
            </Text>
            {unread > 0 && (
              <Badge size="sm" variant="filled" color="blue" circle>
                {unread > 99 ? '99+' : unread}
              </Badge>
            )}
          </Group>
        </UnstyledButton>

        {editable && (
          <Menu position="bottom-end" withinPortal shadow="md">
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" size="sm">
                <IconDotsVertical size={14} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconPencil size={14} />}
                onClick={() => openEdit(folder)}>
                {t('chat:edit', 'Изменить')}
              </Menu.Item>
              <Menu.Item
                color="red"
                leftSection={<IconTrash size={14} />}
                onClick={() => handleDelete(folder)}>
                {t('chat:delete', 'Удалить')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>
    );
  };

  return (
    <Stack gap={4}>
      {/* Обычные папки */}
      <Group justify="space-between" px="sm" py="xs">
        <Text size="xs" fw={600} c="dimmed" tt="uppercase">
          {t('chat:menu.internal', 'Внутренние')}
        </Text>
        <ActionIcon
          variant="subtle"
          size="sm"
          onClick={openCreate}
          title={t('chat:menu.newFolder', 'Новая папка')}>
          <IconPlus size={16} />
        </ActionIcon>
      </Group>

      {regularFolders.map(f => renderFolder(f, builtinIcon(f), f.name))}

      {/* Внешние — обычные глобальные папки external_all/external_mine
          (навигация по folder_id; get_chats резолвит по kind). */}
      {externalFolders.length > 0 && (
        <Text size="xs" fw={600} c="dimmed" px="sm" py="xs" tt="uppercase">
          {t('chat:menu.external', 'Внешние')}
        </Text>
      )}
      {externalFolders.map(f => renderFolder(f, builtinIcon(f), f.name))}

      {/* Каналы (коннекторные папки) — отдельной секцией НИЖЕ */}
      {connectorFolders.length > 0 && (
        <Text size="xs" fw={600} c="dimmed" px="sm" py="xs" tt="uppercase">
          {t('chat:menu.channels', 'Каналы')}
        </Text>
      )}

      {connectorFolders.map(f => {
        const cid = connectorId(f);
        const conn = cid != null ? connMap.get(cid) : undefined;
        const label =
          conn?.name ||
          (typeof f.connector_id === 'object' ? f.connector_id?.name : null) ||
          f.name;
        const iconNode =
          (conn && CONNECTOR_ICONS[conn.type]) || (
            <IconMessageCircle size={18} />
          );
        return renderFolder(f, iconNode, label);
      })}

      <FolderModal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        folder={editing}
      />
    </Stack>
  );
}
