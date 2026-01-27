/**
 * Conversation Preview Item Component
 * 
 * Renders a conversation list item with avatar, name, last message preview,
 * unread badge, and timestamp. Used by the Messages app's conversation list.
 * 
 * @example
 * ```yaml
 * - component: list
 *   data:
 *     capability: message_list_conversations
 *   item_component: conversation-preview
 *   item_props:
 *     name: "{{name}}"
 *     avatar: "{{avatar_url}}"
 *     last_message: "{{last_message}}"
 *     unread_count: "{{unread_count}}"
 *     timestamp: "{{updated_at}}"
 *     status: "{{presence}}"
 * ```
 */

interface ConversationPreviewProps {
  /** Contact or group name */
  name: string;
  /** Avatar image URL */
  avatar?: string;
  /** Last message preview text */
  last_message?: string;
  /** Number of unread messages (hidden if 0) */
  unread_count?: number;
  /** Timestamp of last message */
  timestamp?: string;
  /** Online status: 'online' | 'offline' | 'away' */
  status?: string;
}

export function ConversationPreview({ 
  name, 
  avatar, 
  last_message, 
  unread_count, 
  timestamp,
  status 
}: ConversationPreviewProps) {
  return (
    <div className="conversation-preview" data-status={status}>
      <div className="conversation-preview-avatar">
        {avatar ? (
          <img src={avatar} alt={name} />
        ) : (
          <span className="conversation-preview-avatar-placeholder">
            {name.charAt(0).toUpperCase()}
          </span>
        )}
        {status && <span className="conversation-preview-status-dot" data-status={status} />}
      </div>
      
      <div className="conversation-preview-content">
        <div className="conversation-preview-header">
          <span className="conversation-preview-name">{name}</span>
          {timestamp && (
            <span className="conversation-preview-timestamp">{formatTime(timestamp)}</span>
          )}
        </div>
        {last_message && (
          <p className="conversation-preview-message">{last_message}</p>
        )}
      </div>
      
      {unread_count && unread_count > 0 && (
        <span className="conversation-preview-badge">{unread_count}</span>
      )}
    </div>
  );
}

function formatTime(timestamp: string): string {
  // Simple relative time - themes can override with more sophisticated formatting
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h`;
  return date.toLocaleDateString();
}

export default ConversationPreview;
