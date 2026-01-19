/**
 * Search Result Item Component
 * 
 * Renders a single web search result with title, URL, and optional snippet.
 * Used by the Browser app's search view within a list component.
 * 
 * @example
 * ```yaml
 * - component: list
 *   data:
 *     capability: web_search
 *   item_component: search-result
 *   item_props:
 *     title: "{{title}}"
 *     url: "{{url}}"
 *     snippet: "{{snippet}}"
 * ```
 */

interface SearchResultProps {
  /** Result title - displayed prominently */
  title: string;
  /** Result URL - displayed below title */
  url: string;
  /** Optional snippet/description */
  snippet?: string;
}

export function SearchResult({ title, url, snippet }: SearchResultProps) {
  return (
    <div className="search-result">
      <a className="search-result-title" href={url} target="_blank" rel="noopener">
        {title}
      </a>
      <span className="search-result-url">{url}</span>
      {snippet && (
        <p className="search-result-snippet">{snippet}</p>
      )}
    </div>
  );
}

export default SearchResult;
