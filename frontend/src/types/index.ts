// ─── Offers ──────────────────────────────────────────────────────────────────

export interface Offer {
  id: number
  cvm_registration: string | null
  name: string
  ticker: string | null
  offer_type: 'ipo' | 'follow_on'
  status: string
  total_volume: number | null
  fund_type: string | null
  segment: string | null
  manager: string | null
  administrator: string | null
  lead_coordinator: string | null
  participants: string[]
  distribution_rite: string | null
  financial_terms_available: boolean
  start_date: string | null
  registered_at: string | null
  updated_at: string | null
}

export interface OfferList {
  items: Offer[]
  page: number
  page_size: number
  total_count: number
}

export interface IndicatorData {
  dy_12m: number | null
  dy_6m: number | null
  pvp: number | null
  price: number | null
  pl_total: number | null
  vacancy_rate: number | null
  volume_daily: number | null
  nav_per_unit: number | null
  monthly_return: number | null
  unit_price: number | null
  market_price: number | null
  spread_pct: number | null
  snapshot_date: string | null
  source: string
}

export interface CompareOffer {
  offer: Offer
  indicators: IndicatorData
}

// ─── Documents ───────────────────────────────────────────────────────────────

export interface DocumentItem {
  id: number
  offer_id: number | null
  type: string
  title: string
  source_url: string | null
  download_url: string | null
  available: boolean
  extraction_status: string
}

// ─── Alerts ──────────────────────────────────────────────────────────────────

export interface Alert {
  id: number
  type: string
  offer_id: number | null
  offer_name: string | null
  ticker: string | null
  offer_type: 'ipo' | 'follow_on' | null
  seen: boolean
  created_at: string
  detail: string
}

export interface AlertList {
  items: Alert[]
  page: number
  page_size: number
  total_count: number
}

export interface AlertSummary {
  total: number
  seen: number
  unseen: number
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DailyInsight {
  insight_date: string
  generated_at: string | null
  status: 'generated' | 'not_generated' | 'failed' | 'stale'
  text: string | null
}

export interface VolumeByPeriod {
  period: string
  total_volume: number
  offer_count: number
  ipo_volume: number
  follow_on_volume: number
}

export interface RankingItem {
  rank: number
  name: string
  ticker: string | null
  offer_type: string
  total_volume: number
  coordinator: string | null
}

export interface IpoVsFollowOn {
  period: string
  ipo_volume: number
  ipo_count: number
  follow_on_volume: number
  follow_on_count: number
}

export interface TopNewOffer {
  id: number
  name: string
  ticker: string | null
  offer_type: string
  total_volume: number | null
  coordinator: string | null
  registered_at: string | null
  distribution_rite: string | null
}

export interface PipelineSourceStatus {
  source_code: string
  source_name: string
  last_run_at: string | null
  last_status: string | null
  hours_since_update: number | null
  is_stale: boolean
}

export interface PipelineHealth {
  sources: PipelineSourceStatus[]
  failed_today: number
  stale_sources: number
}

// ─── Macro ───────────────────────────────────────────────────────────────────

export interface MacroKpi {
  code: string
  label: string
  value: number | null
  display_value: string
  unit: string
  metric_date: string | null
  source: string
}

export interface IpcaMonthlyPoint {
  month: string
  value: number
}

export interface PlayerItem {
  coordinator: string
  total_offers: number
  total_volume: number
  unique_funds: number
  share_qty_pct: number
  share_vol_pct: number
  last_offer_date: string | null
}

export interface TopPlayerInsight {
  coordinator: string
  share_vol_pct: number
  offer_count: number
  dominant_offer_type: string
  status: string
  text: string | null
}

export interface OffersByCoordinator {
  coordinator: string
  count: number
  volume: number
}

export interface FundVolume {
  name: string
  ticker: string | null
  total_volume: number
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export interface Conversation {
  id: string
  thread_id: string
  title: string
  created_at: string
  last_message_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: { name: string; content: string }[]
}

// ─── Reports ─────────────────────────────────────────────────────────────────

export interface ReportJob {
  job_id: string
  offer_id: number | null
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  download_url: string | null
  error: string | null
  created_at: string
}

// ─── Period ──────────────────────────────────────────────────────────────────

export type Period = '1d' | '7d' | '15d' | '1m'
