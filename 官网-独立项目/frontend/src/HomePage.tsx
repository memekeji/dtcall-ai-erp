import { FormEvent, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'
import type { ContentItem, FAQ, Lead, PageBlock, Product, PublicData, Release, Resource } from './api'
import { api } from './api'
import { useDocumentSEO } from './hooks'

gsap.registerPlugin(useGSAP, ScrollTrigger)

type HomePageProps = {
  data: PublicData
}

type GenericPageProps = {
  title: string
  blocks: PageBlock[]
  items?: GenericPageItem[]
  faqs?: FAQ[]
}

type GenericPageItem = Product | ContentItem | Resource | Release

const trustSignals = [
  { label: '私有化部署', value: 'Linux / Docker Compose' },
  { label: '在线更新', value: '官网更新中心 + 离线 ZIP' },
  { label: '权限审计', value: '角色权限 / 操作留痕 / 数据隔离' },
  { label: 'AI 协同', value: '工作流、知识库、智能建议' },
  { label: '统一数据底座', value: 'CRM、合同、财务、项目、OA 一体化' }
]

const heroInsightPills = [
  'CRM / 合同 / 财务 / 项目 / OA 一体化',
  '私有化部署与持续升级并行',
  '蓝金未来科技风企业指挥舱'
]

const heroSnapshots = [
  { title: '经营总览', tag: 'Dashboard', image: '/product-shots/dashboard-overview.png' },
  { title: '项目视图', tag: 'Project', image: '/product-shots/project-delivery.png' },
  { title: '企业网盘', tag: 'Disk', image: '/product-shots/disk-center.png' }
]

const productSurfaces = [
  {
    eyebrow: '真实工作台',
    title: '统一后台框架',
    text: '从系统、客户、项目、财务到 AI 协同，在同一后台工作台里连续切换。',
    image: '/product-shots/main-shell.png'
  },
  {
    eyebrow: '经营总览',
    title: '管理层看板',
    text: '订单、合同、审批、项目状态集中呈现，让关键经营动作更容易被看见。',
    image: '/product-shots/dashboard-overview.png'
  },
  {
    eyebrow: '企业网盘',
    title: '资料协同中心',
    text: '文件上传、下载、分享、收藏和回收在同一工作界面闭环处理。',
    image: '/product-shots/disk-center.png'
  },
  {
    eyebrow: '项目交付',
    title: '交付进度总览',
    text: '项目状态、分类、计划与导出操作集中管理，适合持续推进交付过程。',
    image: '/product-shots/project-delivery.png'
  }
]

const capabilityFallback = [
  { title: 'CRM 客户增长', text: '统一线索、客户、商机、跟进与回款视图，帮助销售团队减少重复录入与状态失真。', icon: 'CRM' },
  { title: '合同财务协同', text: '把合同审批、收付款、发票、费用与利润看板串成同一条经营链路。', icon: 'FIN' },
  { title: '项目交付管理', text: '让项目计划、任务进度、风险预警和交付节点在同一套系统里持续同步。', icon: 'PM' },
  { title: 'OA 流程在线化', text: '围绕组织、权限和流程表单构建统一协同网络，让流程真正留痕、可追踪。', icon: 'OA' },
  { title: 'AI 智能协同', text: '通过知识库问答、业务意图识别和智能建议，提升团队处理复杂流程的效率。', icon: 'AI' },
  { title: '更新中心能力', text: '支持官网检测升级、版本目录切换、失败回滚和离线导入 ZIP 包。', icon: 'UPD' }
]

const scenarioCards = [
  {
    title: '销售与经营协同',
    desc: '打通线索、客户、合同、回款、经营看板，让增长过程不再分散在多个系统里。',
    bullets: ['销售漏斗更透明', '回款预测更准确', '客户资产更完整']
  },
  {
    title: '项目与交付管理',
    desc: '把合同履约、项目里程碑、费用与交付风险放在统一视图里，让管理层看见全过程。',
    bullets: ['进度节点实时同步', '交付异常提前预警', '交付复盘可追踪']
  },
  {
    title: '财务与流程治理',
    desc: '通过审批、费用、发票、付款与利润分析联动，提高财务协同效率与经营控制力。',
    bullets: ['审批更快', '数据口径更统一', '利润分析更及时']
  }
]

const deploymentAdvantages = [
  '官网固定域名检测更新',
  'Linux + Docker Compose 标准交付',
  '版本目录切换与健康检查',
  '离线 ZIP 导入与回滚恢复',
]

export function HomePage({ data }: HomePageProps) {
  const pageRef = useRef<HTMLElement>(null)
  const [lead, setLead] = useState<Lead>({ name: '', phone: '', company: '', message: '', sourcePath: '官网首页' })
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const homeBlocks = data.home.blocks || []
  const hero = homeBlocks.find((block) => block.type === 'hero')
  const valueBlock = homeBlocks.find((block) => block.type === 'value' || block.type === 'feature-grid')
  const heroMetrics = hero?.metrics?.length ? hero.metrics : [
    { value: '8+', label: '核心经营模块' },
    { value: '7×24', label: '在线版本迭代' },
    { value: '100%', label: '统一经营链路' }
  ]
  const featuredSolutions = useMemo(() => data.solutions.slice(0, 3), [data.solutions])
  const featuredCases = useMemo(() => data.cases.slice(0, 2), [data.cases])
  const featuredNews = useMemo(() => data.news.slice(0, 3), [data.news])
  const featuredRelease = data.releases[0]
  const faqItems = (data.resources?.faqs || []).slice(0, 4)
  const capabilityCards = (valueBlock?.features?.length ? valueBlock.features.map((feature) => ({
    title: feature.title,
    text: feature.text,
    icon: feature.icon
  })) : capabilityFallback).slice(0, 6)

  useDocumentSEO(data.site, data.home)

  useGSAP(
    () => {
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (reduceMotion) return
      gsap.from('.hero-copy > *', { autoAlpha: 0, y: 24, duration: 0.8, stagger: 0.09, ease: 'power3.out' })
      gsap.from('.hero-product-stage > *', { autoAlpha: 0, y: 26, duration: 0.92, stagger: 0.08, ease: 'power3.out', delay: 0.15 })
      gsap.to('.hero-product-frame', { y: -10, duration: 3.4, repeat: -1, yoyo: true, ease: 'sine.inOut' })
      gsap.to('.hero-preview-chip', { y: -6, duration: 2.2, repeat: -1, yoyo: true, ease: 'sine.inOut', stagger: 0.18 })
      ScrollTrigger.batch('.reveal-card', {
        start: 'top 84%',
        once: true,
        onEnter: (elements) => gsap.fromTo(elements, { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0, duration: 0.72, stagger: 0.08, ease: 'power3.out' })
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
    <main ref={pageRef} className="site-page future-site">
      <section id="home" className="hero-section section-shell">
        <div className="hero-copy">
          <span className="eyebrow">Integrated Enterprise Command Platform</span>
          <h1>{hero?.title || '企业一体化智能管理平台'}</h1>
          <p>{hero?.subtitle || '打通 CRM、合同、财务、项目、OA 与 AI 协同，让企业从分散管理走向统一经营。'}</p>
          <p className="hero-support">{hero?.content || 'DT 面向通用企业管理客户，提供可私有化部署、可持续升级、可连接业务流程与数据决策的一体化经营系统。'}</p>
          <div className="hero-pill-row">
            {heroInsightPills.map((item) => <span key={item}>{item}</span>)}
          </div>
          <div className="hero-actions">
            <a className="primary-action" href="#contact">预约专属演示</a>
            <a className="secondary-action" href="#solutions">查看解决方案</a>
          </div>
          <div className="metric-row hero-metrics" aria-label="平台价值指标">
            {heroMetrics.map((metric) => (
              <strong key={metric.label}>
                <span>{metric.value}</span>
                {metric.label}
              </strong>
            ))}
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-product-stage">
            <div className="hero-preview-chip chip-left">真实工作台</div>
            <div className="hero-preview-chip chip-right">经营总览</div>
            <div className="hero-preview-chip chip-bottom">更新中心</div>
            <div className="hero-product-frame">
              <div className="hero-product-head">
                <div>
                  <small>REAL PRODUCT PREVIEW</small>
                  <strong>DT 企业智能管理系统真实界面</strong>
                </div>
                <b>LIVE UI</b>
              </div>
              <img className="hero-product-image" src="/product-shots/dashboard-overview.png" alt="DT 企业智能管理系统经营总览后台界面" />
            </div>
            <div className="hero-preview-stack">
              {heroSnapshots.map((item) => (
                <article key={item.title} className="hero-preview-card">
                  <div className="hero-preview-meta">
                    <span>{item.tag}</span>
                    <strong>{item.title}</strong>
                  </div>
                  <img src={item.image} alt={`${item.title}系统界面`} />
                </article>
              ))}
            </div>
            <div className="hero-side-spec hero-side-spec-top">
              <strong>PRIVATE DEPLOY</strong>
              <span>Linux + Docker Compose 标准交付</span>
            </div>
            <div className="hero-side-spec hero-side-spec-bottom">
              <strong>UPDATE CENTER</strong>
              <span>固定域名检测升级 / 离线 ZIP 兜底</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section-shell trust-strip reveal-card">
        {trustSignals.map((item) => (
          <article key={item.label} className="trust-card">
            <strong>{item.label}</strong>
            <span>{item.value}</span>
          </article>
        ))}
      </section>

      <section className="section-shell product-surface-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Real Product Experience</span>
          <h2>不是概念示意图，而是系统真实页面直接进入官网首页</h2>
          <p>首页直接展示真实后台工作台、经营总览、网盘协同与项目管理界面，让客户在第一时间看见产品体验，而不是只看文案。</p>
        </div>
        <div className="product-surface-layout">
          <article className="surface-hero-card reveal-card">
            <div className="surface-copy">
              <span className="eyebrow">Executive View</span>
              <h3>管理层可以先看到全局，再进入每个模块</h3>
              <p>订单、合同、项目、审批、消息等关键指标在真实经营总览中集中呈现，适合作为企业管理者的统一入口。</p>
            </div>
            <div className="surface-hero-media">
              <img src="/product-shots/dashboard-overview.png" alt="DT 企业管理系统真实经营总览界面" />
            </div>
          </article>
          <div className="surface-grid">
            {productSurfaces.map((item) => (
              <article className="surface-card reveal-card" key={item.title}>
                <div className="surface-card-media">
                  <img src={item.image} alt={`${item.title}真实系统界面`} />
                </div>
                <div className="surface-card-copy">
                  <span>{item.eyebrow}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="products" className="section-shell capability-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Capability Matrix</span>
          <h2>覆盖 CRM、合同、财务、项目、OA 的一体化经营能力</h2>
          <p>不是把多个孤立工具拼在一起，而是基于统一权限、统一流程、统一数据底座，构建真正可持续演进的企业管理平台。</p>
        </div>
        <div className="capability-grid">
          {capabilityCards.map((item) => (
            <article className="capability-card reveal-card" key={item.title}>
              <div className="capability-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-shell architecture-section">
        <div className="value-panel reveal-card">
          <div className="value-copy">
            <span className="eyebrow">Why Integrated</span>
            <h2>{valueBlock?.title || '把复杂经营链路收束到同一张管理网络里'}</h2>
            <p>{valueBlock?.subtitle || '当 CRM、合同、财务、项目、OA 分散在不同系统里，真正被浪费的是协同效率、数据可信度与管理层的判断速度。'}</p>
            <p>{valueBlock?.content || 'DT 用统一角色权限、流程引擎、数据归档、经营看板和 AI 协同能力，把企业关键业务重新组织成一条连续、透明、可追踪的经营路径。'}</p>
          </div>
          <div className="architecture-board">
            <div className="board-track">
              <span>线索</span>
              <span>合同</span>
              <span>回款</span>
              <span>项目</span>
              <span>交付</span>
              <span>复盘</span>
            </div>
            <div className="board-insight">
              <strong>统一流程 + 统一数据 + AI 协同</strong>
              <p>让管理层看到的不只是局部模块，而是完整经营路径。</p>
            </div>
          </div>
        </div>
      </section>

      <section id="solutions" className="section-shell scenario-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Business Scenarios</span>
          <h2>适合通用企业管理客户的关键落地场景</h2>
          <p>无论你更关注销售经营、项目交付，还是财务协同与组织治理，平台都能围绕同一套数据和流程持续升级。</p>
        </div>
        <div className="scenario-grid">
          {scenarioCards.map((item) => (
            <article className="scenario-card reveal-card" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
              <ul>
                {item.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
              </ul>
            </article>
          ))}
        </div>
        <div className="solution-spotlight reveal-card">
          {featuredSolutions.map((solution) => (
            <article key={solution.id} className="spotlight-card">
              <div className="article-cover">{solution.category}</div>
              <h3>{solution.title}</h3>
              <p>{solution.summary}</p>
              <div className="tag-row">
                {solution.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="cases" className="section-shell proof-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Customer Proof</span>
          <h2>客户不是买功能列表，而是买更清晰的经营结果</h2>
          <p>我们更强调管理结果、流程透明度、回款节奏、交付可控性和组织协同质量，而不只是单个模块上线。</p>
        </div>
        <div className="proof-grid">
          {featuredCases.map((item) => (
            <article className="proof-card reveal-card" key={item.id}>
              <div className="proof-top">
                <span>{item.category}</span>
                <strong>{item.title}</strong>
              </div>
              <p>{item.summary}</p>
              <div className="tag-row">
                {item.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
              </div>
            </article>
          ))}
          <article className="proof-stat-card reveal-card">
            <small>MANAGEMENT VALUE</small>
            <h3>统一客户、合同、财务、项目与 OA 后，管理动作才真正可追踪、可优化。</h3>
            <div className="proof-stat-list">
              <span>更快识别交付风险</span>
              <span>更清晰掌握回款节奏</span>
              <span>更稳定沉淀客户资产</span>
            </div>
          </article>
        </div>
      </section>

      <section id="updates" className="section-shell deployment-section reveal-card">
        <div className="deployment-copy">
          <span className="eyebrow">Private Deployment & Update Center</span>
          <h2>不仅能部署，更能持续、安全地在线升级</h2>
          <p>DT 官网已升级为固定域名更新中心，支持客户部署后通过官网检测版本、执行在线升级，并保留离线 ZIP 导入与回滚恢复能力。</p>
          <div className="deployment-list">
            {deploymentAdvantages.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>
        <div className="deployment-card">
          <div className="deployment-card-head">
            <strong>{featuredRelease?.title || 'DT 企业管理系统版本发布中心'}</strong>
            <b>{featuredRelease?.version || 'v1.0.0'}</b>
          </div>
          <p>{featuredRelease?.summary || '支持官网统一版本检测、Docker ZIP 升级包、版本目录切换与失败回滚。'}</p>
          <div className="meta-stack">
            <span>发布渠道：{featuredRelease?.channel || 'stable'}</span>
            <span>目标环境：{featuredRelease?.target || 'Ubuntu 22.04 x86_64 / Docker Compose'}</span>
            <span>平台标识：{featuredRelease?.platform || 'linux-docker-x64'}</span>
          </div>
          <div className="tag-row">
            {(featuredRelease?.highlights || ['官网统一检测', 'Docker ZIP', '版本目录切换']).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
          </div>
          <a className="text-link" href="/updates">查看版本发布详情</a>
        </div>
      </section>

      <section id="news" className="section-shell insights-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">Knowledge & GEO</span>
          <h2>让搜索引擎与大模型都能更清楚理解你的平台能力</h2>
          <p>我们把企业管理系统、私有化部署、在线更新、AI 协同与一体化经营平台这些核心主题，组织成更清晰的知识与内容结构。</p>
        </div>
        <div className="news-grid">
          {featuredNews.map((item) => (
            <ArticleCard item={item} key={item.id} />
          ))}
        </div>
      </section>

      <section className="section-shell faq-section">
        <div className="section-heading reveal-card">
          <span className="eyebrow">FAQ</span>
          <h2>客户最常问的部署、升级与适用问题</h2>
          <p>这部分会显著提升 GEO 与转化效率，因为它直接回答“这套系统到底怎么部署、怎么更新、适合谁”。</p>
        </div>
        <div className="faq-grid">
          {faqItems.map((item) => (
            <article className="faq-card reveal-card" key={item.id || item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="contact" className="section-shell contact-section contact-section-upgraded">
        <div className="contact-copy reveal-card">
          <span className="eyebrow">Book Executive Demo</span>
          <h2>获取企业专属的一体化管理与部署升级方案</h2>
          <p>如果你正在评估 CRM、合同、财务、项目、OA 一体化平台，或者希望建立私有化部署与持续更新能力，我们可以结合你的组织规模与业务链路给出建议。</p>
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
            <textarea value={lead.message} onChange={(event) => setLead({ ...lead, message: event.target.value })} placeholder="请描述您当前的管理场景、部署要求或升级需求" />
          </label>
          <button className="primary-action" disabled={submitting}>{submitting ? '正在提交' : '预约专属演示'}</button>
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

export function GenericPage({ title, blocks, items = [], faqs = [] }: GenericPageProps) {
  const visibleBlocks = blocks.filter((block) => block.visible)
  const intro = visibleBlocks[0]
  const topFAQs = faqs.slice(0, 4)

  return (
    <main className="site-page inner-page future-site">
      <section className="section-shell page-hero">
        <div className="page-hero-copy reveal-card">
          <span className="eyebrow">DT Official Site</span>
          <h1>{title}</h1>
          <p>{intro?.subtitle || intro?.content || '查看 DT 企业智能管理系统在产品能力、解决方案、案例、资源中心与版本更新方面的完整信息。'}</p>
        </div>
      </section>

      {visibleBlocks.map((block) => (
        <section className="section-shell" key={block.id}>
          <div className="content-band reveal-card">
            <span className="eyebrow">{block.type}</span>
            <h2>{block.title}</h2>
            <p>{block.subtitle || block.content}</p>
          </div>
        </section>
      ))}

      {items.length ? (
        <section className="section-shell generic-grid-section">
          <div className="generic-grid">
            {items.map((item) => (
              <article className="generic-card reveal-card" key={`${item.id}-${item.title}`}>
                <div className="generic-card-top">
                  <div className="card-icon">{displayItemIcon(item)}</div>
                  {'version' in item ? <b className="version-pill">{item.version}</b> : null}
                </div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                <div className="meta-stack">
                  {'category' in item && item.category ? <span>分类：{item.category}</span> : null}
                  {'target' in item && item.target ? <span>目标环境：{item.target}</span> : null}
                  {'channel' in item && item.channel ? <span>发布渠道：{item.channel}</span> : null}
                  {'platform' in item && item.platform ? <span>平台标识：{item.platform}</span> : null}
                  {'build' in item && item.build ? <span>构建号：{item.build}</span> : null}
                  {'minSupportedVersion' in item && item.minSupportedVersion ? <span>最低可升级版本：{item.minSupportedVersion}</span> : null}
                  {'needLead' in item && item.needLead ? <span>获取方式：提交线索后获取</span> : null}
                </div>
                {'highlights' in item ? (
                  <div className="tag-row">{item.highlights.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div>
                ) : 'tags' in item ? (
                  <div className="tag-row">{(item.tags || []).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div>
                ) : null}
                {'releaseNotesMarkdown' in item && item.releaseNotesMarkdown ? <p className="item-note">{item.releaseNotesMarkdown.split('\n')[0].replace(/^- /, '')}</p> : null}
                {'packageUrl' in item && item.packageUrl ? <a className="text-link" href={item.packageUrl}>获取更新包</a> : null}
                {'link' in item && item.link ? <a className="text-link" href={item.link}>查看资源</a> : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {topFAQs.length ? (
        <section className="section-shell faq-section">
          <div className="section-heading reveal-card">
            <span className="eyebrow">FAQ</span>
            <h2>常见问题</h2>
          </div>
          <div className="faq-grid">
            {topFAQs.map((item) => (
              <article className="faq-card reveal-card" key={item.id || item.question}>
                <h3>{item.question}</h3>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  )
}

function displayItemIcon(item: GenericPageItem) {
  if ('version' in item) return 'UPD'
  if ('icon' in item) return item.icon
  if ('category' in item && item.category) return item.category.slice(0, 2).toUpperCase()
  return 'DT'
}
