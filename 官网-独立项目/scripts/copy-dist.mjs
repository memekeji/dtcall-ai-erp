import fs from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const source = path.join(root, 'frontend', 'dist')
const target = path.join(root, 'backend', 'internal', 'app', 'web')
await fs.rm(target, { recursive: true, force: true })
await fs.mkdir(path.dirname(target), { recursive: true })
await fs.cp(source, target, { recursive: true })
