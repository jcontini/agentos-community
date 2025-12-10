#!/usr/bin/env node

/**
 * Validates all skill.md files against the skill schema
 * Run with: node scripts/validate-skills.js
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const VALID_CATEGORIES = ['productivity', 'communication', 'search', 'code', 'finance', 'media'];
const VALID_PROTOCOLS = ['shell', 'rest', 'graphql'];
const VALID_CAPABILITIES = ['web-search', 'url-extract'];
const VALID_AUTH_TYPES = ['api_key', 'oauth', 'service_account', 'cli', 'local'];
const VALID_SETTING_TYPES = ['integer', 'enum', 'boolean', 'string'];
const VALID_PARAM_TYPES = ['string', 'integer', 'boolean', 'number'];

let errors = [];
let warnings = [];

function validateSkill(filePath, frontmatter) {
  const skillId = path.basename(path.dirname(filePath));
  const errors = [];
  const warnings = [];

  // Required fields
  if (!frontmatter.id) errors.push(`Missing required field: id`);
  if (!frontmatter.name) errors.push(`Missing required field: name`);
  if (!frontmatter.description) errors.push(`Missing required field: description`);
  if (!frontmatter.category) errors.push(`Missing required field: category`);
  if (!frontmatter.protocol) errors.push(`Missing required field: protocol`);

  // Validate id matches directory name
  if (frontmatter.id && frontmatter.id !== skillId) {
    errors.push(`id "${frontmatter.id}" doesn't match directory name "${skillId}"`);
  }

  // Validate category
  if (frontmatter.category && !VALID_CATEGORIES.includes(frontmatter.category)) {
    errors.push(`Invalid category: "${frontmatter.category}". Must be one of: ${VALID_CATEGORIES.join(', ')}`);
  }

  // Validate protocol
  if (frontmatter.protocol && !VALID_PROTOCOLS.includes(frontmatter.protocol)) {
    errors.push(`Invalid protocol: "${frontmatter.protocol}". Must be one of: ${VALID_PROTOCOLS.join(', ')}`);
  }

  // Protocol-specific validation
  if (frontmatter.protocol === 'shell') {
    if (!frontmatter.actions || Object.keys(frontmatter.actions).length === 0) {
      errors.push(`shell protocol requires 'actions' field`);
    }
  } else if (frontmatter.protocol === 'rest' || frontmatter.protocol === 'graphql') {
    if (!frontmatter.api) {
      errors.push(`${frontmatter.protocol} protocol requires 'api' field`);
    }
    if (!frontmatter.auth) {
      errors.push(`${frontmatter.protocol} protocol requires 'auth' field`);
    }
  }

  // Validate provides
  if (frontmatter.provides) {
    if (!Array.isArray(frontmatter.provides)) {
      errors.push(`'provides' must be an array`);
    } else {
      frontmatter.provides.forEach((cap, i) => {
        if (!VALID_CAPABILITIES.includes(cap)) {
          errors.push(`Invalid capability in provides[${i}]: "${cap}". Must be one of: ${VALID_CAPABILITIES.join(', ')}`);
        }
      });
    }
  }

  // Validate auth
  if (frontmatter.auth) {
    if (!frontmatter.auth.type) {
      errors.push(`auth.type is required`);
    } else if (!VALID_AUTH_TYPES.includes(frontmatter.auth.type)) {
      errors.push(`Invalid auth.type: "${frontmatter.auth.type}". Must be one of: ${VALID_AUTH_TYPES.join(', ')}`);
    }

    if (frontmatter.auth.type === 'api_key') {
      if (!frontmatter.auth.header) {
        errors.push(`auth.header is required for api_key auth`);
      }
    }

    if (frontmatter.auth.type === 'oauth') {
      if (!frontmatter.auth.auth_url) errors.push(`auth.auth_url is required for oauth`);
      if (!frontmatter.auth.token_url) errors.push(`auth.token_url is required for oauth`);
    }
  }

  // Validate settings
  if (frontmatter.settings) {
    if (typeof frontmatter.settings !== 'object') {
      errors.push(`'settings' must be an object`);
    } else {
      Object.entries(frontmatter.settings).forEach(([key, setting]) => {
        if (!setting.label) errors.push(`settings.${key}: missing required field 'label'`);
        if (!setting.description) errors.push(`settings.${key}: missing required field 'description'`);
        if (!setting.type) {
          errors.push(`settings.${key}: missing required field 'type'`);
        } else if (!VALID_SETTING_TYPES.includes(setting.type)) {
          errors.push(`settings.${key}: invalid type "${setting.type}". Must be one of: ${VALID_SETTING_TYPES.join(', ')}`);
        }
        if (setting.default === undefined || setting.default === null) {
          errors.push(`settings.${key}: missing required field 'default'`);
        } else if (typeof setting.default !== 'string') {
          errors.push(`settings.${key}: 'default' must be a string (got ${typeof setting.default}: ${JSON.stringify(setting.default)})`);
        }

        // Type-specific validation
        if (setting.type === 'enum') {
          if (!setting.options || !Array.isArray(setting.options)) {
            errors.push(`settings.${key}: enum type requires 'options' array`);
          }
        }
        if (setting.type === 'integer') {
          if (setting.min !== undefined && typeof setting.min !== 'number') {
            errors.push(`settings.${key}: 'min' must be a number`);
          }
          if (setting.max !== undefined && typeof setting.max !== 'number') {
            errors.push(`settings.${key}: 'max' must be a number`);
          }
        }
      });
    }
  }

  // Validate actions (for shell protocol)
  if (frontmatter.actions) {
    Object.entries(frontmatter.actions).forEach(([actionName, action]) => {
      if (!action.description) {
        errors.push(`actions.${actionName}: missing required field 'description'`);
      }
      if (!action.run && frontmatter.protocol === 'shell') {
        errors.push(`actions.${actionName}: missing required field 'run' (required for shell protocol)`);
      }

      // Validate params
      if (action.params) {
        Object.entries(action.params).forEach(([paramName, param]) => {
          if (!param.type) {
            errors.push(`actions.${actionName}.params.${paramName}: missing required field 'type'`);
          } else if (!VALID_PARAM_TYPES.includes(param.type)) {
            errors.push(`actions.${actionName}.params.${paramName}: invalid type "${param.type}". Must be one of: ${VALID_PARAM_TYPES.join(', ')}`);
          }
          if (!param.description) {
            warnings.push(`actions.${actionName}.params.${paramName}: missing 'description' (recommended)`);
          }

          // Validate default values are strings
          if (param.default !== undefined && typeof param.default !== 'string') {
            errors.push(`actions.${actionName}.params.${paramName}: 'default' must be a string (got ${typeof param.default}: ${JSON.stringify(param.default)})`);
          }
        });
      }
    });
  }

  return { errors, warnings };
}

function main() {
  const skillsDir = path.join(__dirname, '..', 'skills');
  
  if (!fs.existsSync(skillsDir)) {
    console.error(`❌ Skills directory not found: ${skillsDir}`);
    process.exit(1);
  }

  const skillDirs = fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);

  console.log(`🔍 Validating ${skillDirs.length} skills...\n`);

  let totalErrors = 0;
  let totalWarnings = 0;

  for (const skillDir of skillDirs) {
    const skillPath = path.join(skillsDir, skillDir, 'skill.md');
    
    if (!fs.existsSync(skillPath)) {
      console.error(`⚠️  ${skillDir}: skill.md not found`);
      continue;
    }

    const content = fs.readFileSync(skillPath, 'utf8');
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);

    if (!frontmatterMatch) {
      console.error(`❌ ${skillDir}: No YAML frontmatter found`);
      totalErrors++;
      continue;
    }

    try {
      const frontmatter = yaml.load(frontmatterMatch[1]);
      const { errors, warnings } = validateSkill(skillPath, frontmatter);

      if (errors.length > 0 || warnings.length > 0) {
        console.log(`\n📋 ${skillDir} (${frontmatter.name || 'unnamed'})`);
        
        if (errors.length > 0) {
          console.log(`   ❌ Errors (${errors.length}):`);
          errors.forEach(err => console.log(`      • ${err}`));
          totalErrors += errors.length;
        }
        
        if (warnings.length > 0) {
          console.log(`   ⚠️  Warnings (${warnings.length}):`);
          warnings.forEach(warn => console.log(`      • ${warn}`));
          totalWarnings += warnings.length;
        }
      } else {
        console.log(`✅ ${skillDir}`);
      }
    } catch (e) {
      console.error(`❌ ${skillDir}: Failed to parse YAML: ${e.message}`);
      totalErrors++;
    }
  }

  console.log(`\n${'='.repeat(50)}`);
  if (totalErrors === 0 && totalWarnings === 0) {
    console.log(`✅ All skills validated successfully!`);
    process.exit(0);
  } else {
    console.log(`📊 Summary:`);
    console.log(`   Errors: ${totalErrors}`);
    console.log(`   Warnings: ${totalWarnings}`);
    if (totalErrors > 0) {
      console.log(`\n❌ Validation failed. Please fix the errors above.`);
      process.exit(1);
    } else {
      console.log(`\n⚠️  Validation passed with warnings.`);
      process.exit(0);
    }
  }
}

// Check if js-yaml is available
try {
  require.resolve('js-yaml');
  main();
} catch (e) {
  console.error('❌ Missing dependency: js-yaml');
  console.error('   Install with: npm install js-yaml');
  console.error('   Or use: npx js-yaml (if available)');
  process.exit(1);
}
