import { FormEvent, useEffect, useState } from 'react'
import type { AdminUser, BackupInfo, ContentItem, DashboardStats, FAQ, Lead, NavigationItem, OperationLog, Page, PageBlock, Product, PublicResources, Release, Resource, Role, SEO, SEOAudit, SiteConfig } from './api'
import { api } from './api'

type AdminTab = 'dashboard' | 'site' | 'navigation' | 'pages' | 'products' | 'solutions' | 'cases' | 'news' | 'resources' | 'releases' | 'leads' | 'seo' | 'users' | 'logs' | 'backups'

type AdminData = {
  dashboard: DashboardStats | null
  site: SiteConfig | null
  navigation: NavigationItem[]
  pages: Page[]
  products: Product[]
  solutions: ContentItem[]
  cases: ContentItem[]
  news: ContentItem[]
  resources: PublicResources | null
  releases: Release[]
  leads: Lead[]
  audit: SEOAudit | null
  users: AdminUser[]
  roles: Role[]
  logs: OperationLog[]
  backups: BackupInfo[]
}

const tabs: Array<{ key: AdminTab; label: string; desc: string }> = [
  { key: 'dashboard', label: '工作台', desc: '查看官网运营数据、最新线索和最近操作' },
  { key: 'site', label: '站点配置', desc: '统一维护官网名称、联系方式、域名、备案与全站 SEO' },
  { key: 'navigation', label: '导航管理', desc: '维护顶部导航、页脚导航、路径、排序与打开方式' },
  { key: 'pages', label: '页面内容', desc: '维护每个独立页面的标题、路径、SEO 与页面区块' },
  { key: 'products', label: '产品能力', desc: '维护首页与产品页展示的核心产品能力卡片' },
  { key: 'solutions', label: '解决方案', desc: '维护解决方案页面和首页方案卡片内容' },
  { key: 'cases', label: '客户案例', desc: '维护客户案例、行业分类、成果亮点与 SEO' },
  { key: 'news', label: '新闻动态', desc: '维护产品动态、行业洞察和数字化管理内容' },
  { key: 'resources', label: '资源 FAQ', desc: '维护资料下载、FAQ、资源状态和线索收集开关' },
  { key: 'releases', label: '版本发布', desc: '发布 DT 企业管理系统客户部署升级包和校验信息' },
  { key: 'leads', label: '线索管理', desc: '维护官网咨询线索、跟进状态和客户需求' },
  { key: 'seo', label: 'SEO 体检', desc: '检查核心页面 SEO 覆盖情况和优化建议' },
  { key: 'users', label: '用户角色', desc: '维护后台用户、角色和权限点' },
  { key: 'logs', label: '操作日志', desc: '查看后台登录、保存、备份等操作记录' },
  { key: 'backups', label: '数据备份', desc: '创建和查看官网后台数据备份' }
]

const initialData: AdminData = {
  dashboard: null,
  site: null,
  navigation: [],
  pages: [],
  products: [],
  solutions: [],
  cases: [],
  news: [],
  resources: null,
  releases: [],
  leads: [],
  audit: null,
  users: [],
  roles: [],
  logs: [],
  backups: []
}

