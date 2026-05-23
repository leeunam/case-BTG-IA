import type { Period } from '../types'

export const qk = {
  dailyInsight:       ()              => ['daily-insight'] as const,
  volume:             (p: Period)     => ['volume', p] as const,
  ranking:            (p: Period)     => ['ranking', p] as const,
  ipoVsFO:            (p: Period)     => ['ipo-vs-fo', p] as const,
  topNewOffers:       ()              => ['top-new-offers'] as const,
  pipelineHealth:     ()              => ['pipeline-health'] as const,
  offers:             (p: Period, s: string, page: number) => ['offers', p, s, page] as const,
  indicators:         (id: number)    => ['indicators', id] as const,
  documents:          (id: number)    => ['documents', id] as const,
  compareOffers:      (ids: number[]) => ['compare-offers', ids.join(',')] as const,
  alertSummary:       (p: Period)     => ['alert-summary', p] as const,
  alerts:             (p: Period, page: number) => ['alerts', p, page] as const,
  macroKpis:          ()              => ['macro-kpis'] as const,
  ipcaMonthly:        ()              => ['ipca-monthly'] as const,
  offersByCoord:      (p: Period)     => ['offers-by-coord', p] as const,
  topFundsVolume:     (p: Period)     => ['top-funds-volume', p] as const,
  players:            (p: Period)     => ['players', p] as const,
  topPlayerInsight:   (p: Period)     => ['top-player-insight', p] as const,
  conversations:      ()              => ['conversations'] as const,
  reportJob:          (id: string)    => ['report-job', id] as const,
}
