const INTERNAL_TOOLS_VISIBILITY_KEY = 'internal_tools_visibility'

export type InternalToolsVisibilitySettings = {
  showAiDiagnostics: boolean
  showDevDatabaseExport: boolean
  showResetAiMemory: boolean
}

const DEFAULT_INTERNAL_TOOLS_VISIBILITY: InternalToolsVisibilitySettings = {
  showAiDiagnostics: true,
  showDevDatabaseExport: true,
  showResetAiMemory: true,
}

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
    showDevDatabaseExport: visibility.show_dev_database_export !== false,
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
      show_dev_database_export: visibility.showDevDatabaseExport,
      show_reset_ai_memory: visibility.showResetAiMemory,
    },
  }
}

export function getDefaultInternalToolsVisibility(): InternalToolsVisibilitySettings {
  return DEFAULT_INTERNAL_TOOLS_VISIBILITY
}