export function AdminApp() {
  const [logged, setLogged] = useState(Boolean(localStorage.getItem('dt-site-admin-token')))
  const [loginForm, setLoginForm] = useState({ username: 'admin', password: '' })
  const [tab, setTab] = useState<AdminTab>('dashboard')
  const [data, setData] = useState<AdminData>(initialData)
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!logged) return
    void loadAll()
  }, [logged])

  async function loadAll() {
    setLoading(true)
    try {
      const [dashboard, site, navigation, pages, products, solutions, cases, news, resources, releases, leads, audit, users, roles, logs, backups] = await Promise.all([
        api.admin.dashboard(), api.admin.site(), api.admin.navigation(), api.admin.pages(), api.admin.products(), api.admin.solutions(), api.admin.cases(), api.admin.news(), api.admin.resources(), api.admin.releases(), api.admin.leads(), api.admin.seoAudit(), api.admin.users(), api.admin.roles(), api.admin.logs(), api.admin.backups()
      ])
      setData({ dashboard, site, navigation, pages, products, solutions, cases, news, resources, releases, leads, audit, users, roles, logs, backups })
      setNotice('数据已同步')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '后台数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      const result = await api.admin.login(loginForm.username, loginForm.password)
      localStorage.setItem('dt-site-admin-token', result.token)
      setLogged(true)
      setNotice(`欢迎回来，${result.user.displayName}`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '登录失败')
    }
  }

  async function logout() {
    try {
      await api.admin.logout()
    } finally {
      localStorage.removeItem('dt-site-admin-token')
      setLogged(false)
      setData(initialData)
    }
  }

  async function saveCurrent() {
    setLoading(true)
    try {
      if (tab === 'site' && data.site) await api.admin.updateSite(data.site)
      if (tab === 'navigation') await api.admin.updateNavigation(data.navigation)
      if (tab === 'pages') await api.admin.updatePages(data.pages)
      if (tab === 'products') await api.admin.updateProducts(data.products)
      if (tab === 'solutions') await api.admin.updateSolutions(data.solutions)
      if (tab === 'cases') await api.admin.updateCases(data.cases)
      if (tab === 'news') await api.admin.updateNews(data.news)
      if (tab === 'resources' && data.resources) await api.admin.updateResources(data.resources)
      if (tab === 'releases') await api.admin.saveReleases(data.releases)
      if (tab === 'leads') await api.admin.updateLeads(data.leads)
      if (tab === 'users') {
        await api.admin.updateUsers(data.users)
        await api.admin.updateRoles(data.roles)
      }
      await loadAll()
      setNotice(tab === 'releases' ? '保存成功，DT 企业管理系统版本发布已更新' : '保存成功，后台配置已发布到官网')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '保存失败')
    } finally {
      setLoading(false)
    }
  }

  async function createBackup() {
    setLoading(true)
    try {
      await api.admin.createBackup()
      const backups = await api.admin.backups()
      setData((value) => ({ ...value, backups }))
      setNotice('备份创建成功')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '备份失败')
    } finally {
      setLoading(false)
    }
  }

  if (!logged) {
    return (
      <main className="admin-login-page">
        <section className="login-card">
          <span className="eyebrow">DT Admin Console</span>
          <h1>官网管理后台</h1>
          <p>登录后可管理官网内容、SEO、线索、角色用户、日志、备份与 DT 企业管理系统版本发布，支撑客户部署系统持续升级。</p>
          <form onSubmit={login}>
            <label>账号<input value={loginForm.username} onChange={(event) => setLoginForm({ ...loginForm, username: event.target.value })} /></label>
            <label>密码<input type="password" value={loginForm.password} onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })} placeholder="请输入后台密码" /></label>
            <button className="primary-action">登录后台</button>
          </form>
          {notice ? <p className="form-message">{notice}</p> : null}
        </section>
      </main>
    )
  }

  const currentTab = tabs.find((item) => item.key === tab)

  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <strong>DT 官网后台</strong>
          <span>Official Site Console</span>
        </div>
        <nav>
          {tabs.map((item) => (
            <button className={tab === item.key ? 'active' : ''} key={item.key} onClick={() => setTab(item.key)}><span>{item.label}</span><small>{item.desc}</small></button>
          ))}
        </nav>
      </aside>
      <section className="admin-workspace">
        <header className="admin-topbar">
          <div>
            <span className="eyebrow">{currentTab?.label}</span>
            <h1>{currentTab?.desc}</h1>
          </div>
          <div className="admin-actions">
            <button className="secondary-action" onClick={loadAll} disabled={loading}>刷新</button>
            {isSaveable(tab) ? <button className="primary-action" onClick={saveCurrent} disabled={loading}>保存并发布</button> : null}
            <button className="ghost-action" onClick={logout}>退出</button>
          </div>
        </header>
        {notice ? <div className="admin-notice">{notice}</div> : null}
        {renderPanel(tab, data, setData, createBackup)}
      </section>
    </main>
  )
}

