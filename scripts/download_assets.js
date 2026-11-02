const fs = require('fs');
const path = require('path');
const https = require('https');

// Create directories
const tDir = path.join(__dirname, '..', 'img', 't');
const fDir = path.join(__dirname, '..', 'img', 'f');
if (!fs.existsSync(tDir)) fs.mkdirSync(tDir, { recursive: true });
if (!fs.existsSync(fDir)) fs.mkdirSync(fDir, { recursive: true });

// Read js/app.js to parse the project list P
const appJs = fs.readFileSync(path.join(__dirname, '..', 'js', 'app.js'), 'utf8');
const pMatch = appJs.match(/const P\s*=\s*(\[[\s\S]*?\]);\s*\/\//);
if (!pMatch) {
  console.error('Could not find projects array in js/app.js');
  process.exit(1);
}

// Safely evaluate array
const projects = eval(pMatch[1]);
console.log(`Found ${projects.length} projects to download.`);

function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    if (fs.existsSync(destPath) && fs.statSync(destPath).size > 0) {
      return resolve(false); // already downloaded
    }
    const file = fs.createWriteStream(destPath);
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, res => {
      if (res.statusCode !== 200) {
        file.close();
        fs.unlinkSync(destPath);
        return reject(new Error(`Failed to download ${url}: status ${res.statusCode}`));
      }
      res.pipe(file);
      file.on('finish', () => {
        file.close(() => resolve(true));
      });
    }).on('error', err => {
      if (fs.existsSync(destPath)) fs.unlinkSync(destPath);
      reject(err);
    });
  });
}

async function run() {
  console.log('Downloading thumbnails and full resolution project images...');
  let downloadedCount = 0;
  let skippedCount = 0;

  for (let i = 0; i < projects.length; i++) {
    const p = projects[i];
    const thumbName = `${p.img}.webp`;
    const tUrl = `https://mehak.studio/img/t/${thumbName}`;
    const tDest = path.join(tDir, thumbName);

    const fUrl = `https://mehak.studio/img/f/${thumbName}`;
    const fDest = path.join(fDir, thumbName);

    try {
      const tRes = await downloadFile(tUrl, tDest);
      const fRes = await downloadFile(fUrl, fDest);
      if (tRes || fRes) downloadedCount++;
      else skippedCount++;
      process.stdout.write(`\rProgress: [${i + 1}/${projects.length}] (New: ${downloadedCount}, Cached: ${skippedCount})`);
    } catch (err) {
      console.error(`\nError downloading ${p.img}: ${err.message}`);
    }
  }

  console.log('\nAsset download completed!');
}

run();
