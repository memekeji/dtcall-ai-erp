import { FormEvent, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'
import type { ContentItem, Lead, PageBlock, Product, PublicData, Release, Resource } from './api'
import { api } from './api'
import { useDocumentSEO } from './hooks'

gsap.registerPlugin(useGSAP, ScrollTrigger)

type HomePageProps = {
  data: PublicData
}

export function HomePage({ data }: HomePageProps) {
  const pageRef = useRef<HTMLElement>(null)
  const [lead, setLead] = useState<Lead>({ name: '', phone: '', company: '', message: '', sourcePath: '官网首页' })
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const hero = data.home.blocks.find((block) => block.type === 'hero')
  const ability = data.home.blocks.find((block) => block.type === 'feature-grid')
  const metrics = hero?.metrics || []
  const heroFeatures = ability?.features || []
  const featuredProducts = useMemo(() => data.products.slice(0, 12), [data.products])
  const featuredSolutions = useMemo(() => data.solutions.slice(0, 3), [data.solutions])

  useDocumentSEO(data.site, data.home)

  useGSAP(
    () => {
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (reduceMotion) return
      gsap.from('.hero-copy > *', { autoAlpha: 0, y: 28, duration: 0.82, stagger: 0.1, ease: 'power3.out' })
      gsap.from('.hero-orbit', { autoAlpha: 0, scale: 0.92, rotation: -6, duration: 1.1, ease: 'power3.out' })
      gsap.to('.orbital-ring', { rotation: 360, duration: 24, repeat: -1, ease: 'none' })
      gsap.to('.floating-card', { y: -16, duration: 2.8, repeat: -1, yoyo: true, ease: 'sine.inOut', stagger: 0.2 })
      ScrollTrigger.batch('.reveal-card', {
        start: 'top 82%',
        once: true,
        onEnter: (elements) => gsap.fromTo(elements, { autoAlpha: 0, y: 34 }, { autoAlpha: 1, y: 0, duration: 0.72, stagger: 0.08, ease: 'power3.out' })
      })
    },
    { scope: pageRef }
  )

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    try {
      await api.public.lead(lead)
      setMessage('提交成功，我们会尽快安排顾问联系您。')
      setLead({ name: '', phone: '', company: '', message: '', sourcePath: '官网首页' })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '提交失败，请稍后再试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main ref={pageRef} className="site-page">
      <section id="home" className="hero-section section-shell">
        <div className="hero-copy">
          <span className="eyebrow">DT Enterprise Intelligence Platform</span>
          <h1>{hero?.title || data.site.slogan}</h1>
          <p>{hero?.subtitle || data.site.description}</p>
          <div className="hero-actions">
            <a className="primary-action" href="#contact">预约演示</a>
            <a className="secondary-action" href="#products">查看产品矩阵</a>
          </div>
          <div className="metric-row" aria-label="核心指标">
            {metrics.map((metric) => (
              <strong key={metric.label}>
                <span>{metric.value}</span>
                {metric.label}
              </strong>
            ))}
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="hero-orbit">
            <div className="orbital-ring" />
            <div className="dashboard-plate">
              <div className="plate-topline">
                <span />
                <span />
                <span />
              </div>
              <div className="plate-title">DT 智能运营驾驶舱</div>
              <div className="plate-chart">
                <i />
                <i />
                <i />
                <i />
              </div>
              <div className="plate-grid">
                <b>CRM</b>
                <b>合同</b>
                <b>财务</b>
                <b>生产</b>
              </div>
            </div>
            <div className="floating-card card-one">AI 流程编排</div>
            <div className="floating-card card-two">实时数据洞察</div>
            <div className="floating-card card-three">在线版本更新</div>
          </div>
        </div>
      </section>

      <section id="products" className="section-shell product-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Product Matrix</span>
          <h2>覆盖企业经营全链路的产品能力</h2>
          <p>从客户增长、项目交付到财务生产协同，以统一数据底座消除信息孤岛。</p>
        </div>
        <div className="product-grid">
          {featuredProducts.map((product) => (
            <article className="product-card reveal-card" key={product.id}>
              <div className="card-icon">{product.icon}</div>
              <h3>{product.title}</h3>
              <p>{product.summary}</p>
              <div className="tag-row">
                {product.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section-shell value-section">
        <div className="value-panel reveal-card">
          <span className="eyebrow">Core Value</span>
          <h2>{ability?.title || '让组织从“系统可用”升级为“智能增长”'}</h2>
          <p>{ability?.subtitle || '统一权限、统一流程、统一数据、统一智能体，支撑企业持续在线迭代。'}</p>
          <div className="value-list">
            {heroFeatures.map((feature) => (
              <div key={feature.title}>
                <span>{feature.icon}</span>
                <strong>{feature.title}</strong>
                <p>{feature.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="solutions" className="section-shell split-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Solutions</span>
          <h2>面向关键行业场景快速落地</h2>
        </div>
        <div className="solution-grid">
          {featuredSolutions.map((solution) => (
            <ArticleCard item={solution} key={solution.id} />
          ))}
        </div>
      </section>

      <section id="cases" className="section-shell case-ribbon reveal-card">
        <div>
          <span className="eyebrow">Customer Proof</span>
          <h2>以真实业务结果证明平台价值</h2>
          <p>沉淀客户全生命周期数据，帮助管理层看清经营质量、过程风险与增长空间。</p>
        </div>
        <div className="case-list">
          {data.cases.slice(0, 3).map((item) => (
            <div key={item.id}>
              <strong>{item.title}</strong>
              <span>{item.summary}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="news" className="section-shell news-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Knowledge Center</span>
          <h2>产品动态与数字化管理洞察</h2>
        </div>
        <div className="news-grid">
          {data.news.slice(0, 4).map((item) => (
            <ArticleCard item={item} key={item.id} />
          ))}
        </div>
      </section>

      <section id="updates" className="section-shell update-section reveal-card">
        <div>
          <span className="eyebrow">Version Release</span>
          <h2>通过官网发布 DT 企业管理系统版本更新</h2>
          <p>这里用于发布客户部署的 DT 企业管理系统更新包、版本说明、校验信息与升级策略，便于客户安全获取最新版本。</p>
        </div>
        <div className="update-flow">
          {(data.releases.length ? data.releases.slice(0, 2) : []).map((release) => (
            <span key={release.id}>{release.version} · {release.title}</span>
          ))}
          {data.releases.length === 0 ? ['版本包上传', '兼容性说明', '校验码发布', '客户部署升级'].map((item, index) => (
            <span key={item}>{String(index + 1).padStart(2, '0')} · {item}</span>
          )) : null}
        </div>
      </section>

      <section id="contact" className="section-shell contact-section">
        <div className="contact-copy reveal-card">
          <span className="eyebrow">Book Demo</span>
          <h2>预约 DT 企业智能管理系统专属演示</h2>
          <p>留下您的需求，我们将结合行业、组织规模与当前系统现状，给出系统选型、部署升级与版本更新建议。</p>
          <ul>
            <li>联系电话：{data.site.phone}</li>
            <li>联系邮箱：{data.site.email}</li>
            <li>服务地址：{data.site.address}</li>
          </ul>
        </div>
        <form className="lead-form reveal-card" onSubmit={submit}>
          <label>
            姓名
            <input value={lead.name} onChange={(event) => setLead({ ...lead, name: event.target.value })} required placeholder="请输入姓名" />
          </label>
          <label>
            联系电话
            <input value={lead.phone} onChange={(event) => setLead({ ...lead, phone: event.target.value })} required placeholder="请输入联系电话" />
          </label>
          <label>
            公司名称
            <input value={lead.company} onChange={(event) => setLead({ ...lead, company: event.target.value })} placeholder="请输入公司名称" />
          </label>
          <label>
            需求说明
            <textarea value={lead.message} onChange={(event) => setLead({ ...lead, message: event.target.value })} placeholder="请描述您关注的业务场景" />
          </label>
          <button className="primary-action" disabled={submitting}>{submitting ? '正在提交' : '提交咨询'}</button>
          {message ? <p className="form-message">{message}</p> : null}
        </form>
      </section>
    </main>
  )
}

function ArticleCard({ item }: { item: ContentItem }) {
  return (
    <article className="article-card reveal-card">
      <div className="article-cover">{item.category}</div>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
      <div className="tag-row">
        {item.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
      </div>
    </article>
  )
}

type GenericPageItem = Product | ContentItem | Resource | Release

export function GenericPage({ title, blocks, items = [] }: { title: string; blocks: PageBlock[]; items?: GenericPageItem[] }) {
  return (
    <main className="site-page inner-page">
      <section className="section-shell simple-hero">
        <span className="eyebrow">DT Official Site</span>
        <h1>{title}</h1>
      </section>
      {blocks.filter((block) => block.visible).map((block) => (
        <section className="section-shell value-panel" key={block.id}>
          <span className="eyebrow">{block.type}</span>
          <h2>{block.title}</h2>
          <p>{block.subtitle || block.content}</p>
        </section>
      ))}
      {items.length ? (
        <section className="section-shell generic-grid-section">
          <div className="generic-grid">
            {items.map((item) => (
              <article className="product-card reveal-card" key={`${item.id}-${item.title}`}>
                <div className="card-icon">{'version' in item ? item.version : 'icon' in item ? item.icon : 'category' in item ? item.category : 'DT'}</div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                {'target' in item ? <p className="item-meta">目标环境：{item.target}</p> : null}
                {'checksum' in item && item.checksum ? <p className="item-meta">校验码：{item.checksum}</p> : null}
                {'highlights' in item ? (
                  <div className="tag-row">{item.highlights.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div>
                ) : 'tags' in item ? (
                  <div className="tag-row">{(item.tags || []).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div>
                ) : null}
                {'packageUrl' in item && item.packageUrl ? <a className="text-link" href={item.packageUrl}>获取更新包</a> : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  )
}
