/**
 * Account List Component
 * 
 * Master-detail layout using standardized sidebar pattern:
 * - Uses data-layout="sidebar" for layout
 * - Uses List variant="sidebar" for skill navigation
 * - Right content: selected skill's account details
 * 
 * Features:
 * - Instructions editing: Free-form notes for AI (stored per-credential)
 * - Params editing: Key-value pairs auto-injected into requests (stored in settings)
 * - Keyboard navigation via List component
 */

import React, { useState, useEffect, useCallback, useMemo, KeyboardEvent } from 'react';

interface Credential {
  account: string;
  preview: string;
  label?: string;
  instructions: string;
  created_at?: string;
}

interface SkillAccount {
  skill_id: string;
  skill_name: string;
  auth_label?: string;
  auth_help_url?: string;
  entities: string[];
  credentials: Credential[];
}

interface AccountListProps {
  /** Callback when user clicks "Add Account" button. If not provided, navigates to #accounts/add */
  onAddAccount?: () => void;
}

export function AccountList({ onAddAccount }: AccountListProps) {
  // Default navigation when no callback provided
  const handleAddAccount = onAddAccount || (() => {
    window.location.hash = '#accounts/add';
  });
  const [accounts, setAccounts] = useState<SkillAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  
  // Instructions editing state
  const [editingInstructions, setEditingInstructions] = useState<string | null>(null);
  const [instructionsValue, setInstructionsValue] = useState('');
  
  // Params editing state
  const [editingParams, setEditingParams] = useState<string | null>(null);
  const [allAccountParams, setAllAccountParams] = useState<Record<string, Record<string, any>>>({});
  const [newParamKey, setNewParamKey] = useState('');
  const [newParamValue, setNewParamValue] = useState('');

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch('/sys/accounts');
      const data = await res.json();
      const accountList = data.accounts || [];
      setAccounts(accountList);
      // Select first skill by default
      if (accountList.length > 0 && !selectedSkill) {
        setSelectedSkill(accountList[0].skill_id);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load accounts');
    } finally {
      setLoading(false);
    }
  }, [selectedSkill]);

  const fetchAccountParams = useCallback(async () => {
    try {
      const res = await fetch('/sys/settings/account_params');
      const data = await res.json();
      setAllAccountParams(data.value || {});
    } catch (err) {
      console.error('Failed to load account params:', err);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
    fetchAccountParams();
  }, []);

  const handleRemove = async (skillId: string, account: string) => {
    if (!confirm(`Remove ${account} from ${skillId}?`)) return;
    
    try {
      const res = await fetch(`/sys/accounts/${skillId}/${account}`, { method: 'DELETE' });
      if (res.ok) {
        fetchAccounts();
        fetchAccountParams();
      } else {
        alert('Failed to remove account');
      }
    } catch { 
      alert('Failed to remove account'); 
    }
  };

  // Instructions editing
  const startEditingInstructions = (skillId: string, account: string, currentInstructions: string) => {
    setEditingInstructions(`${skillId}:${account}`);
    setInstructionsValue(currentInstructions);
    // Close params editing if open
    setEditingParams(null);
  };

  const saveInstructions = async (skillId: string, account: string) => {
    try {
      const res = await fetch(`/sys/accounts/${skillId}/${account}/instructions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions: instructionsValue }),
      });
      if (res.ok) {
        setEditingInstructions(null);
        fetchAccounts();
      }
    } catch (err) {
      console.error('Failed to save instructions:', err);
    }
  };

  const cancelInstructionsEditing = () => {
    setEditingInstructions(null);
    setInstructionsValue('');
  };

  // Params editing
  const saveParams = async (skillId: string, account: string, params: Record<string, any>) => {
    const key = `${skillId}:${account}`;
    const newAllParams = { ...allAccountParams, [key]: params };
    
    // Remove empty params objects
    if (Object.keys(params).length === 0) {
      delete newAllParams[key];
    }
    
    try {
      const res = await fetch('/sys/settings/account_params', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: newAllParams }),
      });
      if (res.ok) {
        setAllAccountParams(newAllParams);
      }
    } catch (err) {
      console.error('Failed to save params:', err);
    }
  };

  const addParam = async (skillId: string, account: string) => {
    if (!newParamKey.trim()) return;
    
    const key = `${skillId}:${account}`;
    const currentParams = allAccountParams[key] || {};
    const newParams = { ...currentParams, [newParamKey.trim()]: newParamValue.trim() };
    
    await saveParams(skillId, account, newParams);
    setNewParamKey('');
    setNewParamValue('');
  };

  const removeParam = async (skillId: string, account: string, paramKey: string) => {
    const key = `${skillId}:${account}`;
    const currentParams = { ...(allAccountParams[key] || {}) };
    delete currentParams[paramKey];
    
    await saveParams(skillId, account, currentParams);
  };

  const startEditingParams = (skillId: string, account: string) => {
    setEditingParams(`${skillId}:${account}`);
    // Close instructions editing if open
    setEditingInstructions(null);
  };

  const finishEditingParams = () => {
    setEditingParams(null);
    setNewParamKey('');
    setNewParamValue('');
  };

  const selectedIndex = useMemo(() => {
    return accounts.findIndex(a => a.skill_id === selectedSkill);
  }, [accounts, selectedSkill]);

  // Keyboard navigation handler for sidebar
  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const itemCount = accounts.length;
    if (itemCount === 0) return;

    let newIndex = selectedIndex;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        newIndex = selectedIndex < itemCount - 1 ? selectedIndex + 1 : selectedIndex;
        break;
      case 'ArrowUp':
        e.preventDefault();
        newIndex = selectedIndex > 0 ? selectedIndex - 1 : 0;
        break;
      case 'Home':
        e.preventDefault();
        newIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        newIndex = itemCount - 1;
        break;
      default:
        return;
    }
    if (newIndex !== selectedIndex && newIndex >= 0 && newIndex < itemCount) {
      setSelectedSkill(accounts[newIndex].skill_id);
    }
  }, [accounts, selectedIndex]);

  if (loading) {
    return <div data-component="loading">Loading accounts...</div>;
  }

  if (error) {
    return <div data-component="error">Error: {error}</div>;
  }

  const selectedSkillData = accounts.find(a => a.skill_id === selectedSkill);

  return (
    <div className="account-list" data-layout="sidebar">
      {/* Left Sidebar - Skill List */}
      <div data-slot="nav">
        <div data-component="sidebar-header">
          <span>Accounts</span>
          <button 
            data-component="button"
            data-variant="ghost"
            data-size="sm"
            onClick={handleAddAccount}
            title="Add Account"
          >
            +
          </button>
        </div>

        {accounts.length === 0 ? (
          <div data-component="empty-state">
            No accounts configured
          </div>
        ) : (
          <div
            data-component="list"
            data-variant="sidebar"
            role="listbox"
            aria-label="Skill accounts"
            tabIndex={0}
            onKeyDown={handleKeyDown}
          >
            {accounts.map((skill, index) => (
              <div
                key={skill.skill_id}
                data-component="list-item"
                role="option"
                aria-selected={selectedSkill === skill.skill_id}
                data-selected={selectedSkill === skill.skill_id}
                onClick={() => setSelectedSkill(skill.skill_id)}
              >
                <span
                  data-component="list-item-icon"
                  aria-hidden
                >
                  {skill.skill_name.charAt(0).toUpperCase()}
                </span>
                <span data-component="list-item-label">
                  {skill.skill_name}
                </span>
                <span data-component="list-item-badge">
                  {skill.credentials.length}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right Content - Account Details */}
      <div data-slot="content">
        {!selectedSkillData ? (
          <div data-component="empty-state">
            <p>No accounts configured yet.</p>
            <button 
              data-component="button"
              data-variant="primary"
              onClick={handleAddAccount}
            >
              Add Account
            </button>
          </div>
        ) : (
          <div>
            {/* Skill Header */}
            <div data-component="content-header">
              <span
                data-component="content-header-icon"
                aria-hidden
              >
                {selectedSkillData.skill_name.charAt(0).toUpperCase()}
              </span>
              <div>
                <h2 data-component="content-header-title">{selectedSkillData.skill_name}</h2>
                {selectedSkillData.entities.length > 0 && (
                  <div data-component="content-header-subtitle">
                    Provides: {selectedSkillData.entities.join(', ')}
                  </div>
                )}
              </div>
            </div>

            {/* Credentials */}
            {selectedSkillData.credentials.map(cred => {
              const editKey = `${selectedSkillData.skill_id}:${cred.account}`;
              const isEditingInstr = editingInstructions === editKey;
              const isEditingPrms = editingParams === editKey;
              const params = allAccountParams[editKey] || {};
              const paramEntries = Object.entries(params);

              return (
                <div key={cred.account} className="account-list-credential">
                  {/* Account Header */}
                  <div className="account-list-credential-header">
                    <div>
                      <div className="account-list-credential-name">
                        {cred.label || cred.account}
                      </div>
                      <div className="account-list-credential-preview">
                        {cred.preview}
                      </div>
                    </div>
                    <button
                      data-component="button"
                      data-variant="secondary"
                      data-size="sm"
                      onClick={() => handleRemove(selectedSkillData.skill_id, cred.account)}
                    >
                      Remove
                    </button>
                  </div>

                  {/* Notes for AI Section */}
                  <div className="account-list-section">
                    <div className="account-list-section-label">Notes for AI</div>
                    {isEditingInstr ? (
                      <div>
                        <textarea
                          data-component="input"
                          data-variant="textarea"
                          value={instructionsValue}
                          onChange={(e) => setInstructionsValue(e.target.value)}
                          placeholder="Free-form notes that AI will see when using this account..."
                          autoFocus
                        />
                        <div className="account-list-section-actions">
                          <button
                            data-component="button"
                            data-variant="primary"
                            data-size="sm"
                            onClick={() => saveInstructions(selectedSkillData.skill_id, cred.account)}
                          >
                            Save
                          </button>
                          <button
                            data-component="button"
                            data-variant="secondary"
                            data-size="sm"
                            onClick={cancelInstructionsEditing}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="account-list-section-display"
                        onClick={() => startEditingInstructions(selectedSkillData.skill_id, cred.account, cred.instructions)}
                      >
                        {cred.instructions ? (
                          <span className="account-list-section-text">{cred.instructions}</span>
                        ) : (
                          <span className="account-list-section-placeholder">Click to add notes for AI...</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Auto-injected Parameters Section */}
                  <div className="account-list-section">
                    <div className="account-list-section-header">
                      <span className="account-list-section-label">Auto-injected Parameters</span>
                      {!isEditingPrms && (
                        <button
                          data-component="button"
                          data-variant="ghost"
                          data-size="sm"
                          onClick={() => startEditingParams(selectedSkillData.skill_id, cred.account)}
                        >
                          {paramEntries.length > 0 ? 'Edit' : 'Add'}
                        </button>
                      )}
                    </div>

                    {paramEntries.length === 0 && !isEditingPrms ? (
                      <div className="account-list-section-empty">
                        No parameters configured
                      </div>
                    ) : (
                      <div className="account-list-params-list">
                        {/* Existing params */}
                        {paramEntries.map(([key, value]) => (
                          <div key={key} className="account-list-param-row">
                            <code className="account-list-param-key">{key}</code>
                            <span className="account-list-param-value">{String(value)}</span>
                            {isEditingPrms && (
                              <button
                                data-component="button"
                                data-variant="ghost"
                                data-size="sm"
                                onClick={() => removeParam(selectedSkillData.skill_id, cred.account, key)}
                              >
                                ×
                              </button>
                            )}
                          </div>
                        ))}

                        {/* Add new param form */}
                        {isEditingPrms && (
                          <div className="account-list-param-form">
                            <input
                              data-component="input"
                              type="text"
                              placeholder="key"
                              value={newParamKey}
                              onChange={(e) => setNewParamKey(e.target.value)}
                              className="account-list-param-input-key"
                            />
                            <input
                              data-component="input"
                              type="text"
                              placeholder="value"
                              value={newParamValue}
                              onChange={(e) => setNewParamValue(e.target.value)}
                              className="account-list-param-input-value"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') addParam(selectedSkillData.skill_id, cred.account);
                              }}
                            />
                            <button
                              data-component="button"
                              data-variant="secondary"
                              data-size="sm"
                              onClick={() => addParam(selectedSkillData.skill_id, cred.account)}
                              disabled={!newParamKey.trim()}
                            >
                              Add
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Done button when editing params */}
                    {isEditingPrms && (
                      <div className="account-list-section-actions">
                        <button
                          data-component="button"
                          data-variant="primary"
                          data-size="sm"
                          onClick={finishEditingParams}
                        >
                          Done
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Help Link */}
            {selectedSkillData.auth_help_url && (
              <div className="account-list-help-link">
                <a
                  href={selectedSkillData.auth_help_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  How to get your {selectedSkillData.auth_label || 'API key'} →
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AccountList;