function renderPanel(tab: AdminTab, data: AdminData, setData: (next: AdminData | ((value: AdminData) => AdminData)) => void, createBackup: () => void) {
  if (tab === 'dashboard') return <DashboardPanel data={data} />
  if (tab === 'site' && data.site) return <SitePanel site={data.site} update={(site) => setData((value) => ({ ...value, site }))} />
  if (tab === 'navigation') return <NavigationPanel items={data.navigation} update={(navigation) => setData((value) => ({ ...value, navigation }))} />
  if (tab === 'pages') return <PagePanel items={data.pages} update={(pages) => setData((value) => ({ ...value, pages }))} />
  if (tab === 'products') return <ProductPanel items={data.products} update={(products) => setData((value) => ({ ...value, products }))} />
  if (tab === 'solutions') return <ContentPanel title="解决方案" type="solution" items={data.solutions} update={(solutions) => setData((value) => ({ ...value, solutions }))} />
  if (tab === 'cases') return <ContentPanel title="客户案例" type="case" items={data.cases} update={(cases) => setData((value) => ({ ...value, cases }))} />
  if (tab === 'news') return <ContentPanel title="新闻动态" type="news" items={data.news} update={(news) => setData((value) => ({ ...value, news }))} />
  if (tab === 'resources' && data.resources) return <ResourcesPanel data={data.resources} update={(resources) => setData((value) => ({ ...value, resources }))} />
  if (tab === 'releases') return <ReleasePanel items={data.releases} update={(releases) => setData((value) => ({ ...value, releases }))} />
  if (tab === 'leads') return <LeadPanel items={data.leads} update={(leads) => setData((value) => ({ ...value, leads }))} />
  if (tab === 'seo') return <SEOPanel audit={data.audit} pages={data.pages} products={data.products} />
  if (tab === 'users') return <UsersPanel users={data.users} roles={data.roles} updateUsers={(users) => setData((value) => ({ ...value, users }))} updateRoles={(roles) => setData((value) => ({ ...value, roles }))} />
  if (tab === 'logs') return <LogsPanel items={data.logs} />
  if (tab === 'backups') return <BackupsPanel items={data.backups} createBackup={createBackup} />
  return <div className="admin-card">数据加载中</div>
}

