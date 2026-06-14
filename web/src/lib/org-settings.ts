const INTERNAL_TOOLS_VISIBILITY_KEY = 'internal_tools_visibility'
const LEAD_DISCOVERY_SOURCES_KEY = 'lead_discovery_sources'

export type InternalToolsVisibilitySettings = {
  showAiDiagnostics: boolean
  showResetAiMemory: boolean
}

export type LeadDiscoverySourceOption = {
  value: string
  label: string
}

const DEFAULT_INTERNAL_TOOLS_VISIBILITY: InternalToolsVisibilitySettings = {
  showAiDiagnostics: true,
  showResetAiMemory: true,
}

const DEFAULT_LEAD_DISCOVERY_SOURCES: LeadDiscoverySourceOption[] = [
  { value: 'friends', label: 'Друзья / рекомендация' },
  { value: 'ads', label: 'Реклама' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'google', label: 'Google / поиск' },
  { value: 'website', label: 'Сайт' },
  { value: 'partner', label: 'Партнер' },
  { value: 'repeat_guest', label: 'Уже был гостем' },
  { value: 'other', label: 'Другое' },
]

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function getInternalToolsVisibilitySettings(orgSettings: Record<string, unknown> | null | undefined): InternalToolsVisibilitySettings {
  const root = asRecord(orgSettings)
  const visibility = asRecord(root[INTERNAL_TOOLS_VISIBILITY_KEY])

  return {
    showAiDiagnostics: visibility.show_ai_diagnostics !== false,
    showResetAiMemory: visibility.show_reset_ai_memory !== false,
  }
}

export function buildInternalToolsVisibilityOrgSettings(
  orgSettings: Record<string, unknown> | null | undefined,
  visibility: InternalToolsVisibilitySettings,
): Record<string, unknown> {
  const root = asRecord(orgSettings)
  const currentVisibility = asRecord(root[INTERNAL_TOOLS_VISIBILITY_KEY])

  return {
    ...root,
    [INTERNAL_TOOLS_VISIBILITY_KEY]: {
      ...currentVisibility,
      show_ai_diagnostics: visibility.showAiDiagnostics,
      show_reset_ai_memory: visibility.showResetAiMemory,
    },
  }
}

export function getDefaultInternalToolsVisibility(): InternalToolsVisibilitySettings {
  return DEFAULT_INTERNAL_TOOLS_VISIBILITY
}

function normalizeDiscoverySourceOption(option: unknown): LeadDiscoverySourceOption | null {
  const record = asRecord(option)
  const value = typeof record.value === 'string' ? record.value.trim() : ''
  const label = typeof record.label === 'string' ? record.label.trim() : ''

  if (!value || !label) {
    return null
  }

  return { value, label }
}

export function getDefaultLeadDiscoverySourceOptions(): LeadDiscoverySourceOption[] {
  return DEFAULT_LEAD_DISCOVERY_SOURCES
}

export function getLeadDiscoverySourceOptions(
  orgSettings: Record<string, unknown> | null | undefined,
): LeadDiscoverySourceOption[] {
  const root = asRecord(orgSettings)
  const rawOptions = Array.isArray(root[LEAD_DISCOVERY_SOURCES_KEY])
    ? root[LEAD_DISCOVERY_SOURCES_KEY]
    : []

  const options = rawOptions
    .map(normalizeDiscoverySourceOption)
    .filter((option): option is LeadDiscoverySourceOption => Boolean(option))

  return options.length > 0 ? options : DEFAULT_LEAD_DISCOVERY_SOURCES
}

export function buildLeadDiscoverySourcesOrgSettings(
  orgSettings: Record<string, unknown> | null | undefined,
  options: LeadDiscoverySourceOption[],
): Record<string, unknown> {
  const root = asRecord(orgSettings)
  const cleanOptions = options
    .map((option) => ({
      value: option.value.trim(),
      label: option.label.trim(),
    }))
    .filter((option) => option.value && option.label)

  return {
    ...root,
    [LEAD_DISCOVERY_SOURCES_KEY]: cleanOptions,
  }
}

export function createLeadDiscoverySourceValue(label: string, existingOptions: LeadDiscoverySourceOption[]): string {
  const translitMap: Record<string, string> = {
    а: 'a',
    б: 'b',
    в: 'v',
    г: 'g',
    д: 'd',
    е: 'e',
    ё: 'e',
    ж: 'zh',
    з: 'z',
    и: 'i',
    й: 'y',
    к: 'k',
    л: 'l',
    м: 'm',
    н: 'n',
    о: 'o',
    п: 'p',
    р: 'r',
    с: 's',
    т: 't',
    у: 'u',
    ф: 'f',
    х: 'h',
    ц: 'c',
    ч: 'ch',
    ш: 'sh',
    щ: 'sch',
    ы: 'y',
    э: 'e',
    ю: 'yu',
    я: 'ya',
  }
  const base = label
    .trim()
    .toLowerCase()
    .split('')
    .map((char) => translitMap[char] ?? char)
    .join('')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40) || 'source'

  const existing = new Set(existingOptions.map((option) => option.value))
  let candidate = base
  let index = 2
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`
    index += 1
  }

  return candidate
}
