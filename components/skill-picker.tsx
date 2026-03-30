/**
 * Skill Picker Component
 * 
 * Grid of skills grouped by entity type.
 * Used for "Add Account" flow, skill selection, and any skill browsing.
 * 
 * Features:
 * - Fetch from installed skills or library
 * - Filter to auth-requiring skills
 * - Group by entity (all entities or primary only)
 * - Optional header/footer with cancel button
 */

import React, { useState, useEffect } from 'react';

export interface Skill {
  id: string;
  name: string;
  description: string;
  entities: string[];
  // Auth fields (populated when fetching installed skills)
  auth_required?: boolean;
  auth_placeholders?: string[];
  auth_label?: string;
  auth_help_url?: string;
}

interface GroupedSkills {
  [entity: string]: Skill[];
}

interface SkillPickerProps {
  /** Group skills by entity type, or show flat list */
  grouped_by?: 'entity' | 'primary_entity' | 'none';
  /** Only show installed skills (vs library) */
  show_installed_only?: boolean;
  /** Only show skills that require authentication */
  filter_has_auth?: boolean;
  /** Optional title for the picker */
  title?: string;
  /** Optional description below title */
  description?: string;
  /** Callback when skill is selected */
  onSelect?: (skill: Skill) => void;
  /** Callback for back/cancel button (shows footer when provided) */
  onCancel?: () => void;
}

/**
 * Category overrides for entity grouping.
 * Most entities use their plural name (from schema), but some need custom category names.
 */
const CATEGORY_OVERRIDES: Record<string, string> = {
  event: 'Calendar',
  conversation: 'Messages',  // Group with messages
  webpage: 'Web Search',
  post: 'Social',
  table: 'Databases',
};

export function SkillPicker({ 
  grouped_by = 'entity',
  show_installed_only = false,
  filter_has_auth = false,
  title,
  description,
  onSelect,
  onCancel,
}: SkillPickerProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [entityNames, setEntityNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch entities for display names
    fetch('/mem')
      .then(res => res.json())
      .then(data => {
        const names: Record<string, string> = {};
        for (const entity of data.entities || []) {
          // Capitalize plural for category name (e.g., "tasks" → "Tasks")
          const plural = entity.plural || entity.id + 's';
          names[entity.id] = plural.charAt(0).toUpperCase() + plural.slice(1);
        }
        setEntityNames(names);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const endpoint = show_installed_only ? '/use' : '/use/library';
    fetch(endpoint)
      .then(res => res.json())
      .then(data => {
        let skillList = data.skills || [];
        
        if (filter_has_auth) {
          skillList = skillList.filter((p: any) => p.auth?.required);
        }
        
        const transformed: Skill[] = skillList.map((p: any) => ({
          id: p.id,
          name: p.name,
          description: p.description || '',
          entities: p.entities || Object.keys(p.adapters || {}),
          auth_required: p.auth?.required,
          auth_placeholders: p.auth?.placeholders || [],
          auth_label: p.auth?.label,
          auth_help_url: p.auth?.help_url,
        }));
        
        setSkills(transformed);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [show_installed_only, filter_has_auth]);
  
  const getEntityLabel = (entityId: string): string => {
    if (CATEGORY_OVERRIDES[entityId]) return CATEGORY_OVERRIDES[entityId];
    if (entityNames[entityId]) return entityNames[entityId];
    return entityId.charAt(0).toUpperCase() + entityId.slice(1) + 's';
  };

  if (loading) {
    return <div className="skill-picker-loading">Loading skills...</div>;
  }

  if (skills.length === 0) {
    return (
      <div className="skill-picker-empty">
        <p>{filter_has_auth 
          ? 'No skills available that require authentication.' 
          : 'No skills available.'
        }</p>
        {filter_has_auth && (
          <p>Install skills from the Library to connect to services.</p>
        )}
        {onCancel && (
          <button 
            data-component="button" 
            data-variant="secondary"
            onClick={onCancel}
          >
            Back
          </button>
        )}
      </div>
    );
  }

  const showGrouped = grouped_by === 'entity' || grouped_by === 'primary_entity';
  const grouped = showGrouped 
    ? groupByEntity(skills, grouped_by === 'primary_entity')
    : null;

  return (
    <div className="skill-picker">
      {/* Optional header */}
      {(title || description) && (
        <div className="skill-picker-header">
          {title && <h2>{title}</h2>}
          {description && <p>{description}</p>}
        </div>
      )}
      
      {/* Grouped view */}
      {grouped && Object.entries(grouped).map(([entity, entitySkills]) => (
        <div key={entity} className="skill-picker-group">
          <h3 className="skill-picker-group-title">
            {getEntityLabel(entity)}
          </h3>
          <div className="skill-picker-grid">
            {entitySkills.map(skill => (
              <SkillCard 
                key={skill.id} 
                skill={skill} 
                onClick={() => onSelect?.(skill)}
              />
            ))}
          </div>
        </div>
      ))}
      
      {/* Flat view */}
      {!grouped && (
        <div className="skill-picker-grid">
          {skills.map(skill => (
            <SkillCard 
              key={skill.id} 
              skill={skill} 
              onClick={() => onSelect?.(skill)}
            />
          ))}
        </div>
      )}
      
      {/* Optional footer with cancel button */}
      {onCancel && (
        <div className="skill-picker-footer">
          <button 
            data-component="button" 
            data-variant="secondary"
            onClick={onCancel}
          >
            Back
          </button>
        </div>
      )}
    </div>
  );
}

function SkillCard({ skill, onClick }: { skill: Skill; onClick: () => void }) {
  const initial = skill.name.charAt(0).toUpperCase();
  return (
    <button className="skill-picker-card" onClick={onClick}>
      <span className="skill-picker-card-icon skill-picker-card-icon--monogram" aria-hidden>
        {initial}
      </span>
      <span className="skill-picker-card-name">{skill.name}</span>
    </button>
  );
}

/**
 * Group skills by entity type.
 * @param primaryOnly - If true, each skill appears only in its first entity's group.
 *                      If false, skill appears in all entity groups it supports.
 */
function groupByEntity(skills: Skill[], primaryOnly: boolean = false): GroupedSkills {
  const grouped: GroupedSkills = {};
  
  for (const skill of skills) {
    const entities = skill.entities?.length ? skill.entities : ['other'];
    const entitiesToGroup = primaryOnly ? [entities[0]] : entities;
    
    for (const entity of entitiesToGroup) {
      if (!grouped[entity]) {
        grouped[entity] = [];
      }
      if (!grouped[entity].find(p => p.id === skill.id)) {
        grouped[entity].push(skill);
      }
    }
  }
  
  return grouped;
}

export default SkillPicker;