function DashboardPanel({ data }: { data: AdminData }) {
  const stats = data.dashboard
  const cards = [
    ['页面', stats?.pageCount || 0], ['产品', stats?.productCount || 0], ['解决方案', stats?.solutionCount || 0], ['案例', stats?.caseCount || 0], ['版本', stats?.releaseCount || 0], ['线索', stats?.leadCount || 0], ['SEO 分', stats?.seoScore || 0]
  ]
  return (
    <div className="admin-grid-panels">
      {cards.map(([label, value]) => <div className="admin-stat-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}
      <div className="admin-card wide"><h2>待跟进线索</h2>{data.leads.length ? data.leads.slice(0, 6).map((lead) => <p key={lead.id}>{lead.name} · {lead.phone} · {lead.status}</p>) : <EmptyState text="暂无线索，可在“线索管理”新增或等待前台表单提交。" />}</div>
      <div className="admin-card wide"><h2>最新操作</h2>{data.logs.length ? data.logs.slice(0, 6).map((log) => <p key={log.id}>{log.user} · {log.action} · {log.createdAt}</p>) : <EmptyState text="暂无操作记录。" />}</div>
    </div>
  )
}

function SitePanel({ site, update }: { site: SiteConfig; update: (site: SiteConfig) => void }) {
  return <PanelIntro title="站点配置" text="这里是官网所有公开联系方式的统一来源，前台电话、邮箱、地址、页脚和联系区都会读取这些配置。"><div className="admin-form-grid">
    {field('站点名称', site.name, (name) => update({ ...site, name }))}
    {field('LOGO 文案', site.logo, (logo) => update({ ...site, logo }))}
    {field('副标题', site.subtitle, (subtitle) => update({ ...site, subtitle }))}
    {field('主标语', site.slogan, (slogan) => update({ ...site, slogan }))}
    {field('官网域名', site.domain, (domain) => update({ ...site, domain }))}
    {field('联系电话', site.phone, (phone) => update({ ...site, phone }))}
    {field('联系邮箱', site.email, (email) => update({ ...site, email }))}
    {field('地址', site.address, (address) => update({ ...site, address }))}
    {field('ICP备案', site.icp, (icp) => update({ ...site, icp }))}
    {field('主题色', site.themePrimary || '', (themePrimary) => update({ ...site, themePrimary }))}
    {textareaField('站点描述', site.description, (description) => update({ ...site, description }))}
    <SEOEditor seo={site.seo} update={(seo) => update({ ...site, seo })} />
  </div></PanelIntro>
}

function NavigationPanel({ items, update }: { items: NavigationItem[]; update: (items: NavigationItem[]) => void }) {
  return <EditableList items={items} update={update} emptyText="暂无导航，点击新增创建顶部或页脚导航。" create={() => ({ id: Date.now(), label: '新导航', path: '/', order: items.length + 1, visible: true, position: 'header', target: '_self' })} render={(item, index, setItem) => <>
    {field('名称', item.label, (label) => setItem({ ...item, label }))}
    {field('路径', item.path, (path) => setItem({ ...item, path }))}
    {selectField('位置', item.position || 'header', ['header', 'footer'], (position) => setItem({ ...item, position }))}
    {selectField('打开方式', item.target || '_self', ['_self', '_blank'], (target) => setItem({ ...item, target }))}
    {numberField('排序', item.order, (order) => setItem({ ...item, order }))}
    {switchField('显示', item.visible, (visible) => setItem({ ...item, visible }))}
  </>} />
}

function PagePanel({ items, update }: { items: Page[]; update: (items: Page[]) => void }) {
  return <EditableList items={items} update={update} emptyText="暂无页面，点击新增创建独立页面。" create={() => ({ id: Date.now(), slug: 'new-page', title: '新页面', summary: '', path: '/new-page', seo: emptySEO(), blocks: [newPageBlock()], status: 'draft', updatedAt: new Date().toISOString() })} render={(item, index, setItem) => <>
    {field('页面标题', item.title, (title) => setItem({ ...item, title }))}
    {field('页面标识', item.slug, (slug) => setItem({ ...item, slug }))}
    {field('独立页面路径', item.path, (path) => setItem({ ...item, path }))}
    {selectField('状态', item.status, ['published', 'draft', 'hidden'], (status) => setItem({ ...item, status }))}
    {textareaField('摘要', item.summary, (summary) => setItem({ ...item, summary }))}
    <PageBlockEditor blocks={item.blocks || []} update={(blocks) => setItem({ ...item, blocks })} />
    <SEOEditor seo={item.seo} update={(seo) => setItem({ ...item, seo })} />
  </>} />
}

function ProductPanel({ items, update }: { items: Product[]; update: (items: Product[]) => void }) {
  return <EditableList items={items} update={update} emptyText="暂无产品能力，点击新增创建首页产品卡片。" create={() => ({ id: Date.now(), slug: 'new-product', title: '新产品', summary: '', icon: '✦', tags: [], highlights: [], metrics: [], detail: '', seo: emptySEO(), status: 'draft', order: items.length + 1, updatedAt: new Date().toISOString() })} render={(item, index, setItem) => <>
    {field('标题', item.title, (title) => setItem({ ...item, title }))}
    {field('标识', item.slug, (slug) => setItem({ ...item, slug }))}
    {field('图标', item.icon, (icon) => setItem({ ...item, icon }))}
    {numberField('排序', item.order, (order) => setItem({ ...item, order }))}
    {selectField('状态', item.status, ['published', 'draft', 'hidden'], (status) => setItem({ ...item, status }))}
    {field('标签，逗号分隔', (item.tags || []).join(','), (tags) => setItem({ ...item, tags: split(tags) }))}
    {field('亮点，逗号分隔', (item.highlights || []).join(','), (highlights) => setItem({ ...item, highlights: split(highlights) }))}
    {textareaField('摘要', item.summary, (summary) => setItem({ ...item, summary }))}
    {textareaField('详情', item.detail, (detail) => setItem({ ...item, detail }))}
    <SEOEditor seo={item.seo} update={(seo) => setItem({ ...item, seo })} />
  </>} />
}

function ContentPanel({ title, type, items, update }: { title: string; type: string; items: ContentItem[]; update: (items: ContentItem[]) => void }) {
  return <EditableList items={items} update={update} emptyText={`暂无${title}，点击新增创建内容。`} create={() => ({ id: Date.now(), slug: 'new-content', title: `新${title}`, summary: '', category: title, cover: '', tags: [], body: '', type, recommended: true, seo: emptySEO(), status: 'draft', order: items.length + 1, publishedAt: new Date().toISOString(), updatedAt: new Date().toISOString() })} render={(item, index, setItem) => <>
    {field('标题', item.title, (value) => setItem({ ...item, title: value }))}
    {field('标识', item.slug, (value) => setItem({ ...item, slug: value }))}
    {field('分类', item.category, (value) => setItem({ ...item, category: value }))}
    {field('封面图地址', item.cover, (value) => setItem({ ...item, cover: value }))}
    {numberField('排序', item.order, (value) => setItem({ ...item, order: value }))}
    {selectField('状态', item.status, ['published', 'draft', 'hidden'], (value) => setItem({ ...item, status: value }))}
    {switchField('推荐展示', Boolean(item.recommended), (recommended) => setItem({ ...item, recommended }))}
    {field('标签，逗号分隔', (item.tags || []).join(','), (value) => setItem({ ...item, tags: split(value) }))}
    {field('发布时间', item.publishedAt || '', (publishedAt) => setItem({ ...item, publishedAt }))}
    {textareaField('摘要', item.summary, (value) => setItem({ ...item, summary: value }))}
    {textareaField('正文', item.body, (value) => setItem({ ...item, body: value }))}
    <SEOEditor seo={item.seo} update={(seo) => setItem({ ...item, seo })} />
  </>} />
}

function ResourcesPanel({ data, update }: { data: PublicResources; update: (data: PublicResources) => void }) {
  return <div className="admin-stack"><PanelIntro title="资源下载" text="资料、手册、白皮书等资源会在资源中心展示，可设置是否需要线索登记。"><EditableList items={data.resources} update={(resources) => update({ ...data, resources })} emptyText="暂无资源，点击新增创建资料。" create={() => ({ id: Date.now(), title: '新资源', category: '资料', summary: '', link: '#', order: data.resources.length + 1, status: 'published', slug: 'new-resource', needLead: false, tags: [], publishedAt: new Date().toISOString(), seo: emptySEO() })} render={(item, index, setItem) => <ResourceEditor item={item} setItem={setItem} />} /></PanelIntro><PanelIntro title="FAQ" text="维护官网常见问题，帮助客户自助了解产品、部署与版本更新。"><EditableList items={data.faqs} update={(faqs) => update({ ...data, faqs })} emptyText="暂无 FAQ，点击新增创建问题。" create={() => ({ id: Date.now(), question: '新问题', answer: '答案', category: '产品', sort: data.faqs.length + 1, status: 'published' })} render={(item, index, setItem) => <FAQEditor item={item} setItem={setItem} />} /></PanelIntro></div>
}

function ResourceEditor({ item, setItem }: { item: Resource; setItem: (item: Resource) => void }) {
  return <>
    {field('标题', item.title, (title) => setItem({ ...item, title }))}
    {field('标识', item.slug || '', (slug) => setItem({ ...item, slug }))}
    {field('分类', item.category, (category) => setItem({ ...item, category }))}
    {field('下载/跳转链接', item.link, (link) => setItem({ ...item, link }))}
    {numberField('排序', item.order, (order) => setItem({ ...item, order }))}
    {selectField('状态', item.status, ['published', 'draft', 'hidden'], (status) => setItem({ ...item, status }))}
    {switchField('下载前收集线索', Boolean(item.needLead), (needLead) => setItem({ ...item, needLead }))}
    {field('标签，逗号分隔', (item.tags || []).join(','), (tags) => setItem({ ...item, tags: split(tags) }))}
    {textareaField('摘要', item.summary, (summary) => setItem({ ...item, summary }))}
    <SEOEditor seo={item.seo || emptySEO()} update={(seo) => setItem({ ...item, seo })} />
  </>
}

function FAQEditor({ item, setItem }: { item: FAQ; setItem: (item: FAQ) => void }) {
  return <>
    {field('问题', item.question, (question) => setItem({ ...item, question }))}
    {field('分类', item.category || '', (category) => setItem({ ...item, category }))}
    {numberField('排序', item.sort || 0, (sort) => setItem({ ...item, sort }))}
    {selectField('状态', item.status || 'published', ['published', 'draft', 'hidden'], (status) => setItem({ ...item, status }))}
    {textareaField('答案', item.answer, (answer) => setItem({ ...item, answer }))}
  </>
}

function ReleasePanel({ items, update }: { items: Release[]; update: (items: Release[]) => void }) {
  return <PanelIntro title="DT 企业管理系统版本发布" text="这里维护的是客户部署的 DT 企业管理系统升级包、版本说明、目标环境、校验信息、渠道与升级规则。官网会基于这些数据作为固定域名更新中心。"><EditableList items={items} update={update} emptyText="暂无版本发布，点击新增创建客户部署升级包信息。" create={() => ({ id: Date.now(), version: '1.0.0', title: '新版本发布', summary: '', packageUrl: '', checksum: '', checksumType: 'sha256', manifestUrl: '', target: 'Ubuntu 22.04 x86_64 / Docker Compose', channel: 'stable', platform: 'linux-docker-x64', build: '', packageSize: 0, minSupportedVersion: '1.0.0', forceUpdate: false, dockerImageTags: [], releaseNotesMarkdown: '', status: 'draft', publishedAt: new Date().toISOString(), updatedAt: new Date().toISOString(), highlights: [] })} render={(item, index, setItem) => <>
    {field('版本号', item.version, (version) => setItem({ ...item, version }))}
    {field('标题', item.title, (title) => setItem({ ...item, title }))}
    {field('发布渠道', item.channel || 'stable', (channel) => setItem({ ...item, channel }))}
    {field('平台标识', item.platform || 'linux-docker-x64', (platform) => setItem({ ...item, platform }))}
    {field('构建号', item.build || '', (build) => setItem({ ...item, build }))}
    {field('目标环境', item.target, (target) => setItem({ ...item, target }))}
    {selectField('状态', item.status, ['published', 'draft', 'hidden'], (status) => setItem({ ...item, status }))}
    {field('更新包地址', item.packageUrl, (packageUrl) => setItem({ ...item, packageUrl }))}
    {field('校验码', item.checksum, (checksum) => setItem({ ...item, checksum }))}
    {field('校验算法', item.checksumType || 'sha256', (checksumType) => setItem({ ...item, checksumType }))}
    {field('Manifest 地址', item.manifestUrl || '', (manifestUrl) => setItem({ ...item, manifestUrl }))}
    {numberField('更新包大小（字节）', item.packageSize || 0, (packageSize) => setItem({ ...item, packageSize }))}
    {field('最低可升级版本', item.minSupportedVersion || '', (minSupportedVersion) => setItem({ ...item, minSupportedVersion }))}
    {switchField('是否强制更新', Boolean(item.forceUpdate), (forceUpdate) => setItem({ ...item, forceUpdate }))}
    {field('Docker 镜像标签，逗号分隔', (item.dockerImageTags || []).join(','), (dockerImageTags) => setItem({ ...item, dockerImageTags: split(dockerImageTags) }))}
    {field('发布时间', item.publishedAt, (publishedAt) => setItem({ ...item, publishedAt }))}
    {field('版本亮点，逗号分隔', (item.highlights || []).join(','), (highlights) => setItem({ ...item, highlights: split(highlights) }))}
    {textareaField('版本说明', item.summary, (summary) => setItem({ ...item, summary }))}
    {textareaField('详细发布说明（Markdown）', item.releaseNotesMarkdown || '', (releaseNotesMarkdown) => setItem({ ...item, releaseNotesMarkdown }))}
  </>} /></PanelIntro>
}

function LeadPanel({ items, update }: { items: Lead[]; update: (items: Lead[]) => void }) {
  const statuses = ['new', 'contacted', 'qualified', 'closed', 'invalid']
  return <EditableList items={items} update={update} emptyText="暂无线索，可点击新增录入线下咨询，或等待官网联系表单提交。" create={() => ({ id: Date.now(), name: '新线索', company: '', phone: '', email: '', demandType: '', message: '', status: 'new', sourcePath: '后台录入', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), followups: [] })} render={(item, index, setItem) => <>
    {field('姓名', item.name, (name) => setItem({ ...item, name }))}
    {field('公司', item.company, (company) => setItem({ ...item, company }))}
    {field('电话', item.phone, (phone) => setItem({ ...item, phone }))}
    {field('邮箱', item.email || '', (email) => setItem({ ...item, email }))}
    {field('需求类型', item.demandType || '', (demandType) => setItem({ ...item, demandType }))}
    {selectField('状态', item.status || 'new', statuses, (status) => setItem({ ...item, status }))}
    {field('来源', item.sourcePath || '', (sourcePath) => setItem({ ...item, sourcePath }))}
    {textareaField('需求', item.message, (message) => setItem({ ...item, message }))}
  </>} />
}

function SEOPanel({ audit, pages, products }: { audit: SEOAudit | null; pages: Page[]; products: Product[] }) {
  return <div className="admin-grid-panels"><div className="seo-score"><span>SEO 综合评分</span><strong>{audit?.score || 0}</strong></div><div className="admin-card"><h2>待优化项</h2>{audit?.issues.length ? audit.issues.map((item) => <p key={item}>{item}</p>) : <EmptyState text="暂无严重 SEO 问题。" />}</div><div className="admin-card"><h2>优化建议</h2>{audit?.suggestions.map((item) => <p key={item}>{item}</p>)}</div><div className="admin-card wide"><h2>SEO 覆盖</h2><p>页面 {pages.length} 个，产品 {products.length} 个，均支持标题、关键词、描述、canonical、OG 与结构化数据。</p></div></div>
}

function UsersPanel({ users, roles, updateUsers, updateRoles }: { users: AdminUser[]; roles: Role[]; updateUsers: (items: AdminUser[]) => void; updateRoles: (items: Role[]) => void }) {
  return <div className="admin-stack"><PanelIntro title="后台用户" text="维护可登录官网管理后台的用户。修改密码时填写新密码，不修改则留空。"><EditableList items={users} update={updateUsers} emptyText="暂无用户，点击新增创建后台账号。" create={() => ({ id: Date.now(), username: 'new-user', password: '', displayName: '新用户', role: roles[0]?.name || '内容运营', status: 'active', createdAt: new Date().toISOString() })} render={(item, index, setItem) => <>
    {field('账号', item.username, (username) => setItem({ ...item, username }))}
    {field('显示名', item.displayName, (displayName) => setItem({ ...item, displayName }))}
    {selectField('角色', item.role, roles.map((role) => role.name), (role) => setItem({ ...item, role }))}
    {selectField('状态', item.status, ['active', 'disabled'], (status) => setItem({ ...item, status }))}
    {field('新密码', item.password || '', (password) => setItem({ ...item, password }))}
  </>} /></PanelIntro><PanelIntro title="角色权限" text="维护角色名称和权限点，系统管理员建议保留完整权限。"><EditableList items={roles} update={updateRoles} emptyText="暂无角色，点击新增创建角色。" create={() => ({ id: Date.now(), name: '新角色', permissions: [], createdAt: new Date().toISOString() })} render={(item, index, setItem) => <>
    {field('角色名称', item.name, (name) => setItem({ ...item, name }))}
    {field('权限，逗号分隔', (item.permissions || []).join(','), (permissions) => setItem({ ...item, permissions: split(permissions) }))}
  </>} /></PanelIntro></div>
}

function LogsPanel({ items }: { items: OperationLog[] }) {
  return <div className="table-card"><table><thead><tr><th>用户</th><th>动作</th><th>对象</th><th>IP</th><th>时间</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={item.id}><td>{item.user}</td><td>{item.action}</td><td>{item.targetType}</td><td>{item.ip}</td><td>{item.createdAt}</td></tr>) : <tr><td colSpan={5}>暂无操作日志</td></tr>}</tbody></table></div>
}

