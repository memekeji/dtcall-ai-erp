export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type SEO = {
  title: string
  keywords: string
  description: string
  canonical: string
  ogTitle: string
  ogDescription: string
  ogImage: string
  schema: string
}

export type SiteConfig = {
  name: string
  subtitle: string
  slogan: string
  description: string
  logo: string
  domain: string
  phone: string
  email: string
  address: string
  icp: string
  favicon?: string
  themePrimary?: string
  seo: SEO
}

export type NavigationItem = {
  id?: number
  label: string
  path: string
  order: number
  visible: boolean
  position?: string
  target?: string
}

export type Metric = {
  value: string
  label: string
}

export type Feature = {
  title: string
  text: string
  icon: string
}

export type CTA = {
  title: string
  text: string
  primaryText: string
  primaryLink: string
  secondaryText: string
  secondaryLink: string
}

export type PageBlock = {
  id: number
  type: string
  title: string
  subtitle: string
  content: string
  image: string
  metrics: Metric[]
  features: Feature[]
  cta: CTA
  order: number
  visible: boolean
  extra?: Record<string, string>
}

export type Page = {
  id: number
  slug: string
  title: string
  summary: string
  path: string
  seo: SEO
  blocks: PageBlock[]
  status: string
  updatedAt: string
}

export type Product = {
  id: number
  slug: string
  title: string
  summary: string
  icon: string
  tags: string[]
  highlights: string[]
  metrics?: Metric[]
  detail: string
  seo: SEO
  status: string
  order: number
  updatedAt: string
}

export type ContentItem = {
  id: number
  slug: string
  title: string
  summary: string
  category: string
  cover: string
  tags: string[]
  body: string
  type?: string
  recommended?: boolean
  publishedAt?: string
  seo: SEO
  status: string
  order: number
  updatedAt: string
}

export type Resource = {
  id: number
  title: string
  category: string
  summary: string
  link: string
  order: number
  status: string
  slug?: string
  needLead?: boolean
  tags?: string[]
  publishedAt?: string
  seo?: SEO
}

export type Release = {
  id: number
  version: string
  title: string
  summary: string
  packageUrl: string
  checksum: string
  target: string
  status: string
  publishedAt: string
  updatedAt: string
  highlights: string[]
}

export type FAQ = {
  id?: number
  question: string
  answer: string
  category?: string
  sort?: number
  status?: string
}

export type PublicResources = {
  resources: Resource[]
  faqs: FAQ[]
}

export type PublicData = {
  site: SiteConfig
  navigation: NavigationItem[]
  home: Page
  pages: Record<string, Page>
  products: Product[]
  solutions: ContentItem[]
  cases: ContentItem[]
  news: ContentItem[]
  resources: PublicResources
  releases: Release[]
}

export type Lead = {
  id?: number
  name: string
  company: string
  phone: string
  email?: string
  demandType?: string
  message: string
  status?: string
  sourcePath?: string
  ip?: string
  createdAt?: string
  updatedAt?: string
  followups?: LeadFollowup[]
}

export type LeadFollowup = {
  user: string
  content: string
  nextAction: string
  createdAt: string
}

export type DashboardStats = {
  pageCount: number
  productCount: number
  solutionCount: number
  caseCount: number
  newsCount: number
  releaseCount: number
  leadCount: number
  newLeadCount: number
  seoScore: number
  updatedAt: string
}

export type OperationLog = {
  id: number
  user: string
  action: string
  targetType: string
  targetId: number
  ip: string
  createdAt: string
}

export type Role = {
  id: number
  name: string
  permissions: string[]
  createdAt: string
}

export type AdminUser = {
  id: number
  username: string
  password?: string
  displayName: string
  role: string
  status: string
  createdAt: string
}

export type SEOAudit = {
  score: number
  issues: string[]
  suggestions: string[]
}

export type BackupInfo = {
  file: string
  size: number
  createdAt: string
}

type BackendSiteConfig = {
  siteName?: string
  slogan?: string
  logo?: string
  favicon?: string
  phone?: string
  email?: string
  address?: string
  icp?: string
  domain?: string
  themePrimary?: string
  seoTitle?: string
  seoKeywords?: string
  seoDescription?: string
  ogImage?: string
}

type BackendNavigationItem = {
  id?: number
  title?: string
  path?: string
  position?: string
  target?: string
  sort?: number
  enabled?: boolean
}

