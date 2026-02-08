#!/usr/bin/env node
/**
 * Generate manifest.json from repository contents
 * 
 * Usage:
 *   node scripts/generate-manifest.js           # Generate manifest.json
 *   node scripts/generate-manifest.js --check   # Validate without writing
 */

import { readdirSync, readFileSync, writeFileSync, statSync, existsSync, lstatSync } from 'fs';
import { join, basename } from 'path';

/**
 * Get the most recent modification time of any file in a directory (recursive)
 */
function getLatestModTime(dir) {
  let latestTime = 0;
  
  function scanDir(currentDir) {
    try {
      const entries = readdirSync(currentDir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.name.startsWith('.')) continue;
        
        const fullPath = join(currentDir, entry.name);
        const stats = lstatSync(fullPath);
        
        if (stats.isFile()) {
          latestTime = Math.max(latestTime, stats.mtimeMs);
        } else if (stats.isDirectory()) {
          scanDir(fullPath);
        }
      }
    } catch (err) {
      // Skip directories we can't read
    }
  }
  
  scanDir(dir);
  return latestTime > 0 ? new Date(latestTime).toISOString() : null;
}
import yaml from 'js-yaml';

const REPO_ROOT = new URL('..', import.meta.url).pathname;
const MANIFEST_PATH = join(REPO_ROOT, 'manifest.json');

/**
 * Walk a directory recursively, looking for items
 */
function walkDirectory(dir, depth = 0, maxDepth = 3) {
  if (depth > maxDepth) return [];
  
  const items = [];
  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue;
      
      const fullPath = join(dir, entry.name);
      
      if (entry.isDirectory()) {
        items.push(...walkDirectory(fullPath, depth + 1, maxDepth));
      }
    }
  } catch (err) {
    console.warn(`Skipping directory ${dir}: ${err.message}`);
  }
  
  return items;
}

/**
 * Extract metadata from a adapter directory
 */
function extractAdapterMetadata(adapterDir) {
  const readmePath = join(adapterDir, 'readme.md');
  
  if (!existsSync(readmePath)) return null;
  
  try {
    readFileSync(readmePath, 'utf-8');
  } catch {
    return null;
  }
  
  const content = readFileSync(readmePath, 'utf-8');
  const frontMatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
  
  if (!frontMatterMatch) return null;
  
  const metadata = yaml.load(frontMatterMatch[1]);
  
  // Get relative path from adapters/ directory (e.g., "tasks/todoist")
  const adaptersRoot = join(REPO_ROOT, 'adapters');
  const relativePath = adapterDir.replace(adaptersRoot + '/', '');
  
  // Get the most recent file modification time in this adapter's folder
  const updatedAt = getLatestModTime(adapterDir);
  
  // Extract entities from adapters keys (e.g., { post: {...}, group: {...} } → ["post", "group"])
  const entities = metadata.adapters ? Object.keys(metadata.adapters) : [];
  
  return {
    id: metadata.id || basename(adapterDir),
    name: metadata.name || basename(adapterDir),
    description: metadata.description || '',
    icon: `adapters/${relativePath}/icon.svg`,
    color: metadata.color || null,
    entities,
    version: metadata.version || '1.0.0',
    author: metadata.author || 'community',
    updated_at: updatedAt,
  };
}

/**
 * Extract metadata from an app directory
 */
function extractAppMetadata(appDir) {
  const yamlPath = join(appDir, 'app.yaml');
  
  try {
    const content = readFileSync(yamlPath, 'utf-8');
    const metadata = yaml.load(content);
    
    const updatedAt = getLatestModTime(appDir);
    
    return {
      id: metadata.id || basename(appDir),
      name: metadata.name || basename(appDir),
      description: metadata.description || '',
      icon: `models/${basename(appDir)}/icon.svg`,
      version: metadata.version || '1.0.0',
      author: metadata.author || 'agentos',
      updated_at: updatedAt,
    };
  } catch (err) {
    console.warn(`Skipping app ${basename(appDir)}: ${err.message}`);
    return null;
  }
}

/**
 * Extract metadata from a theme directory
 */
function extractThemeMetadata(themeDir, themeType) {
  const yamlPath = join(themeDir, 'theme.yaml');
  
  try {
    const content = readFileSync(yamlPath, 'utf-8');
    const metadata = yaml.load(content);
    
    const updatedAt = getLatestModTime(themeDir);
    
    return {
      id: metadata.id || basename(themeDir),
      name: metadata.name || basename(themeDir),
      type: themeType,
      description: metadata.description || '',
      preview: `themes/${themeType}/${basename(themeDir)}/preview.png`,
      version: metadata.version || '1.0.0',
      author: metadata.author || 'agentos',
      updated_at: updatedAt,
    };
  } catch (err) {
    console.warn(`Skipping theme ${basename(themeDir)}: ${err.message}`);
    return null;
  }
}

/**
 * Extract metadata from a component file
 */
