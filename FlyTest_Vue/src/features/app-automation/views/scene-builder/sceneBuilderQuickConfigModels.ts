export interface SceneBuilderConfigStringReadable {
  readSelectedConfigString: (key: string, fallback?: string) => string
}

export interface SceneBuilderConfigNumberReadable {
  readSelectedConfigNumber: (key: string, fallback?: number) => number
}

export interface SceneBuilderConfigBooleanReadable {
  readSelectedConfigBoolean: (key: string, fallback?: boolean) => boolean
}

export interface SceneBuilderConfigValueReadable {
  readSelectedConfigValue: (key: string, fallback?: unknown) => unknown
}

export interface SceneBuilderQuickConfigWritable {
  updateSelectedStepConfig: (key: string, value: unknown) => void
}

export interface SceneBuilderQuickConfigStringProps
  extends SceneBuilderConfigStringReadable,
    SceneBuilderQuickConfigWritable {}

export interface SceneBuilderQuickConfigNumericProps
  extends SceneBuilderQuickConfigStringProps,
    SceneBuilderConfigNumberReadable {}

export interface SceneBuilderQuickConfigBooleanProps
  extends SceneBuilderQuickConfigNumericProps,
    SceneBuilderConfigBooleanReadable {}

export interface SceneBuilderQuickConfigValueProps
  extends SceneBuilderQuickConfigStringProps,
    SceneBuilderConfigValueReadable {}

export interface SceneBuilderQuickConfigValueNumericProps
  extends SceneBuilderQuickConfigValueProps,
    SceneBuilderConfigNumberReadable {}

export interface SceneBuilderQuickConfigFormatter {
  formatQuickConfigValue: (value: unknown) => string
}

export interface SceneBuilderLooseConfigTextChangeHandler {
  handleLooseConfigTextChange: (key: string, value: string) => void
}

export interface SceneBuilderJsonConfigTextChangeHandler {
  handleJsonConfigTextChange: (key: string, value: string, emptyValue?: unknown) => void
}

export interface SceneBuilderSelectedStepActionType {
  selectedStepActionType: string
}

export interface SceneBuilderSelectedVariableScope {
  selectedVariableScope: string
}

export interface SceneBuilderSelectedPrimarySelectorType {
  selectedPrimarySelectorType: string
}

export interface SceneBuilderSelectedFallbackSelectorType {
  selectedFallbackSelectorType: string
}

export interface SceneBuilderSelectedClickSelectorType {
  selectedClickSelectorType: string
}

export interface SceneBuilderSelectedTargetSelectorType {
  selectedTargetSelectorType: string
}

export interface SceneBuilderSelectedAssertQuickMode {
  selectedAssertType: string
  selectedAssertQuickMode: string
}

export interface SceneBuilderExpectedListBindings {
  expectedListText: string
  handleExpectedListTextChange: (value: string) => void
}

export interface SceneBuilderAssertTypeChangeHandler {
  handleAssertTypeChange: (value: string) => void
}