function BackupsPanel({ items, createBackup }: { items: BackupInfo[]; createBackup: () => void }) {
  return <div className="admin-stack"><button className="primary-action" onClick={createBackup}>立即创建备份</button><div className="table-card"><table><thead><tr><th>文件</th><th>大小</th><th>时间</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={item.file}><td>{item.file}</td><td>{Math.ceil(item.size / 1024)} KB</td><td>{item.createdAt}</td></tr>) : <tr><td colSpan={3}>暂无备份，点击上方按钮创建。</td></tr>}</tbody></table></div></div>
}

function PageBlockEditor({ blocks, update }: { blocks: PageBlock[]; update: (blocks: PageBlock[]) => void }) {
  return <section className="seo-editor full"><h3>页面区块</h3><button className="secondary-action" type="button" onClick={() => update([...blocks, newPageBlock()])}>新增区块</button>{blocks.length ? blocks.map((block, index) => <div className="block-editor" key={block.id || index}>
    <div className="editor-card-head"><strong>区块 #{index + 1}</strong><button className="ghost-action" type="button" onClick={() => update(blocks.filter((_, blockIndex) => blockIndex !== index))}>删除</button></div>
    {field('类型', block.type, (type) => updateItem(blocks, update, index, { ...block, type }))}
    {field('标题', block.title, (title) => updateItem(blocks, update, index, { ...block, title }))}
    {field('副标题', block.subtitle, (subtitle) => updateItem(blocks, update, index, { ...block, subtitle }))}
    {numberField('排序', block.order, (order) => updateItem(blocks, update, index, { ...block, order }))}
    {switchField('显示', block.visible, (visible) => updateItem(blocks, update, index, { ...block, visible }))}
    {field('按钮文案', block.cta?.primaryText || '', (primaryText) => updateItem(blocks, update, index, { ...block, cta: { ...block.cta, primaryText } }))}
    {field('按钮链接', block.cta?.primaryLink || '', (primaryLink) => updateItem(blocks, update, index, { ...block, cta: { ...block.cta, primaryLink } }))}
    {textareaField('正文', block.content, (content) => updateItem(blocks, update, index, { ...block, content }))}
  </div>) : <EmptyState text="暂无区块，点击新增区块。" />}</section>
}

