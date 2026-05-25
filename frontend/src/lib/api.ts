import type {
  Offer, OfferList, IndicatorData, CompareOffer,
  Alert, AlertList, AlertSummary,
  DailyInsight, VolumeByPeriod, RankingItem, IpoVsFollowOn,
  TopNewOffer, TopNewOffersResponse, PipelineHealth, MacroKpi, IpcaMonthlyPoint,
  PlayerItem, TopPlayerInsight, OffersByCoordinator, FundVolume,
  Conversation, ReportJob, Period,
} from '../types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetch(BASE + path, { method: 'DELETE' })
  if (!res.ok && res.status !== 204) throw new Error(res.statusText)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const api = {
  getDailyInsight:   ()              => get<DailyInsight>('/dashboard/daily-insight'),
  getVolume:         (p: Period)     => get<VolumeByPeriod>('/dashboard/volume', { period: p }),
  getRanking:        (p: Period)     => get<RankingItem[]>('/dashboard/ranking', { period: p }),
  getIpoVsFO:        (p: Period)     => get<IpoVsFollowOn>('/dashboard/ipo-vs-followon', { period: p }),
  getTopNewOffers:   ()              => get<TopNewOffersResponse>('/dashboard/top-new-offers'),
  getPipelineHealth: ()              => get<PipelineHealth>('/dashboard/pipeline-health'),

  // ─── Offers ────────────────────────────────────────────────────────────────
  getOffers: (p: Period, status: string, page: number, pageSize = 50) =>
    get<OfferList>('/offers', { period: p, status, page, page_size: pageSize }),
  getIndicators: (id: number) => get<IndicatorData>(`/offers/${id}/indicators`),
  compareOffers: (ids: number[]) =>
    get<CompareOffer[]>('/offers/compare', { offer_ids: ids.join(',') }),

  // ─── Alerts ────────────────────────────────────────────────────────────────
  getAlertSummary: (p: Period)                => get<AlertSummary>('/alerts/summary', { period: p }),
  getAlerts:       (p: Period, page: number)  => get<AlertList>('/alerts', { period: p, page }),
  markAlertSeen:   (id: number, seen: boolean) => patch(`/alerts/${id}/seen`, { seen }),
  markAllSeen:     (p: Period)                => patch(`/alerts/seen-all?period=${p}`),

  // ─── General Scenario ──────────────────────────────────────────────────────
  getMacroKpis:         ()          => get<MacroKpi[]>('/general-scenario/macro-kpis'),
  getIpcaMonthly:       ()          => get<IpcaMonthlyPoint[]>('/general-scenario/ipca-monthly'),
  getOffersByCoord:     (p: Period) => get<OffersByCoordinator[]>('/general-scenario/offers-by-coordinator', { period: p }),
  getTopFundsVolume:    (p: Period) => get<FundVolume[]>('/general-scenario/top-funds-volume', { period: p }),
  getPlayers:           (p: Period) => get<PlayerItem[]>('/general-scenario/players', { period: p }),
  getTopPlayerInsight:  (p: Period) => get<TopPlayerInsight>('/general-scenario/top-player-insight', { period: p }),

  // ─── Agent ─────────────────────────────────────────────────────────────────
  getConversations:   ()              => get<Conversation[]>('/agent/conversations'),
  createConversation: ()              => post<Conversation>('/agent/conversations'),
  deleteConversation: (id: string)   => del(`/agent/conversations/${id}`),

  // ─── Reports ───────────────────────────────────────────────────────────────
  createReport:  (offerId: number)  => post<ReportJob>(`/reports/offers/${offerId}`),
  getReportJob:  (jobId: string)    => get<ReportJob>(`/reports/jobs/${jobId}`),

  // ─── Settings ──────────────────────────────────────────────────────────────
  triggerRefresh: (source = 'all') => post('/settings/refresh', { source }),
}
