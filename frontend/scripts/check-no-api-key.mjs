import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const distDirectory = fileURLToPath(new URL('../dist', import.meta.url))
const forbiddenPatterns = [
  /API_KEY/i,
  /X-API-KEY/i,
  /REPLACE_WITH/i,
  /Authorization\s*:\s*Bearer/i,
]

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []

  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...(await listFiles(path)))
    else files.push(path)
  }

  return files
}

const files = await listFiles(distDirectory)
const leaks = []

for (const file of files) {
  const content = await readFile(file, 'utf8')
  for (const pattern of forbiddenPatterns) {
    if (pattern.test(content)) leaks.push(`${file}: ${pattern}`)
  }
}

if (leaks.length > 0) {
  console.error('Potential API credential found in frontend bundle:')
  console.error(leaks.join('\n'))
  process.exit(1)
}

console.log(`Bundle security scan passed (${files.length} files).`)