function SEOEditor({ seo, update }: { seo: SEO; update: (seo: SEO) => void }) {
  return <section className="seo-editor full"><h3>SEO 设置</h3>{field('SEO 标题', seo.title, (title) => update({ ...seo, title }))}{field('关键词', seo.keywords, (keywords) => update({ ...seo, keywords }))}{textareaField('描述', seo.description, (description) => update({ ...seo, description }))}{field('Canonical', seo.canonical, (canonical) => update({ ...seo, canonical }))}{field('OG 标题', seo.ogTitle, (ogTitle) => update({ ...seo, ogTitle }))}{field('OG 描述', seo.ogDescription, (ogDescription) => update({ ...seo, ogDescription }))}{field('OG 图片', seo.ogImage, (ogImage) => update({ ...seo, ogImage }))}</section>
}

function EditableList<T>({ items, update, create, render, emptyText }: { items: T[]; update: (items: T[]) => void; create: () => T; render: (item: T, index: number, setItem: (item: T) => void) => JSX.Element; emptyText: string }) {
  return <div className="editable-list"><div className="list-toolbar"><button className="secondary-action" type="button" onClick={() => update([...items, create()])}>新增</button><span>共 {items.length} 条</span></div>{items.length ? items.map((item, index) => <section className="editor-card" key={index}><div className="editor-card-head"><strong>#{index + 1}</strong><button className="ghost-action" type="button" onClick={() => update(items.filter((_, itemIndex) => itemIndex !== index))}>删除</button></div><div className="admin-form-grid">{render(item, index, (next) => update(items.map((current, itemIndex) => itemIndex === index ? next : current)))}</div></section>) : <EmptyState text={emptyText} />}</div>
}

function PanelIntro({ title, text, children }: { title: string; text: string; children: JSX.Element }) {
  return <section className="admin-stack"><div className="admin-card wide"><h2>{title}</h2><p>{text}</p></div>{children}</section>
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>
}

function field(label: string, value: string, update: (value: string) => void) {
  return <label>{label}<input value={value || ''} onChange={(event) => update(event.target.value)} /></label>
}

function textareaField(label: string, value: string, update: (value: string) => void) {
  return <label className="full">{label}<textarea value={value || ''} onChange={(event) => update(event.target.value)} /></label>
}

function numberField(label: string, value: number, update: (value: number) => void) {
  return <label>{label}<input type="number" value={Number.isFinite(value) ? value : 0} onChange={(event) => update(Number(event.target.value))} /></label>
}

function switchField(label: string, value: boolean, update: (value: boolean) => void) {
  return <label className="switch-label">{label}<input type="checkbox" checked={value} onChange={(event) => update(event.target.checked)} /></label>
}

function selectField(label: string, value: string, options: string[], update: (value: string) => void) {
  const values = options.length ? options : [value || '']
  return <label>{label}<select value={value || values[0]} onChange={(event) => update(event.target.value)}>{values.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
}

function updateItem<T>(items: T[], update: (items: T[]) => void, index: number, next: T) {
  update(items.map((item, itemIndex) => itemIndex === index ? next : item))
}

function split(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function emptySEO(): SEO {
  return { title: '', keywords: '', description: '', canonical: '', ogTitle: '', ogDescription: '', ogImage: '', schema: '{}' }
}

function newPageBlock(): PageBlock {
  return { id: Date.now(), type: 'section', title: '新区块', subtitle: '', content: '', image: '', metrics: [], features: [], cta: { title: '', text: '', primaryText: '', primaryLink: '', secondaryText: '', secondaryLink: '' }, order: 1, visible: true, extra: {} }
}

function isSaveable(tab: AdminTab) {
  return !['dashboard', 'seo', 'logs', 'backups'].includes(tab)
}