type BackendPageBlock = {
  id?: number
  blockKey?: string
  title?: string
  subtitle?: string
  content?: string
  image?: string
  actionText?: string
  actionLink?: string
  sort?: number
  status?: string
  extra?: Record<string, string>
}

type BackendPage = {
  id?: number
  key?: string
  title?: string
  path?: string
  status?: string
  seo?: Partial<SEO>
  blocks?: BackendPageBlock[]
  updatedAt?: string
}

type BackendProduct = {
  id?: number
  title?: string
  slug?: string
  icon?: string
  summary?: string
  description?: string
  features?: string[]
  metrics?: Metric[]
  sort?: number
  status?: string
  seo?: Partial<SEO>
  updatedAt?: string
}

type BackendContentItem = {
  id?: number
  type?: string
  title?: string
  slug?: string
  category?: string
  cover?: string
  summary?: string
  content?: string
  tags?: string[]
  status?: string
  recommended?: boolean
  publishedAt?: string
  updatedAt?: string
  seo?: Partial<SEO>
}

type BackendResource = {
  id?: number
  title?: string
  slug?: string
  category?: string
  summary?: string
  fileUrl?: string
  needLead?: boolean
  tags?: string[]
  status?: string
  publishedAt?: string
  seo?: Partial<SEO>
}

type BackendRelease = {
  id?: number
  version?: string
  title?: string
  summary?: string
  packageUrl?: string
  checksum?: string
  target?: string
  status?: string
  publishedAt?: string
  updatedAt?: string
  highlights?: string[]
}

type BackendDashboard = {
  pageCount?: number
  productCount?: number
  solutionCount?: number
  caseCount?: number
  newsCount?: number
  releaseCount?: number
  contentCount?: number
  leadCount?: number
  newLeadCount?: number
  seoScore?: number
  seoIssues?: BackendSEOIssue[]
  updatedAt?: string
}

type BackendSEOIssue = {
  path?: string
  title?: string
  level?: string
  message?: string
}

type BackendSession = {
  token: string
  username: string
  displayName: string
  role: string
  expiresAt: string
}

const headers = {
  'Content-Type': 'application/json'
}

const defaultHeroMetrics: Metric[] = [
  { value: '8+', label: '核心业务模块' },
  { value: '30%+', label: '协同效率提升' },
  { value: '7×24', label: '在线运营更新' }
]

const defaultValueFeatures: Feature[] = [
  { icon: '✦', title: '统一数据底座', text: '客户、合同、财务、生产、项目、OA 与知识文档共享同一套经营数据。' },
  { icon: '⬡', title: '智能流程协同', text: '用 AI 工作流辅助判断、提醒、分析和内容生成，减少重复管理动作。' },
  { icon: '◈', title: '官网在线发布', text: '内容、SEO、线索、资源和备份通过管理后台维护，前台实时生效。' }
]

function token() {
  return localStorage.getItem('dt-site-admin-token') || ''
}

async function requestData<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...headers,
      ...(init.headers || {}),
      ...(token() ? { Authorization: `Bearer ${token()}` } : {})
    }
  })
  const payload = (await response.json()) as ApiResponse<T>
  const successCode = payload.code === 0 || payload.code === 200 || (payload.code >= 200 && payload.code < 300)
  if (!response.ok || !successCode) {
    throw new Error(payload.message || '请求失败')
  }
  return payload.data
}

function emptySEO(): SEO {
  return { title: '', keywords: '', description: '', canonical: '', ogTitle: '', ogDescription: '', ogImage: '', schema: '' }
}

function normalizeSEO(seo?: Partial<SEO>, fallback?: Partial<SEO>): SEO {
  return {
    title: seo?.title || fallback?.title || '',
    keywords: seo?.keywords || fallback?.keywords || '',
    description: seo?.description || fallback?.description || '',
    canonical: seo?.canonical || fallback?.canonical || '',
    ogTitle: seo?.ogTitle || fallback?.ogTitle || seo?.title || fallback?.title || '',
    ogDescription: seo?.ogDescription || fallback?.ogDescription || seo?.description || fallback?.description || '',
    ogImage: seo?.ogImage || fallback?.ogImage || '',
    schema: seo?.schema || fallback?.schema || ''
  }
}

