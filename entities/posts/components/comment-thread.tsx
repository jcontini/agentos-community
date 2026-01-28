/**
 * Comment Thread Component
 * 
 * Renders a recursive tree of comments/replies.
 * Each comment can have nested replies, displayed with indentation.
 */

import React from 'react';

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
  /** Current nesting depth (internal use) */
  depth?: number;
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
 * Single comment with its metadata
 */
function SingleComment({ comment, depth }: SingleCommentProps) {
  const indentPx = depth * 16; // 16px per level
  
  return (
    <div 
      className="comment"
      style={{ marginLeft: `${indentPx}px` }}
    >
      {/* Comment header */}
      <div className="comment__header">
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
            {comment.engagement.score} points
          </span>
        )}
        
        {comment.published_at && (
          <span className="comment__time">
            {formatRelativeTime(comment.published_at)}
          </span>
        )}
      </div>
      
      {/* Comment body */}
      <div className="comment__body">
        {comment.content}
      </div>
      
      {/* Nested replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="comment__replies">
          {comment.replies.map((reply) => (
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

export function CommentThread({ 
  replies, 
  hasMore,
  depth = 0 
}: CommentThreadProps) {
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
          depth={depth} 
        />
      ))}
      
      {hasMore && (
        <div className="comment-thread__more">
          <span>More comments not loaded</span>
        </div>
      )}
    </div>
  );
}

export default CommentThread;
