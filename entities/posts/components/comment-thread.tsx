/**
 * Comment Thread Component
 * 
 * Renders a recursive tree of comments/replies with:
 * - Threading lines (like Reddit)
 * - Collapse/expand toggle
 * - Upvote indicator
 */

import React, { useState } from 'react';

interface Comment {
  id: string;
  content: string;
  author?: {
    name: string;
    url?: string;
  };
  engagement?: {
    score?: number;
  };
  published_at?: string;
  replies?: Comment[];
}

interface CommentThreadProps {
  /** Array of top-level comments with nested replies */
  replies?: Comment[];
  /** Whether there are more comments not loaded */
  hasMore?: boolean;
}

interface SingleCommentProps {
  comment: Comment;
  depth: number;
}

/**
 * Format relative time
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/**
 * Format score
 */
function formatScore(score: number): string {
  if (score >= 1000) {
    return `${(score / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  }
  return String(score);
}

/**
 * Single comment with its metadata and nested replies
 */
function SingleComment({ comment, depth }: SingleCommentProps) {
  const [collapsed, setCollapsed] = useState(false);
  const hasReplies = comment.replies && comment.replies.length > 0;
  
  return (
    <div className={`comment ${collapsed ? 'comment--collapsed' : ''}`}>
      {/* Collapse toggle */}
      <div 
        className="comment__collapse"
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? 'Expand' : 'Collapse'}
      >
        {collapsed ? '+' : '−'}
      </div>
      
      {/* Threading line (only if has replies and not collapsed) */}
      {hasReplies && !collapsed && (
        <div 
          className="comment__thread-line"
          onClick={() => setCollapsed(true)}
          title="Collapse thread"
        />
      )}
      
      {/* Comment header */}
      <div className="comment__header">
        <span className="comment__vote">▲</span>
        {comment.author && (
          comment.author.url ? (
            <a 
              href={comment.author.url}
              target="_blank"
              rel="noopener noreferrer"
              className="comment__author"
            >
              {comment.author.name}
            </a>
          ) : (
            <span className="comment__author">{comment.author.name}</span>
          )
        )}
        
        {comment.engagement?.score !== undefined && (
          <span className="comment__score">
            {formatScore(comment.engagement.score)} points
          </span>
        )}
        
        {comment.published_at && (
          <span className="comment__time">
            {formatRelativeTime(comment.published_at)}
          </span>
        )}
        
        {collapsed && hasReplies && (
          <span className="comment__score">
            ({comment.replies!.length} {comment.replies!.length === 1 ? 'child' : 'children'})
          </span>
        )}
      </div>
      
      {/* Comment body */}
      <div className="comment__body">
        {comment.content}
      </div>
      
      {/* Nested replies */}
      {hasReplies && (
        <div className="comment__replies">
          {comment.replies!.map((reply) => (
            <SingleComment 
              key={reply.id} 
              comment={reply} 
              depth={depth + 1} 
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function CommentThread({ replies, hasMore }: CommentThreadProps) {
  if (!replies || replies.length === 0) {
    return (
      <div className="comment-thread comment-thread--empty">
        <span className="comment-thread__empty-message">No comments yet</span>
      </div>
    );
  }
  
  return (
    <div className="comment-thread">
      {replies.map((comment) => (
        <SingleComment 
          key={comment.id} 
          comment={comment} 
          depth={0} 
        />
      ))}
      
      {hasMore && (
        <div className="comment-thread__more">
          More comments not loaded...
        </div>
      )}
    </div>
  );
}

export default CommentThread;