function siteSEO(site: BackendSiteConfig): SEO {
  return normalizeSEO(
    {
      title: site.seoTitle || site.siteName || '',
      keywords: site.seoKeywords || '',
      description: site.seoDescription || '',
      canonical: site.domain || '',
      ogTitle: site.seoTitle || site.siteName || '',
      ogDescription: site.seoDescription || '',
      ogImage: site.ogImage || '',
      schema: ''
    },
    emptySEO()
  )
}

function fromSiteConfig(site: BackendSiteConfig): SiteConfig {
  const seo = siteSEO(site)
  return {
    name: site.siteName || 'DT 企业智能管理系统',
    subtitle: site.slogan || '',
    slogan: site.slogan || '',
    description: site.seoDescription || seo.description,
    logo: site.logo || 'DT',
    domain: site.domain || '',
    phone: site.phone || '',
    email: site.email || '',
    address: site.address || '',
    icp: site.icp || '',
    favicon: site.favicon || '',
    themePrimary: site.themePrimary || '#8B5CF6',
    seo
  }
}

function toSiteConfig(site: SiteConfig): BackendSiteConfig {
  return {
    siteName: site.name,
    slogan: site.slogan || site.subtitle,
    logo: site.logo,
    favicon: site.favicon || '',
    phone: site.phone,
    email: site.email,
    address: site.address,
    icp: site.icp,
    domain: site.domain || site.seo.canonical,
    themePrimary: site.themePrimary || '#8B5CF6',
    seoTitle: site.seo.title || site.name,
    seoKeywords: site.seo.keywords,
    seoDescription: site.seo.description || site.description,
    ogImage: site.seo.ogImage
  }
}

function fromNavigationItem(item: BackendNavigationItem, index: number): NavigationItem {
  return {
    id: item.id,
    label: item.title || '未命名导航',
    path: item.path || '/',
    order: item.sort || index + 1,
    visible: item.enabled !== false,
    position: item.position || 'header',
    target: item.target || '_self'
  }
}

function toNavigationItem(item: NavigationItem, index: number): BackendNavigationItem {
  return {
    id: item.id || index + 1,
    title: item.label,
    path: item.path,
    position: item.position || 'header',
    target: item.target || '_self',
    sort: item.order || index + 1,
    enabled: item.visible
  }
}

