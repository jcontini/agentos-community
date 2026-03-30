/**
 * Request/Response Component
 * 
 * Postman-style display for activities without custom entity views.
 * Shows the raw request and response in a clean, developer-friendly format.
 * 
 * This is the fallback view for any entity that doesn't have custom views defined.
 * 
 * CSS: Uses .request-response-* classes from base.css (dark theme)
 */

interface RequestResponseProps {
  /** Entity type (e.g., 'task', 'message') */
  entity?: string;
  /** Operation (e.g., 'list', 'get', 'create') */
  operation?: string;
  /** Skill that handled the request */
  skill?: string;
  /** Request parameters */
  request?: Record<string, unknown>;
  /** Response data */
  response?: unknown;
  /** Whether the request is still pending */
  pending?: boolean;
  /** Error message if request failed */
  error?: string;
  /** Response status */
  status?: string;
  /** Duration in milliseconds */
  duration_ms?: number;
}

/**
 * Format JSON with syntax highlighting classes
 */
function formatJson(data: unknown): string {
  if (data === null || data === undefined) return 'null';
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

/**
 * Get HTTP method based on operation
 */
function getMethodForOperation(operation?: string): string {
  if (!operation) return 'GET';
  
  const op = operation.toLowerCase();
  if (op.includes('create') || op.includes('add') || op.includes('send')) return 'POST';
  if (op.includes('update') || op.includes('edit') || op.includes('modify')) return 'PUT';
  if (op.includes('delete') || op.includes('remove')) return 'DELETE';
  if (op.includes('list') || op.includes('search') || op.includes('get') || op.includes('read')) return 'GET';
  return 'POST';
}

/**
 * Get status type for styling
 */
function getStatusType(error?: string, pending?: boolean): string {
  if (error) return 'error';
  if (pending) return 'pending';
  return 'success';
}

export function RequestResponse({
  entity,
  operation,
  skill,
  request,
  response,
  pending,
  error,
  status,
  duration_ms,
}: RequestResponseProps) {
  const method = getMethodForOperation(operation);
  const endpoint = `/${entity}${operation ? '/' + operation : ''}`;
  const statusType = getStatusType(error, pending);
  const statusCode = error ? '500' : pending ? '...' : '200';
  
  return (
    <div className="request-response">
      {/* Header bar */}
      <div className="request-response-header">
        <span className="request-response-method" data-method={method}>
          {method}
        </span>
        
        <span className="request-response-endpoint">
          {skill && <span className="request-response-skill">{skill}</span>}
          {endpoint}
        </span>
        
        <span className="request-response-status" data-status={statusType}>
          {statusCode}
        </span>
        
        {duration_ms !== undefined && (
          <span className="request-response-duration">
            {duration_ms}ms
          </span>
        )}
      </div>
      
      {/* Content area */}
      <div className="request-response-content">
        {/* Request section */}
        {request && Object.keys(request).length > 0 && (
          <div className="request-response-section" data-section="request">
            <div className="request-response-section-header">
              Request
            </div>
            <pre className="request-response-section-body">
              {formatJson(request)}
            </pre>
          </div>
        )}
        
        {/* Response section */}
        <div className="request-response-section" data-section="response">
          <div className="request-response-section-header">
            Response
            {Array.isArray(response) && (
              <span className="request-response-section-count">
                [{response.length} items]
              </span>
            )}
          </div>
          
          {pending ? (
            <div className="request-response-loading">
              Loading...
            </div>
          ) : error ? (
            <pre className="request-response-section-body request-response-error-body">
              {error}
            </pre>
          ) : (
            <pre className="request-response-section-body">
              {formatJson(response)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default RequestResponse;
