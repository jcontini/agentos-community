/**
 * Chat Bubble Item Component
 * 
 * Renders a single chat message with sender, content, and timestamp.
 * Supports different styling for sent vs received messages.
 * 
 * @example
 * ```yaml
 * - component: list
 *   data:
 *     capability: message_list
 *   item_component: items/chat-bubble
 *   item_props:
 *     content: "{{content}}"
 *     sender: "{{sender_name}}"
 *     is_self: "{{is_outgoing}}"
 *     timestamp: "{{timestamp}}"
 * ```
 */

// Import shared utilities from the framework
import { formatTime } from '/lib/utils.js';

interface ChatBubbleProps {
  /** Message content */
  content: string;
  /** Sender's display name */
  sender: string;
  /** Whether this message was sent by the current user */
  is_self: boolean;
  /** Message timestamp (ISO string) */
  timestamp: string;
  /** Sender's avatar URL */
  avatar?: string;
  /** Message delivery status: 'sending' | 'sent' | 'delivered' | 'read' */
  status?: string;
}

export function ChatBubble({ 
  content, 
  sender, 
  is_self, 
  timestamp,
  avatar,
  status
}: ChatBubbleProps) {
  return (
    <div className="chat-bubble" data-is-self={is_self}>
      {!is_self && avatar && (
        <img className="chat-bubble-avatar" src={avatar} alt={sender} />
      )}
      
      <div className="chat-bubble-content">
        {!is_self && (
          <span className="chat-bubble-sender">{sender}</span>
        )}
        <p className="chat-bubble-text">{content}</p>
        <div className="chat-bubble-meta">
          <span className="chat-bubble-timestamp">{formatTime(timestamp)}</span>
          {is_self && status && (
            <span className="chat-bubble-status" data-status={status}>
              {getStatusIcon(status)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'sending': return '○';
    case 'sent': return '✓';
    case 'delivered': return '✓✓';
    case 'read': return '✓✓'; // themes style this differently (blue checkmarks)
    default: return '';
  }
}

export default ChatBubble;