function fromPage(page: BackendPage): Page {
  const blocks = (page.blocks || []).map(fromPageBlock).sort((a, b) => a.order - b.order)
  const fallbackSummary = blocks.find((block) => block.subtitle || block.content)?.subtitle || blocks.find((block) => block.content)?.content || ''
  const path = page.path || (page.key === 'home' ? '/' : `/${page.key || ''}`)
  return {
    id: page.id || 0,
    slug: page.key || path.replace(/^\//, '') || 'home',
    title: page.title || '',
    summary: fallbackSummary,
    path,
    seo: normalizeSEO(page.seo, { title: page.title || '', description: fallbackSummary, canonical: path }),
    blocks,
    status: page.status || 'published',
    updatedAt: page.updatedAt || ''
  }
}

function toPage(page: Page): BackendPage {
  return {
    id: page.id,
    key: page.slug,
    title: page.title,
    path: page.path || (page.slug === 'home' ? '/' : `/${page.slug}`),
    status: page.status,
    seo: page.seo,
    blocks: page.blocks.map(toPageBlock),
    updatedAt: page.updatedAt
  }
}

function fromPageBlock(block: BackendPageBlock): PageBlock {
  const metrics = readJSONList<Metric>(block.extra?.metrics, block.blockKey === 'hero' ? defaultHeroMetrics : [])
  const features = readJSONList<Feature>(block.extra?.features, block.blockKey === 'value' ? defaultValueFeatures : [])
  return {
    id: block.id || 0,
    type: block.blockKey || 'section',
    title: block.title || '',
    subtitle: block.subtitle || '',
    content: block.content || '',
    image: block.image || '',
    metrics,
    features,
    cta: {
      title: block.title || '',
      text: block.content || '',
      primaryText: block.actionText || '了解更多',
      primaryLink: block.actionLink || '#contact',
      secondaryText: '',
      secondaryLink: ''
    },
    order: block.sort || 0,
    visible: block.status !== 'draft' && block.status !== 'hidden',
    extra: block.extra || {}
  }
}

function toPageBlock(block: PageBlock): BackendPageBlock {
  return {
    id: block.id,
    blockKey: block.type,
    title: block.title,
    subtitle: block.subtitle,
    content: block.content,
    image: block.image,
    actionText: block.cta.primaryText,
    actionLink: block.cta.primaryLink,
    sort: block.order,
    status: block.visible ? 'published' : 'draft',
    extra: {
      ...(block.extra || {}),
      metrics: JSON.stringify(block.metrics || []),
      features: JSON.stringify(block.features || [])
    }
  }
}

function fromProduct(product: BackendProduct): Product {
  const features = product.features || []
  return {
    id: product.id || 0,
    slug: product.slug || '',
    title: product.title || '',
    summary: product.summary || '',
    icon: iconGlyph(product.icon || ''),
    tags: features,
    highlights: features,
    metrics: product.metrics || [],
    detail: product.description || '',
    seo: normalizeSEO(product.seo, { title: product.title || '', description: product.summary || '' }),
    status: product.status || 'published',
    order: product.sort || 0,
    updatedAt: product.updatedAt || ''
  }
}

function toProduct(product: Product): BackendProduct {
  return {
    id: product.id,
    title: product.title,
    slug: product.slug,
    icon: product.icon,
    summary: product.summary,
    description: product.detail,
    features: unique([...(product.tags || []), ...(product.highlights || [])]),
    metrics: product.metrics || [],
    sort: product.order,
    status: product.status,
    seo: product.seo,
    updatedAt: product.updatedAt
  }
}

function fromContentItem(item: BackendContentItem, index: number): ContentItem {
  return {
    id: item.id || 0,
    slug: item.slug || '',
    title: item.title || '',
    summary: item.summary || '',
    category: item.category || '',
    cover: item.cover || '',
    tags: item.tags || [],
    body: item.content || '',
    type: item.type || '',
    recommended: item.recommended || false,
    publishedAt: item.publishedAt || '',
    seo: normalizeSEO(item.seo, { title: item.title || '', description: item.summary || '' }),
    status: item.status || 'published',
    order: index + 1,
    updatedAt: item.updatedAt || ''
  }
}

function toContentItem(item: ContentItem, kind: string): BackendContentItem {
  return {
    id: item.id,
    type: item.type || kind,
    title: item.title,
    slug: item.slug,
    category: item.category,
    cover: item.cover,
    summary: item.summary,
    content: item.body,
    tags: item.tags,
    status: item.status,
    recommended: item.recommended || false,
    publishedAt: item.publishedAt || item.updatedAt || new Date().toISOString(),
    updatedAt: item.updatedAt,
    seo: item.seo
  }
}

function fromResource(item: BackendResource, index: number): Resource {
  return {
    id: item.id || 0,
    title: item.title || '',
    category: item.category || '',
    summary: item.summary || '',
    link: item.fileUrl || '',
    order: index + 1,
    status: item.status || 'published',
    slug: item.slug || '',
    needLead: item.needLead || false,
    tags: item.tags || [],
    publishedAt: item.publishedAt || '',
    seo: normalizeSEO(item.seo, { title: item.title || '', description: item.summary || '' })
  }
}

function fromRelease(item: BackendRelease): Release {
  return {
    id: item.id || 0,
    version: item.version || '',
    title: item.title || '',
    summary: item.summary || '',
    packageUrl: item.packageUrl || '',
    checksum: item.checksum || '',
    target: item.target || '',
    status: item.status || 'published',
    publishedAt: item.publishedAt || '',
    updatedAt: item.updatedAt || '',
    highlights: item.highlights || []
  }
}

function toRelease(item: Release): BackendRelease {
  return {
    id: item.id,
    version: item.version,
    title: item.title,
    summary: item.summary,
    packageUrl: item.packageUrl,
    checksum: item.checksum,
    target: item.target,
    status: item.status,
    publishedAt: item.publishedAt || new Date().toISOString(),
    updatedAt: item.updatedAt,
    highlights: item.highlights || []
  }
}

function toResource(item: Resource): BackendResource {
  return {
    id: item.id,
    title: item.title,
    slug: item.slug || slugify(item.title),
    category: item.category,
    summary: item.summary,
    fileUrl: item.link,
    needLead: item.needLead || false,
    tags: item.tags || [],
    status: item.status,
    publishedAt: item.publishedAt || new Date().toISOString(),
    seo: item.seo || normalizeSEO({ title: item.title, description: item.summary })
  }
}

function fromDashboard(data: BackendDashboard): DashboardStats {
  const issueCount = data.seoIssues?.length || 0
  return {
    pageCount: data.pageCount || 0,
    productCount: data.productCount || 0,
    solutionCount: data.solutionCount || data.contentCount || 0,
    caseCount: data.caseCount || 0,
    newsCount: data.newsCount || 0,
    releaseCount: data.releaseCount || 0,
    leadCount: data.leadCount || 0,
    newLeadCount: data.newLeadCount || 0,
    seoScore: data.seoScore || Math.max(60, 100 - issueCount * 8),
    updatedAt: data.updatedAt || ''
  }
}

function fromSEOAudit(items: BackendSEOIssue[]): SEOAudit {
  const issues = (items || []).map((item) => `${item.path || '/'}：${item.message || 'SEO 待优化'}`)
  return {
    score: Math.max(60, 100 - issues.length * 8),
    issues,
    suggestions: issues.length ? ['补齐每个页面的标题、关键词、描述、canonical 与结构化数据。', '保持核心关键词自然分布在 H1、首屏文案、内容段落与链接锚文本中。'] : ['当前核心页面 SEO 基础配置完整，可继续优化长尾关键词内容。']
  }
}

function fromSession(session: BackendSession) {
  return {
    token: session.token,
    user: {
      id: 0,
      username: session.username,
      displayName: session.displayName,
      role: session.role,
      status: 'active',
      createdAt: ''
    },
    expiresAt: session.expiresAt
  }
}

function readJSONList<T>(value: string | undefined, fallback: T[]): T[] {
  if (!value) return fallback
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed as T[] : fallback
  } catch {
    return fallback
  }
}

