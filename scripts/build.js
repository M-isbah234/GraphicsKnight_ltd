/**
 * Production Static Build Script for Graphic Knight Portfolio
 * Generates the production-ready 'dist' directory for Hostinger / static web hosting.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const rootDir = path.resolve(__dirname, '..');
const distDir = path.join(rootDir, 'dist');
const zipFile = path.join(rootDir, 'dist.zip');

console.log('🚀 Starting Graphic Knight production build...\n');

// 1. Clean previous build
if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
if (fs.existsSync(zipFile)) {
  fs.rmSync(zipFile, { force: true });
}

fs.mkdirSync(distDir, { recursive: true });

// 2. Files & Directories to copy into dist/
const filesToCopy = [
  'index.html',
  'portrait.jpg',
  'site.webmanifest',
  'apple-touch-icon.png',
  'android-chrome-192x192.png',
  'android-chrome-512x512.png',
  'og-share-image-1200x630.jpg',
  'preview.gif'
];

const dirsToCopy = [
  'css',
  'js',
  'audio'
];

// Copy files
filesToCopy.forEach(file => {
  const src = path.join(rootDir, file);
  const dest = path.join(distDir, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest);
    console.log(`  ✓ Copied ${file}`);
  } else {
    console.warn(`  ⚠️ Warning: ${file} not found at root`);
  }
});

// Copy directories
dirsToCopy.forEach(dir => {
  const src = path.join(rootDir, dir);
  const dest = path.join(distDir, dir);
  if (fs.existsSync(src)) {
    fs.cpSync(src, dest, { recursive: true });
    console.log(`  ✓ Copied ${dir}/`);
  } else {
    console.warn(`  ⚠️ Warning: directory ${dir} not found`);
  }
});

// 3. Generate Hostinger / Apache / LiteSpeed .htaccess file
const htaccessContent = `# ==============================================================
# Hostinger / LiteSpeed / Apache Production Config for Graphic Knight
# ==============================================================

# 1. Force UTF-8 Encoding
AddDefaultCharset UTF-8

# 2. Correct MIME Types
<IfModule mod_mime.c>
  AddType text/html .html
  AddType text/css .css
  AddType application/javascript .js
  AddType application/json .json
  AddType application/manifest+json .webmanifest
  AddType audio/mpeg .mp3
  AddType image/svg+xml .svg
  AddType image/webp .webp
  AddType image/png .png
  AddType image/jpeg .jpg .jpeg
  AddType font/woff2 .woff2
  AddType font/woff .woff
  AddType font/ttf .ttf
</IfModule>

# 3. Enable GZIP / Brotli Compression
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/plain text/css text/xml
  AddOutputFilterByType DEFLATE application/javascript application/x-javascript
  AddOutputFilterByType DEFLATE application/json application/manifest+json
  AddOutputFilterByType DEFLATE image/svg+xml
</IfModule>

# 4. Leverage Browser Caching
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresDefault "access plus 1 month"

  # HTML: keep short so updates deploy immediately
  ExpiresByType text/html "access plus 0 seconds"

  # CSS & JavaScript
  ExpiresByType text/css "access plus 1 year"
  ExpiresByType application/javascript "access plus 1 year"

  # Media & Audio
  ExpiresByType audio/mpeg "access plus 1 year"
  ExpiresByType image/jpeg "access plus 1 year"
  ExpiresByType image/png "access plus 1 year"
  ExpiresByType image/gif "access plus 1 year"
  ExpiresByType image/svg+xml "access plus 1 year"
  ExpiresByType image/x-icon "access plus 1 year"
</IfModule>

# 5. Security Headers
<IfModule mod_headers.c>
  Header set X-Content-Type-Options "nosniff"
  Header set X-Frame-Options "SAMEORIGIN"
  Header set Referrer-Policy "strict-origin-when-cross-origin"
</IfModule>

# 6. Fallback 404 to index.html for Single-Page Navigation
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule ^ index.html [L]
</IfModule>

ErrorDocument 404 /index.html
`;

fs.writeFileSync(path.join(distDir, '.htaccess'), htaccessContent, 'utf-8');
console.log('  ✓ Created .htaccess (optimized for Hostinger LiteSpeed/Apache)');

// 4. Generate robots.txt
const robotsContent = `User-agent: *\nAllow: /\n`;
fs.writeFileSync(path.join(distDir, 'robots.txt'), robotsContent, 'utf-8');
console.log('  ✓ Created robots.txt');

// 5. Create dist.zip archive for easy 1-click upload
try {
  const pyZip = `import zipfile, os
dist = r"${distDir.replace(/\\/g, '/')}"
zip_path = r"${zipFile.replace(/\\/g, '/')}"
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(dist):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, dist)
            z.write(full, rel)
print("ZIP_OK")
`;
  execSync(`python -c "${pyZip.replace(/\n/g, ';')}"`, { stdio: 'pipe' });
  console.log('  ✓ Created ready-to-upload dist.zip archive');
} catch (e) {
  // Fallback to powershell Compress-Archive
  try {
    execSync(`powershell -Command "Compress-Archive -Path '${distDir}\\*' -DestinationPath '${zipFile}' -Force"`, { stdio: 'pipe' });
    console.log('  ✓ Created ready-to-upload dist.zip archive (via PowerShell)');
  } catch (err) {
    console.warn('  ⚠️ Could not auto-generate dist.zip (dist/ folder is ready)');
  }
}

// 6. Summary of output files
function getFilesRecursively(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      results = results.concat(getFilesRecursively(fullPath));
    } else {
      results.push({
        path: path.relative(distDir, fullPath).replace(/\\/g, '/'),
        size: (stat.size / 1024).toFixed(1) + ' KB'
      });
    }
  });
  return results;
}

const buildFiles = getFilesRecursively(distDir);
console.log('\n📦 Production Build Summary:');
console.log('------------------------------------------------------');
buildFiles.forEach(f => console.log(`  • dist/${f.path.padEnd(30)} [${f.size}]`));
console.log('------------------------------------------------------');
console.log(`\n🎉 Build complete!`);
console.log(`📁 Final production folder: ${distDir}`);
console.log(`📄 Main entry point:       ${path.join(distDir, 'index.html')}`);
if (fs.existsSync(zipFile)) {
  const zipSize = (fs.statSync(zipFile).size / (1024 * 1024)).toFixed(2);
  console.log(`📦 Ready-to-upload archive: ${zipFile} (${zipSize} MB)`);
}
