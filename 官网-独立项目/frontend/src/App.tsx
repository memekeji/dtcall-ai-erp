import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { AdminApp } from './AdminApp'
import { GenericPage, HomePage } from './HomePage'
import { useDocumentSEO, usePublicData } from './hooks'
import './styles.css'

function PublicShell() {
  const { data, loading, error, reload } = usePublicData()
  const location = useLocation()
  const normalizedSlug = location.pathname === '/' ? 'home' : location.pathname.replace(/^\//, '')
  const slug = normalizedSlug === 'products' ? 'product' : normalizedSlug
  const page = data?.pages[slug] || data?.home

  useDocumentSEO(data?.site, page)

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error || '官网数据加载失败'} retry={reload} />

  return (
    <div className="app-root">
      <Header data={data} />
      <Routes>
        <Route path="/" element={<HomePage data={data} />} />
        <Route path="/product" element={<GenericPage title={data.pages.product?.title || '产品能力'} blocks={data.pages.product?.blocks || data.home.blocks} items={data.products} />} />
        <Route path="/products" element={<GenericPage title={data.pages.product?.title || '产品能力'} blocks={data.pages.product?.blocks || data.home.blocks} items={data.products} />} />
        <Route path="/solutions" element={<GenericPage title={data.pages.solutions?.title || '解决方案'} blocks={data.pages.solutions?.blocks || data.home.blocks} items={data.solutions} />} />
        <Route path="/cases" element={<GenericPage title={data.pages.cases?.title || '客户案例'} blocks={data.pages.cases?.blocks || data.home.blocks} items={data.cases} />} />
        <Route path="/news" element={<GenericPage title={data.pages.news?.title || '新闻动态'} blocks={data.pages.news?.blocks || data.home.blocks} items={data.news} />} />
        <Route path="/resources" element={<GenericPage title={data.pages.resources?.title || '资源中心'} blocks={data.pages.resources?.blocks || data.home.blocks} items={data.resources.resources} />} />
        <Route path="/updates" element={<GenericPage title={data.pages.updates?.title || '版本更新'} blocks={data.pages.updates?.blocks || data.home.blocks} items={data.releases} />} />
        <Route path="/contact" element={<GenericPage title={data.pages.contact?.title || '联系我们'} blocks={data.pages.contact?.blocks || data.home.blocks} />} />
        <Route path="*" element={<GenericPage title="DT 企业智能管理系统" blocks={data.home.blocks} />} />
      </Routes>
      <Footer data={data} />
    </div>
  )
}

function Header({ data }: { data: NonNullable<ReturnType<typeof usePublicData>['data']> }) {
  return (
    <header className="site-header">
      <Link className="brand" to="/" aria-label="返回首页">
        <span>{data.site.logo}</span>
        <strong>{data.site.name}</strong>
      </Link>
      <nav className="site-nav" aria-label="官网主导航">
        {data.navigation.filter((item) => item.visible).map((item) => (
          <a key={item.path} href={item.path === '/' ? '/' : item.path.startsWith('/') ? item.path : `#${item.path}`}>{item.label}</a>
        ))}
      </nav>
      <div className="header-actions">
        <a className="phone-link" href={`tel:${data.site.phone}`}>{data.site.phone}</a>
      </div>
    </header>
  )
}

function Footer({ data }: { data: NonNullable<ReturnType<typeof usePublicData>['data']> }) {
  return (
    <footer className="site-footer">
      <div>
        <strong>{data.site.name}</strong>
        <p>{data.site.description}</p>
      </div>
      <div>
        <span>{data.site.phone}</span>
        <span>{data.site.email}</span>
        <span>{data.site.address}</span>
      </div>
      <div>
        <a href="/sitemap.xml">Sitemap</a>
        <a href="/robots.txt">Robots</a>
      </div>
      <small>{data.site.icp} · © {new Date().getFullYear()} DT Enterprise Intelligence Platform</small>
    </footer>
  )
}

function Loading() {
  return <main className="loading-screen"><div className="loading-orb" /><strong>正在加载 DT 官网</strong></main>
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <main className="loading-screen"><strong>{message}</strong><button className="primary-action" onClick={retry}>重新加载</button></main>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="*" element={<PublicShell />} />
      </Routes>
    </BrowserRouter>
  )
}
