/**
 * Connector Bookmarks Component
 * 
 * A bookmarks-style bar showing available connectors for the current entity type.
 * Clicking a bookmark triggers a new request to that specific connector.
 * 
 * Appears below the URL bar, above the ConnectorBar (inner chrome).
 * Only shows when there are multiple connectors for the current entity.
 * 
 * @example
 * ```tsx
 * <ConnectorBookmarks
 *   connectors={[
 *     { skill: 'linear', account: 'Adavia', entities: ['task'] },
 *     { skill: 'todoist', account: 'Personal', entities: ['task'] },
 *   ]}
 *   currentEntity="task"
 *   currentOperation="list"
 *   currentSkill="linear"
 *   currentAccount="Adavia"
 * />
 * ```
 */

interface Connector {
  skill: string;
  account: string;
  entities: string[];
}

interface ConnectorBookmarksProps {
  /** Available connectors for the current entity */
  connectors: Connector[];
  /** Current entity type (e.g., 'task', 'webpage') */
  currentEntity: string;
  /** Current operation (e.g., 'list', 'search') */
  currentOperation?: string;
  /** Currently active skill */
  currentSkill?: string;
  /** Currently active account */
  currentAccount?: string;
  /** Function to get skill display name */
  getSkillName?: (skillId: string) => string;
}

export function ConnectorBookmarks({
  connectors,
  currentEntity,
  currentOperation,
  currentSkill,
  currentAccount,
}: ConnectorBookmarksProps) {
  // Handler to trigger a new request to a specific connector
  const handleBookmarkClick = async (connector: Connector) => {
    // Build the operation (e.g., "task.list")
    const operation = currentOperation || 'list';
    const tool = `${currentEntity}.${operation}`;
    
    try {
      const response = await fetch(`/use/${connector.skill}/${tool}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Agent': 'browser',
        },
        body: JSON.stringify({
          account: connector.account === 'default' ? undefined : connector.account,
          limit: 25,
        }),
      });
      
      if (!response.ok) {
        console.error('[ConnectorBookmarks] Request failed:', response.statusText);
      }
      // Activity will appear via WebSocket, no need to handle response
    } catch (error) {
      console.error('[ConnectorBookmarks] Error:', error);
    }
  };
  
  // Check if a connector is currently active
  const isActive = (connector: Connector) => {
    return connector.skill === currentSkill && 
           (connector.account === currentAccount || (!currentAccount && connector.account === 'default'));
  };
  
  return (
    <div className="connector-bookmarks">
      {connectors.map((connector) => {
        const active = isActive(connector);
        return (
          <button
            key={`${connector.skill}-${connector.account}`}
            className={`connector-bookmark ${active ? 'active' : ''}`}
            onClick={() => handleBookmarkClick(connector)}
            type="button"
            title={`${connector.skill} - ${connector.account}`}
          >
            <span className="connector-bookmark-icon connector-bookmark-icon--monogram" aria-hidden>
              {connector.skill.charAt(0).toUpperCase()}
            </span>
            <span className="connector-bookmark-label">
              {connector.account === 'default' ? connector.skill : connector.account}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default ConnectorBookmarks;