function iconGlyph(value: string) {
  const icons: Record<string, string> = {
    spark: '✦',
    contract: '◈',
    factory: '⬡',
    ai: '✺'
  }
  return icons[value] || value || '✦'
}

function unique(items: string[]) {
  return Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)))
}

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, '-').replace(/^-+|-+$/g, '') || `resource-${Date.now()}`
}

function toLead(lead: Lead): Lead {
  return {
    ...lead,
    company: lead.company || '',
    email: lead.email || '',
    demandType: lead.demandType || '',
    status: lead.status || 'new',
    sourcePath: lead.sourcePath || '官网后台',
    followups: lead.followups || []
  }
}

export const api = {
  public: {
    site: () => requestData<BackendSiteConfig>('/api/public/site').then(fromSiteConfig),
    navigation: () => requestData<BackendNavigationItem[]>('/api/public/navigation').then((items) => items.map(fromNavigationItem)),
    page: (slug: string) => requestData<BackendPage>(`/api/public/pages/${slug}`).then(fromPage),
    seo: (slug: string) => requestData<Partial<SEO>>(`/api/public/seo/${slug}`).then((seo) => normalizeSEO(seo)),
    products: () => requestData<BackendProduct[]>('/api/public/products').then((items) => items.map(fromProduct)),
    solutions: () => requestData<BackendContentItem[]>('/api/public/solutions').then((items) => items.map(fromContentItem)),
    cases: () => requestData<BackendContentItem[]>('/api/public/cases').then((items) => items.map(fromContentItem)),
    news: () => requestData<BackendContentItem[]>('/api/public/news').then((items) => items.map(fromContentItem)),
    resources: () => requestData<{ resources: BackendResource[]; faqs: FAQ[] }>('/api/public/resources').then((data) => ({ resources: data.resources.map(fromResource), faqs: data.faqs || [] })),
    releases: () => requestData<BackendRelease[]>('/api/public/releases').then((items) => items.map(fromRelease)),
    lead: (lead: Lead) => requestData<Lead>('/api/public/leads', { method: 'POST', body: JSON.stringify(toLead(lead)) })
  },
  admin: {
    login: (username: string, password: string) =>
      requestData<BackendSession>('/api/admin/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      }).then(fromSession),
    logout: () => requestData<null>('/api/admin/auth/logout', { method: 'POST' }),
    dashboard: () => requestData<BackendDashboard>('/api/admin/dashboard').then(fromDashboard),
    site: () => requestData<BackendSiteConfig>('/api/admin/site').then(fromSiteConfig),
    updateSite: (site: SiteConfig) => requestData<BackendSiteConfig>('/api/admin/site', { method: 'PUT', body: JSON.stringify(toSiteConfig(site)) }).then(fromSiteConfig),
    navigation: () => requestData<BackendNavigationItem[]>('/api/admin/navigation').then((items) => items.map(fromNavigationItem)),
    updateNavigation: (items: NavigationItem[]) =>
      requestData<BackendNavigationItem[]>('/api/admin/navigation', { method: 'PUT', body: JSON.stringify(items.map(toNavigationItem)) }).then((data) => data.map(fromNavigationItem)),
    pages: () => requestData<BackendPage[]>('/api/admin/pages').then((items) => items.map(fromPage)),
    updatePages: (items: Page[]) => requestData<BackendPage[]>('/api/admin/pages', { method: 'PUT', body: JSON.stringify(items.map(toPage)) }).then((data) => data.map(fromPage)),
    products: () => requestData<BackendProduct[]>('/api/admin/products').then((items) => items.map(fromProduct)),
    updateProducts: (items: Product[]) =>
      requestData<BackendProduct[]>('/api/admin/products', { method: 'PUT', body: JSON.stringify(items.map(toProduct)) }).then((data) => data.map(fromProduct)),
    solutions: () => requestData<BackendContentItem[]>('/api/admin/solutions').then((items) => items.map(fromContentItem)),
    updateSolutions: (items: ContentItem[]) =>
      requestData<BackendContentItem[]>('/api/admin/solutions', { method: 'PUT', body: JSON.stringify(items.map((item) => toContentItem(item, 'solution'))) }).then((data) => data.map(fromContentItem)),
    cases: () => requestData<BackendContentItem[]>('/api/admin/cases').then((items) => items.map(fromContentItem)),
    updateCases: (items: ContentItem[]) => requestData<BackendContentItem[]>('/api/admin/cases', { method: 'PUT', body: JSON.stringify(items.map((item) => toContentItem(item, 'case'))) }).then((data) => data.map(fromContentItem)),
    news: () => requestData<BackendContentItem[]>('/api/admin/news').then((items) => items.map(fromContentItem)),
    updateNews: (items: ContentItem[]) => requestData<BackendContentItem[]>('/api/admin/news', { method: 'PUT', body: JSON.stringify(items.map((item) => toContentItem(item, 'news'))) }).then((data) => data.map(fromContentItem)),
    resources: () => requestData<{ resources: BackendResource[]; faqs: FAQ[] }>('/api/admin/resources').then((data) => ({ resources: (data.resources || []).map(fromResource), faqs: data.faqs || [] })),
    updateResources: (items: PublicResources) =>
      requestData<{ resources: BackendResource[]; faqs: FAQ[] }>('/api/admin/resources', { method: 'PUT', body: JSON.stringify({ resources: items.resources.map(toResource), faqs: items.faqs }) }).then((data) => ({ resources: (data.resources || []).map(fromResource), faqs: data.faqs || [] })),
    releases: () => requestData<BackendRelease[]>('/api/admin/releases').then((items) => (items || []).map(fromRelease)),
    saveReleases: (items: Release[]) => requestData<BackendRelease[]>('/api/admin/releases', { method: 'PUT', body: JSON.stringify(items.map(toRelease)) }).then((saved) => (saved || []).map(fromRelease)),
    leads: () => requestData<Lead[] | null>('/api/admin/leads').then((items) => (items || []).map(toLead)),
    updateLeads: (items: Lead[]) => requestData<Lead[]>('/api/admin/leads', { method: 'PUT', body: JSON.stringify(items.map(toLead)) }).then((saved) => (saved || []).map(toLead)),
    seoAudit: () => requestData<BackendSEOIssue[]>('/api/admin/seo/audit').then(fromSEOAudit),
    logs: () => requestData<OperationLog[]>('/api/admin/logs'),
    roles: () => requestData<Role[]>('/api/admin/roles'),
    updateRoles: (items: Role[]) => requestData<Role[]>('/api/admin/roles', { method: 'PUT', body: JSON.stringify(items) }),
    users: () => requestData<AdminUser[]>('/api/admin/users'),
    updateUsers: async (items: AdminUser[]) => {
      await requestData<boolean>('/api/admin/users', { method: 'PUT', body: JSON.stringify(items) })
      return requestData<AdminUser[]>('/api/admin/users')
    },
    backups: () => requestData<BackupInfo[]>('/api/admin/backups'),
    createBackup: () => requestData<BackupInfo>('/api/admin/backups', { method: 'POST' })
  }
}
