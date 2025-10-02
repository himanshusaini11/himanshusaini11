import { makeBadge } from 'badge-maker';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Simple badge using an options object
export function createBadge({
  label,
  message = '',
  color = '#7A003C',
  labelColor = '#FFFFFF',
  style = 'flat',
  outputFile
}) {
  if (!label) throw new Error('label is required');
  if (!outputFile) throw new Error('outputFile is required');

  const format = { label, message, color, labelColor, style };
  const svg = makeBadge(format);
  fs.writeFileSync(outputFile, svg);
  console.log(`Created badge: ${outputFile}`);
}

// Badge with logo using an options object
export function createBadgeWithLogo({
  label,
  message = '',
  color = '#7A003C',
  labelColor = '#FFFFFF',
  style = 'flat',
  logoPath,
  outputFile
}) {
  if (!label) throw new Error('label is required');
  if (!logoPath) throw new Error('logoPath is required');
  if (!outputFile) throw new Error('outputFile is required');

  const resolvedLogoPath = path.isAbsolute(logoPath) ? logoPath : path.join(__dirname, logoPath);
  const logoSvg = fs.readFileSync(resolvedLogoPath, 'utf8');
  const logoDataUri = 'data:image/svg+xml;base64,' + Buffer.from(logoSvg).toString('base64');

  const format = { label, message, color, labelColor, style, logoBase64: logoDataUri };
  const svg = makeBadge(format);
  fs.writeFileSync(outputFile, svg);
  console.log(`Created badge with logo: ${outputFile}`);
}

// --- Example usage ---
// Basic badge with defaults (maroon + white)
//createBadge({ label: 'SQL', outputFile: 'sql-badge.svg' });

// Badge with logo (uses local SVG)
createBadgeWithLogo({
  label: 'Matplotlib',
  message: '',
  logoPath: './logo/matplotlib-logo.svg',
  outputFile: 'matplotlib-badge.svg'
});