function extractComponentMetadata(componentPath) {
  const id = basename(componentPath, '.tsx');
  
  try {
    const content = readFileSync(componentPath, 'utf-8');
    
    // Look for JSDoc-style metadata comment at the top
    const metaMatch = content.match(/\/\*\*\s*\n([\s\S]*?)\n\s*\*\//);
    
    let name = id;
    let description = '';
    
    if (metaMatch) {
      const metaContent = metaMatch[1];
      const nameMatch = metaContent.match(/\*\s*@name\s+(.+)/);
      const descMatch = metaContent.match(/\*\s*@description\s+(.+)/);
      
      if (nameMatch) name = nameMatch[1].trim();
      if (descMatch) description = descMatch[1].trim();
    }
    
    return {
      id,
      name,
      description,
      version: '1.0.0',
      author: 'agentos',
    };
  } catch (err) {
    console.warn(`Skipping component ${id}: ${err.message}`);
    return null;
  }
}

/**
 * Generate the manifest from repository contents
 */
function generateManifest() {
  const manifest = {
    version: '1.0.0',
    updated_at: new Date().toISOString(),
    adapters: [],
    apps: [],
    themes: [],
    components: [],
  };
  
  // Scan adapters recursively (handles both flat and nested structures)
  const adaptersDir = join(REPO_ROOT, 'adapters');
  
  function scanAdaptersRecursive(dir, depth = 0, maxDepth = 3) {
    if (depth > maxDepth) return;
    
    try {
      const entries = readdirSync(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        if (entry.name.startsWith('.')) continue;
        
        const entryPath = join(dir, entry.name);
        
        if (entry.isDirectory()) {
          // Check if this directory is a adapter (has readme.md)
          const readmePath = join(entryPath, 'readme.md');
          if (existsSync(readmePath)) {
            const metadata = extractAdapterMetadata(entryPath);
            if (metadata) manifest.adapters.push(metadata);
          } else {
            // It's a category folder, recurse into it
            scanAdaptersRecursive(entryPath, depth + 1, maxDepth);
          }
        }
      }
    } catch (err) {
      // Silently skip directories we can't read
    }
  }
  
  try {
    scanAdaptersRecursive(adaptersDir);
  } catch (err) {
    console.warn(`No adapters directory: ${err.message}`);
  }
  
  // Scan models (apps are spawned from models at runtime)
  const appsDir = join(REPO_ROOT, 'models');
  try {
    const appDirs = readdirSync(appsDir, { withFileTypes: true })
      .filter(entry => entry.isDirectory() && !entry.name.startsWith('.'))
      .map(entry => join(appsDir, entry.name));
    
    for (const appDir of appDirs) {
      const metadata = extractAppMetadata(appDir);
      if (metadata) manifest.apps.push(metadata);
    }
  } catch (err) {
    console.warn(`No apps directory: ${err.message}`);
  }
  
  // Scan themes (OS and app themes)
  const themesDir = join(REPO_ROOT, 'themes');
  try {
    for (const themeType of ['os', 'app']) {
      const typeDir = join(themesDir, themeType);
      try {
        const themeDirs = readdirSync(typeDir, { withFileTypes: true })
          .filter(entry => entry.isDirectory() && !entry.name.startsWith('.'))
          .map(entry => join(typeDir, entry.name));
        
        for (const themeDir of themeDirs) {
          const metadata = extractThemeMetadata(themeDir, themeType);
          if (metadata) manifest.themes.push(metadata);
        }
      } catch (err) {
        console.warn(`No ${themeType} themes: ${err.message}`);
      }
    }
  } catch (err) {
    console.warn(`No themes directory: ${err.message}`);
  }
  
  // Scan components
  const componentsDir = join(REPO_ROOT, 'components');
  try {
    const componentFiles = readdirSync(componentsDir)
      .filter(file => file.endsWith('.tsx') && !file.startsWith('.'))
      .map(file => join(componentsDir, file));
    
    for (const componentPath of componentFiles) {
      const metadata = extractComponentMetadata(componentPath);
      if (metadata) manifest.components.push(metadata);
    }
  } catch (err) {
    console.warn(`No components directory: ${err.message}`);
  }
  
  // Sort each category by id
  manifest.adapters.sort((a, b) => a.id.localeCompare(b.id));
  manifest.apps.sort((a, b) => a.id.localeCompare(b.id));
  manifest.themes.sort((a, b) => a.id.localeCompare(b.id));
  manifest.components.sort((a, b) => a.id.localeCompare(b.id));
  
  return manifest;
}

/**
 * Main
 */
function main() {
  const checkOnly = process.argv.includes('--check');
  
  console.log('Generating manifest from repository contents...');
  const manifest = generateManifest();
  
  console.log(`Found:`);
  console.log(`  - ${manifest.adapters.length} adapters`);
  console.log(`  - ${manifest.apps.length} apps`);
  console.log(`  - ${manifest.themes.length} themes`);
  console.log(`  - ${manifest.components.length} components`);
  
  const manifestJson = JSON.stringify(manifest, null, 2);
  
  if (checkOnly) {
    // Check if current manifest matches
    try {
      const currentManifest = readFileSync(MANIFEST_PATH, 'utf-8');
      if (currentManifest.trim() === manifestJson.trim()) {
        console.log('✓ Manifest is up to date');
        process.exit(0);
      } else {
        console.error('✗ Manifest is out of date. Run: node scripts/generate-manifest.js');
        process.exit(1);
      }
    } catch (err) {
      console.error('✗ manifest.json not found or unreadable');
      process.exit(1);
    }
  } else {
    // Write the manifest
    writeFileSync(MANIFEST_PATH, manifestJson + '\n');
    console.log(`✓ Wrote manifest to ${MANIFEST_PATH}`);
  }
}

main();
