import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(currentDir, '..')
const dist = path.join(root, 'dist')
const indexPath = path.join(dist, 'index.html')
const indexHtml = await fs.readFile(indexPath, 'utf8')

const pages = ['product', 'products', 'solutions', 'cases', 'news', 'resources', 'updates', 'contact']

await Promise.all(pages.map(async (page) => {
  const pageDir = path.join(dist, page)
  await fs.mkdir(pageDir, { recursive: true })
  await fs.writeFile(path.join(pageDir, 'index.html'), indexHtml)
}))
