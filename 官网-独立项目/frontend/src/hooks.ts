import { useEffect, useState } from 'react'
import type { ContentItem, Page, Product, PublicData, SiteConfig } from './api'
import { api } from './api'

export type LoadState<T> = {
  data: T | null
  loading: boolean
  error: string
  reload: () => void
}

export function usePublicData(): LoadState<PublicData> {
  const [data, setData] = useState<PublicData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    const loadPage = (slug: string) => api.public.page(slug).catch(() => api.public.seo(slug).then((seo) => ({ ...emptyPage(slug), seo })))
    Promise.all([
      api.public.site(),
      api.public.navigation(),
      loadPage('home'),
      loadPage('product'),
      loadPage('solutions'),
      loadPage('cases'),
      loadPage('news'),
      loadPage('resources'),
      loadPage('updates'),
      loadPage('contact'),
      api.public.products(),
      api.public.solutions(),
      api.public.cases(),
      api.public.news(),
      api.public.resources(),
      api.public.releases()
    ])
      .then(([site, navigation, home, productPage, solutionsPage, casesPage, newsPage, resourcesPage, updatesPage, contactPage, products, solutions, cases, news, resources, releases]) => {
        if (active) {
          setData({
            site,
            navigation,
            home,
            pages: {
              home,
              product: productPage,
              products: productPage,
              solutions: solutionsPage,
              cases: casesPage,
              news: newsPage,
              resources: resourcesPage,
              updates: updatesPage,
              contact: contactPage
            },
            products,
            solutions,
            cases,
            news,
            resources,
            releases
          })
          setError('')
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message)
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [tick])

  return { data, loading, error, reload: () => setTick((value) => value + 1) }
}

export function useDocumentSEO(site?: SiteConfig, page?: Page | ContentItem | Product) {
  useEffect(() => {
    const seo = page?.seo || site?.seo
    if (!seo) return
    document.title = seo.title || site?.name || 'DT 企业智能管理系统官网'
    setMeta('description', seo.description)
    setMeta('keywords', seo.keywords)
    setMeta('robots', 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1')
    setProperty('og:title', seo.ogTitle || seo.title)
    setProperty('og:description', seo.ogDescription || seo.description)
    setProperty('og:image', seo.ogImage)
    setCanonical(seo.canonical)
  }, [page, site])
}

function emptyPage(slug: string): Page {
  const normalizedSlug = slug === 'products' ? 'product' : slug
  return {
    id: 0,
    slug: normalizedSlug,
    title: '',
    summary: '',
    path: normalizedSlug === 'home' ? '/' : `/${normalizedSlug}`,
    seo: {
      title: '',
      keywords: '',
      description: '',
      canonical: '',
      ogTitle: '',
      ogDescription: '',
      ogImage: '',
      schema: ''
    },
    blocks: [],
    status: 'published',
    updatedAt: ''
  }
}

function setMeta(name: string, content: string) {
  if (!content) return
  let element = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
  if (!element) {
    element = document.createElement('meta')
    element.name = name
    document.head.appendChild(element)
  }
  element.content = content
}

function setProperty(property: string, content: string) {
  if (!content) return
  let element = document.querySelector<HTMLMetaElement>(`meta[property="${property}"]`)
  if (!element) {
    element = document.createElement('meta')
    element.setAttribute('property', property)
    document.head.appendChild(element)
  }
  element.content = content
}

function setCanonical(href: string) {
  if (!href) return
  let element = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!element) {
    element = document.createElement('link')
    element.rel = 'canonical'
    document.head.appendChild(element)
  }
  element.href = href
}
